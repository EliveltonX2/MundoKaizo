from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.core.cache import cache
from django.core.files.storage import default_storage
from .models import Livro, Pagina, User, VideoAula
from .services import adicionar_watermark
from django.db.models import Q
from django.urls import reverse

@login_required
def estante_view(request):
    user = request.user
    livros = Livro.objects.filter(is_versao_professor=False)
    
    # --- NOVO: LÓGICA DE BUSCA ---
    query = request.GET.get('q') # Pega o que foi digitado no input name="q"
    if query:
        livros = livros.filter(titulo__icontains=query) # Filtra pelo título
    # -----------------------------
    
    context = {
        'livros': livros,
        'is_gestor': user.tipo in ['GESTOR_LOCAL', 'GESTOR_GERAL', 'ADMIN'] or user.tipo == 'PROFESSOR'
    }
    return render(request, 'core/estante.html', context)


@login_required
def pagina_livro_view(request, livro_id, numero_pagina):
    # 1. Busca o livro e a página
    livro = get_object_or_404(Livro, pk=livro_id)
    pagina = get_object_or_404(Pagina, livro=livro, numero=numero_pagina)

    # 2. Segurança
    if livro.is_versao_professor and request.user.tipo == 'ALUNO':
        return HttpResponseForbidden("Acesso restrito.")

    # 3. Cache Key
    cache_key = f"watermark_u{request.user.id}_l{livro_id}_p{numero_pagina}"
    imagem_data = cache.get(cache_key)

    if not imagem_data:
        try:
            # --- CORREÇÃO S3 ---
            # Não usamos .path! Abrimos o arquivo diretamente do S3.
            # O 'imagem_original' é um FieldFile que se comporta como arquivo aberto.
            arquivo_s3 = pagina.imagem_original
            arquivo_s3.open() # Abre o stream do S3
            
            # Passamos o ARQUIVO ABERTO para o serviço, não uma string de caminho
            buffer = adicionar_watermark(arquivo_s3, request.user.username.upper())
            
            if buffer:
                imagem_data = buffer.getvalue()
                cache.set(cache_key, imagem_data, timeout=86400)
            else:
                raise Exception("Falha ao gerar marca d'água")
                
        except Exception as e:
            print(f"ERRO S3/WATERMARK: {e}")
            return HttpResponse(status=500)

    # 5. Retorna como WEBP (já que seus arquivos originais são WebP)
    return HttpResponse(imagem_data, content_type="image/webp")

@login_required
def visualizar_livro(request, livro_id):
    livro = get_object_or_404(Livro, pk=livro_id)
    
    # Segurança
    if livro.is_versao_professor and request.user.tipo == 'ALUNO':
        return HttpResponseForbidden("Acesso restrito.")

    # 1. Busca Páginas
    paginas_db = livro.paginas.all().order_by('numero')
    
    # 2. Busca Vídeos relacionados a páginas deste livro
    videos_relacionados = livro.aulas.exclude(pagina_referencia=None)
    
    # Cria um dicionário para busca rápida: { numero_pagina: objeto_video }
    mapa_videos = {v.pagina_referencia.numero: v for v in videos_relacionados}

    # 3. Monta uma estrutura combinada para o Template
    # Em vez de mandar só a página, mandamos um dicionário com a página e o vídeo (se houver)
    paginas_estruturadas = []
    for p in paginas_db:
        paginas_estruturadas.append({
            'conteudo': p,                 # O objeto Pagina original
            'video': mapa_videos.get(p.numero) # O objeto VideoAula ou None
        })
    
    # Verifica se o usuário é "Staff" (Prof ou Gestor) para mostrar os botões extras
    is_staff_school = request.user.tipo in ['PROFESSOR', 'GESTOR_LOCAL', 'GESTOR_GERAL', 'ADMIN']

    context = {
        'livro': livro,
        'paginas_estruturadas': paginas_estruturadas, # Usaremos este novo nome no HTML
        'is_staff_school': is_staff_school
    }
    return render(request, 'core/leitor.html', context)

@login_required
def painel_gestao_view(request):
    user = request.user
    
    # Se for aluno, chuta para a estante (não tem acesso a painel)
    if user.tipo == 'ALUNO':
        return redirect('estante')

    # 1. Lógica de Hierarquia (Definir QUEM o usuário pode ver)
    usuarios_listados = User.objects.none() # Começa vazio
    
    if user.tipo == 'PROFESSOR':
        # Professor vê alunos das suas turmas
        minhas_turmas = user.turmas.all()
        usuarios_listados = User.objects.filter(
            tipo='ALUNO',
            turmas__in=minhas_turmas
        ).distinct()

    elif user.tipo == 'GESTOR_LOCAL':
        # Gestor Local vê Alunos e Professores das suas Escolas
        minhas_escolas = user.escolas.all()
        usuarios_listados = User.objects.filter(
            tipo__in=['ALUNO', 'PROFESSOR'],
            turmas__escola__in=minhas_escolas 
        ).distinct()

    elif user.tipo in ['GESTOR_GERAL', 'ADMIN'] or user.is_superuser:
        # Vê todo mundo (menos outros admins/superusers para segurança básica)
        usuarios_listados = User.objects.exclude(is_superuser=True)

    # 2. LÓGICA DE BUSCA (O que estava faltando)
    # Filtra a lista já definida acima com base no que foi digitado na navbar
    query = request.GET.get('q')
    if query:
        usuarios_listados = usuarios_listados.filter(
            Q(username__icontains=query) | 
            Q(first_name__icontains=query) |
            Q(email__icontains=query)
        )

    context = {
        'usuarios': usuarios_listados
    }
    return render(request, 'core/painel.html', context)


@login_required
def resetar_senha(request, user_id):
    # Apenas POST para segurança
    if request.method == 'POST':
        alvo = get_object_or_404(User, pk=user_id)
        quem_pede = request.user
        
        # Verificação de Segurança (Muito Importante!)
        autorizado = False
        
        if quem_pede.tipo == 'PROFESSOR':
            # Só pode se o alvo for aluno de suas turmas
            turmas_professor = quem_pede.turmas.all()
            if alvo.tipo == 'ALUNO' and alvo.turmas.filter(id__in=turmas_professor).exists():
                autorizado = True
                
        elif quem_pede.tipo == 'GESTOR_LOCAL':
            # Lógica simplificada: Se o alvo está numa turma de uma escola que o gestor cuida
            escolas_gestor = quem_pede.escolas.all()
            if alvo.turmas.filter(escola__in=escolas_gestor).exists():
                autorizado = True
        
        elif quem_pede.tipo in ['GESTOR_GERAL', 'ADMIN'] or quem_pede.is_superuser:
            autorizado = True

        if autorizado:
            nova_senha = "123456" # Senha padrão de reset (ou gerar aleatória)
            alvo.password = make_password(nova_senha) # Hash da senha
            alvo.save()
            messages.success(request, f"Senha de {alvo.username} resetada para '123456'.")
        else:
            messages.error(request, "Você não tem permissão para resetar este usuário.")
    
    return redirect('painel_gestao')


# core/views.py
from .models import VideoAula # Não esqueça de importar

@login_required
def lista_aulas_view(request, livro_id):
    livro = get_object_or_404(Livro, pk=livro_id)
    
    # Segurança
    if livro.is_versao_professor and request.user.tipo == 'ALUNO':
        return HttpResponseForbidden("Acesso restrito.")
        
    aulas = livro.aulas.all()
    
    # Verifica permissão
    is_staff = request.user.tipo in ['PROFESSOR', 'GESTOR_LOCAL', 'GESTOR_GERAL', 'ADMIN']
    
    if is_staff:
        # Funde com aulas do livro do professor, se houver
        if livro.versao_professor_relacionada:
            aulas_prof = livro.versao_professor_relacionada.aulas.all()
            aulas = aulas | aulas_prof
            
    aulas = aulas.distinct().order_by('ordem', 'titulo')
    
    context = {
        'livro': livro,
        'aulas': aulas,
        'is_staff': is_staff  # <--- ADICIONADO: Agora o template sabe se é Staff
    }
    return render(request, 'core/lista_aulas.html', context)

@login_required
def galeria_videos(request):
    """
    Página Rosto dos Vídeos (Galeria)
    Mostra vídeos avulsos e recentes.
    """
    # Lógica de Busca (reaproveitando a navbar)
    query = request.GET.get('q')
    if query:
        videos = VideoAula.objects.filter(titulo__icontains=query)
        titulo_pagina = f"Buscando por: {query}"
    else:
        # Pega todos os vídeos, ordenados pelos mais novos
        videos = VideoAula.objects.all().order_by('-criado_em')
        titulo_pagina = "Galeria de Vídeos"

    context = {
        'videos': videos,
        'titulo_pagina': titulo_pagina
    }
    return render(request, 'core/videos_home.html', context)


@login_required
def assistir_aula_view(request, aula_id):
    aula = get_object_or_404(VideoAula, pk=aula_id)
    livro = aula.livro
    
    # Segurança: Só verifica permissão de professor se o vídeo pertencer a um livro de professor
    if livro and livro.is_versao_professor and request.user.tipo == 'ALUNO':
        return HttpResponseForbidden("Acesso restrito.")
    
    # Navegação Lateral (Playlist)
    if livro:
        # Se tem livro, a playlist são as aulas do livro
        aulas_playlist = list(livro.aulas.all().order_by('ordem'))
        titulo_playlist = f"Aulas de: {livro.titulo}"
        voltar_url = reverse('lista_aulas', args=[livro.id])
    else:
        # Se é avulso, a playlist são outros vídeos avulsos ou recentes
        # Aqui pegamos os 10 últimos vídeos gerais para sugerir
        aulas_playlist = list(VideoAula.objects.all().order_by('-criado_em')[:10])
        titulo_playlist = "Últimos Vídeos Adicionados"
        voltar_url = reverse('galeria_videos')

    # Lógica de Próximo/Anterior na lista
    try:
        indice_atual = aulas_playlist.index(aula)
        proxima_aula = aulas_playlist[indice_atual + 1] if indice_atual + 1 < len(aulas_playlist) else None
        aula_anterior = aulas_playlist[indice_atual - 1] if indice_atual > 0 else None
    except ValueError:
        # Caso a aula atual não esteja na lista filtrada (ex: paginação)
        proxima_aula = None
        aula_anterior = None

    context = {
        'aula_atual': aula,
        'livro': livro, # Pode ser None agora
        'aulas': aulas_playlist,
        'titulo_playlist': titulo_playlist,
        'voltar_url': voltar_url,
        'proxima_aula': proxima_aula,
        'aula_anterior': aula_anterior
    }
    return render(request, 'core/assistir_aula.html', context)