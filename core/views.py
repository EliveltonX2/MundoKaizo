from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.core.cache import cache
from django.core.files.storage import default_storage
from .models import (
    Livro, Pagina, User, VideoAula, Turma, TokenCadastro, SessaoChat, 
    Mensagem, EstatisticasUsuario, RegistroAcessoDemo, AnoEscolar, 
    Cidade, Escola, Estado, Pais
)
from jogos.models import Jogo, SessaoJogo
from .services import adicionar_watermark
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import login
from .forms import *
from .services import enviar_mensagem_para_ia
from django.views.decorators.http import require_POST
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
import json
import markdown
import requests
import datetime


@login_required
def home_view(request):
    """ Página Inicial (Hub Principal) """
    return render(request, 'core/home.html')

@login_required
def estante_view(request):
    
    user = request.user
    query = request.GET.get('q')

    if request.user.tipo == 'DEMO':
        # Filtra SÓ os livros marcados como demonstração
        livros = Livro.objects.filter(is_demo=True).exclude(formato='INTERATIVO')

    elif request.user.tipo == 'ALUNO':
        livros = Livro.objects.filter(is_versao_professor=False, is_demo=False).exclude(formato='INTERATIVO')
        #TODO: uma forma de filtrar apenas o livro do ano especifico do aluno.

        
    
    else:
        user = request.user
        livros = Livro.objects.filter(is_versao_professor=False).exclude(formato='INTERATIVO')
        
        if query:
            livros = Livro.objects.filter(
            Q(titulo__icontains=query) | Q(tags__icontains=query))
   
    
    livros = livros.order_by('colecao__ordem', 'volume', 'titulo')

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
    
    if request.user.tipo == 'DEMO' and not livro.is_demo:
        messages.error(request, "Este livro é exclusivo para alunos matriculados e não está disponível na demonstração.")
        return redirect('home')

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
def detalhes_aluno_view(request, aluno_id):
    user = request.user
    
    if user.tipo == 'ALUNO':
        return redirect('home')
        
    aluno = get_object_or_404(User, pk=aluno_id, tipo='ALUNO')
    
    # 1. Segurança: checar se o usuário atual pode ver esse aluno
    autorizado = False
    if user.tipo == 'PROFESSOR':
        if aluno.turmas.filter(id__in=user.turmas.all()).exists():
            autorizado = True
    elif user.tipo == 'GESTOR_LOCAL':
        if aluno.turmas.filter(escola__in=user.escolas.all()).exists():
            autorizado = True
    elif user.tipo == 'GESTOR_REGIONAL':
        if aluno.turmas.filter(escola__cidade__in=user.cidades_gestao.all()).exists():
            autorizado = True
    elif user.tipo in ['GESTOR_KAIZO', 'ADMIN'] or user.is_superuser:
        autorizado = True
        
    if not autorizado:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Você não tem permissão para visualizar os detalhes deste aluno.")

    # 2. Resgatar Estatísticas
    from livros_interativos.models import SessaoAulaInterativa
    estatisticas, _ = EstatisticasUsuario.objects.get_or_create(user=aluno)
    sessoes_jogos = SessaoJogo.objects.filter(user=aluno).order_by('-atualizado_em')[:50]
    sessoes_livros = SessaoAulaInterativa.objects.filter(user=aluno).order_by('-atualizado_em')[:50]
    
    # NOVAS ESTATÍSTICAS
    from datetime import timedelta
    from django.utils import timezone
    hoje = timezone.now().date()
    
    # Mapa de acessos (30 dias)
    dias_30 = [hoje - timedelta(days=i) for i in range(29, -1, -1)]
    
    # Usando .values() invés de flat=True para evitar erros de date() cast em SQLite
    acessos_recente = RegistroAcessoDemo.objects.filter(
        user=aluno, 
        data_login__gte=timezone.now() - timedelta(days=31)
    )
    acessos_set = {a.data_login.date() for a in acessos_recente}
    
    mapa_acessos = []
    for d in dias_30:
        mapa_acessos.append({
            'data': d.strftime("%d/%m"),
            'ativo': d in acessos_set
        })
        
    # Últimos 5 acessos
    ultimos_5 = RegistroAcessoDemo.objects.filter(user=aluno).order_by('-data_login')[:5]
    ultimos_acessos_labels = [acesso.data_login.strftime("%d/%m") for acesso in reversed(ultimos_5)]
    ultimos_acessos_tempos = [acesso.tempo_navegacao_minutos for acesso in reversed(ultimos_5)]
    
    # Tempo por Habilidade BNCC
    tempo_habilidades = {}
    
    sessoes_j_all = SessaoJogo.objects.filter(user=aluno).select_related('jogo').prefetch_related('jogo__habilidades_relacionadas')
    for sj in sessoes_j_all:
        minutos = sj.tempo_jogo / 60.0 if sj.tempo_jogo else 0
        if minutos > 0:
            for h in sj.jogo.habilidades_relacionadas.all():
                label = f"{h.codigo}"
                tempo_habilidades[label] = tempo_habilidades.get(label, 0) + minutos
                
    sessoes_l_all = SessaoAulaInterativa.objects.filter(user=aluno).select_related('aula').prefetch_related('aula__habilidades_bncc')
    for sl in sessoes_l_all:
        minutos = sl.tempo_gasto / 60.0 if sl.tempo_gasto else 0
        if minutos > 0:
            for h in sl.aula.habilidades_bncc.all():
                label = f"{h.codigo}"
                tempo_habilidades[label] = tempo_habilidades.get(label, 0) + minutos
                
    habilidades_ordenadas = sorted(tempo_habilidades.items(), key=lambda x: x[1], reverse=True)[:15] # Top 15
    habilidades_labels = [item[0] for item in habilidades_ordenadas]
    habilidades_tempos = [round(item[1], 1) for item in habilidades_ordenadas]
    
    import json
    context = {
        'aluno': aluno,
        'estatisticas': estatisticas,
        'sessoes_jogos': sessoes_jogos,
        'sessoes_livros': sessoes_livros,
        'mapa_acessos': mapa_acessos,
        'ultimos_acessos_labels_json': json.dumps(ultimos_acessos_labels),
        'ultimos_acessos_tempos_json': json.dumps(ultimos_acessos_tempos),
        'habilidades_labels_json': json.dumps(habilidades_labels),
        'habilidades_tempos_json': json.dumps(habilidades_tempos),
    }
    return render(request, 'core/detalhes_aluno.html', context)


@login_required
def resetar_senha(request, user_id):
    # Apenas POST para segurança
    if request.method == 'POST':
        alvo = get_object_or_404(User, pk=user_id)
        quem_pede = request.user
        
        # Verificação de Segurança Hierárquica
        autorizado = False
        
        if quem_pede.tipo == 'PROFESSOR':
            # Só pode se o alvo for aluno de suas turmas
            turmas_professor = quem_pede.turmas.all()
            if alvo.tipo == 'ALUNO' and alvo.turmas.filter(id__in=turmas_professor).exists():
                autorizado = True
                
        elif quem_pede.tipo == 'GESTOR_LOCAL':
            # Se o alvo está numa turma de uma escola que o gestor cuida
            escolas_gestor = quem_pede.escolas.all()
            if alvo.turmas.filter(escola__in=escolas_gestor).exists():
                autorizado = True

        elif quem_pede.tipo == 'GESTOR_REGIONAL':
            cidades_gestor = quem_pede.cidades_gestao.all()
            escolas_gestor = quem_pede.escolas.all()
            if alvo.turmas.filter(Q(escola__cidade__in=cidades_gestor) | Q(escola__in=escolas_gestor)).exists():
                autorizado = True

        elif quem_pede.tipo == 'GESTOR_REDE':
            cidades_gestor = quem_pede.cidades_gestao.all()
            estados_gestor = quem_pede.estados_gestao.all()
            if alvo.turmas.filter(Q(escola__cidade__in=cidades_gestor) | Q(escola__cidade__estado__in=estados_gestor)).exists():
                autorizado = True
        
        elif quem_pede.tipo in ['GESTOR_KAIZO', 'ADMIN', 'GESTOR_GERAL'] or quem_pede.is_superuser:
            autorizado = True

        if autorizado:
            nova_senha = "123456" # Senha padrão de reset
            alvo.password = make_password(nova_senha) # Hash da senha
            alvo.save()
            messages.success(request, f"Senha do aluno '{alvo.get_full_name() or alvo.username}' resetada para '123456'.")
        else:
            messages.error(request, "Você não tem permissão para resetar a senha deste usuário.")
    
    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('detalhes_aluno', aluno_id=user_id)




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

def ativar_conta_view(request):
    # FASE 1: Digitar Código
    if 'token_id' not in request.session:
        if request.method == 'POST':
            form = ValidarTokenForm(request.POST)
            if form.is_valid():
                token = TokenCadastro.objects.get(codigo=form.cleaned_data['codigo'])
                request.session['token_id'] = token.id
                request.session['token_tipo'] = token.tipo_usuario
                return redirect('ativar_conta')
        else:
            form = ValidarTokenForm()
        return render(request, 'core/ativar_codigo.html', {'form': form})

    # FASE 2: Preencher Dados
    token_id = request.session.get('token_id')
    token_tipo = request.session.get('token_tipo')
    token = TokenCadastro.objects.get(id=token_id)
    
    if request.method == 'POST':
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['senha'])
            
            # 1. APLICA O TIPO DE USUÁRIO DIRETO DO CARTÃO
            user.tipo = token.tipo_usuario 
            user.save()
            
            # 2. VINCULAÇÕES
            # Se o cartão tem uma escola (Gestor, Prof, Aluno), vincula.
            if token.escola:
                user.escolas.add(token.escola)
            
            # Se o cartão tem uma turma (Aluno), vincula.
            if token.turma and token.tipo_usuario == 'ALUNO':
                user.turmas.add(token.turma)
            
            # 3. QUEIMA O CARTÃO
            token.usado = True
            token.usado_por = user
            token.data_uso = timezone.now()
            token.save()
            
            # 4. LIMPEZA E REDIRECIONAMENTO
            del request.session['token_id']
            del request.session['token_tipo']
            login(request, user)
            
            # Todos vão para a estante inicialmente (você pode mudar depois)
            return redirect('home') 
    else:
        form = RegistroUsuarioForm()
        
    # Passamos o tipo (ex: "Professor") para o HTML mostrar "Bem-vindo, Professor!"
    contexto = {
        'form': form, 
        'token': token,
        'tipo_nome': token.get_tipo_usuario_display()
    }
    return render(request, 'registration/cadastro_usuario.html', contexto)

# API simples para o Javascript consumir
def api_turmas_por_escola(request, escola_id):
    turmas = Turma.objects.filter(escola_id=escola_id).values('id', 'nome', 'serie') 
    # Ajuste 'nome' e 'serie' conforme seus campos no models.py
    
    lista_turmas = []
    for t in turmas:
        lista_turmas.append({
            'id': t['id'],
            'nome_completo': f"{t['serie']} - {t['nome']}" # Ex: "6º Ano - A"
        })
        
    return JsonResponse(lista_turmas, safe=False)


@login_required
def vincular_cartoes_view(request):
    # Alunos não têm acesso a /gestao/*
    if request.user.tipo == 'ALUNO':
        messages.error(request, "Acesso restrito. Alunos não têm acesso à área de gestão.")
        return redirect('home')

    # Apenas Professores ou Gestores podem acessar
    if request.user.tipo not in ['PROFESSOR', 'GESTOR_LOCAL', 'GESTOR_REGIONAL', 'GESTOR_REDE', 'GESTOR_KAIZO', 'GESTOR_GERAL', 'ADMIN'] and not request.user.is_superuser:
        return redirect('home')

    if request.method == 'POST':
        form = VincularCartoesForm(request.POST, professor=request.user)
        if form.is_valid():
            codigos_raw = form.cleaned_data['codigos']
            turma_selecionada = form.cleaned_data['turma']
            
            # Limpa o texto, separando por linha e removendo espaços
            lista_codigos = [c.strip().upper() for c in codigos_raw.split('\n') if c.strip()]
            
            sucesso = 0
            erros = 0
            
            for codigo in lista_codigos:
                try:
                    # Busca o token em branco
                    token = TokenCadastro.objects.get(codigo=codigo, tipo_usuario='ALUNO', usado=False)
                    # Vincula a turma e a escola
                    token.turma = turma_selecionada
                    token.escola = turma_selecionada.escola
                    token.save()
                    sucesso += 1
                except TokenCadastro.DoesNotExist:
                    erros += 1
            
            if sucesso > 0:
                messages.success(request, f"{sucesso} cartões foram vinculados à turma {turma_selecionada.nome} com sucesso!")
            if erros > 0:
                messages.warning(request, f"{erros} códigos eram inválidos, não eram de aluno ou já estavam usados.")
                
            return redirect('vincular_cartoes')
    else:
        form = VincularCartoesForm(professor=request.user)

    return render(request, 'core/vincular_cartoes.html', {'form': form})

@login_required
def gestao_organizacao_view(request):
    user = request.user
    
    # 1. Alunos e usuários Demo NÃO têm acesso à página de controle de turmas /gestao/*
    if user.tipo in ['ALUNO', 'DEMO']:
        messages.error(request, "Acesso restrito. Alunos não têm acesso à área de controle de turmas e gestão.")
        return redirect('home')

    # Permissões do usuário
    is_admin = user.is_superuser or user.tipo in ['ADMIN', 'GESTOR_KAIZO', 'GESTOR_GERAL']
    is_gestor_rede = user.tipo == 'GESTOR_REDE'
    is_gestor_regional = user.tipo == 'GESTOR_REGIONAL'
    is_gestor_local = user.tipo == 'GESTOR_LOCAL'
    is_professor = user.tipo == 'PROFESSOR'

    if not (is_admin or is_gestor_rede or is_gestor_regional or is_gestor_local or is_professor):
        messages.error(request, "Você não tem permissão para acessar esta área.")
        return redirect('home')

    # Níveis de capacidade
    pode_gerenciar_rede = is_admin or is_gestor_rede
    pode_gerenciar_escolas = is_admin or is_gestor_rede or is_gestor_regional
    pode_gerenciar_turmas = is_admin or is_gestor_rede or is_gestor_regional or is_gestor_local

    # Escopos de Dados
    if is_admin:
        cidades_escopo = Cidade.objects.all().select_related('estado').order_by('nome')
        escolas_escopo = Escola.objects.all().select_related('cidade', 'cidade__estado').order_by('nome')
        turmas_escopo = Turma.objects.all().select_related('escola', 'ano_escolar').prefetch_related('user_set').order_by('escola__nome', 'nome')
    elif is_gestor_rede:
        cidades_escopo = user.cidades_gestao.all().select_related('estado').order_by('nome')
        escolas_escopo = Escola.objects.filter(
            Q(cidade__in=cidades_escopo) | Q(cidade__estado__in=user.estados_gestao.all())
        ).distinct().select_related('cidade', 'cidade__estado').order_by('nome')
        turmas_escopo = Turma.objects.filter(escola__in=escolas_escopo).select_related('escola', 'ano_escolar').prefetch_related('user_set').order_by('escola__nome', 'nome')
    elif is_gestor_regional:
        cidades_escopo = user.cidades_gestao.all().select_related('estado').order_by('nome')
        escolas_escopo = Escola.objects.filter(
            Q(cidade__in=cidades_escopo) | Q(id__in=user.escolas.values_list('id', flat=True))
        ).distinct().select_related('cidade', 'cidade__estado').order_by('nome')
        turmas_escopo = Turma.objects.filter(escola__in=escolas_escopo).select_related('escola', 'ano_escolar').prefetch_related('user_set').order_by('escola__nome', 'nome')
    elif is_gestor_local:
        cidades_escopo = Cidade.objects.none()
        escolas_escopo = user.escolas.all().select_related('cidade', 'cidade__estado').order_by('nome')
        turmas_escopo = Turma.objects.filter(escola__in=escolas_escopo).select_related('escola', 'ano_escolar').prefetch_related('user_set').order_by('escola__nome', 'nome')
    else: # PROFESSOR
        cidades_escopo = Cidade.objects.none()
        escolas_escopo = user.escolas.all().select_related('cidade', 'cidade__estado').order_by('nome')
        turmas_escopo = user.turmas.all().select_related('escola', 'ano_escolar').prefetch_related('user_set').order_by('escola__nome', 'nome')

    aba_ativa = request.GET.get('aba', 'turmas')

    if request.method == 'POST':
        acao = request.POST.get('acao')
        aba_ativa = request.POST.get('aba_origem', 'turmas')

        # 1. CRIAR TURMA
        if acao == 'criar_turma':
            if not pode_gerenciar_turmas:
                messages.error(request, "Você não tem permissão para criar turmas.")
                return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

            nome = request.POST.get('nome', '').strip()
            escola_id = request.POST.get('escola')
            ano_escolar_id = request.POST.get('ano_escolar')
            professor_id = request.POST.get('professor')

            if not nome or not escola_id:
                messages.error(request, "Nome da turma e Escola são obrigatórios.")
                return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

            escola = get_object_or_404(Escola, id=escola_id)
            if not is_admin and escola not in escolas_escopo:
                messages.error(request, "Você não tem permissão para cadastrar turmas nesta escola.")
                return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

            ano_obj = AnoEscolar.objects.filter(id=ano_escolar_id).first() if ano_escolar_id else None
            turma = Turma.objects.create(nome=nome, escola=escola, ano_escolar=ano_obj)

            if professor_id:
                prof = User.objects.filter(id=professor_id, tipo='PROFESSOR').first()
                if prof:
                    prof.turmas.add(turma)
                    prof.escolas.add(escola)
                    messages.success(request, f"Turma '{turma.nome}' criada com sucesso e atribuída ao professor {prof.get_full_name() or prof.username}!")
                else:
                    messages.success(request, f"Turma '{turma.nome}' criada com sucesso!")
            else:
                messages.success(request, f"Turma '{turma.nome}' criada com sucesso!")

            return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

        # 2. EDITAR TURMA
        elif acao == 'editar_turma':
            if not pode_gerenciar_turmas:
                messages.error(request, "Você não tem permissão para editar turmas.")
                return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

            turma_id = request.POST.get('turma_id')
            turma = get_object_or_404(Turma, id=turma_id)
            if not is_admin and turma not in turmas_escopo:
                messages.error(request, "Você não tem permissão sobre esta turma.")
                return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

            nome = request.POST.get('nome', '').strip()
            escola_id = request.POST.get('escola')
            ano_escolar_id = request.POST.get('ano_escolar')

            if not nome:
                messages.error(request, "O nome da turma não pode ficar em branco.")
                return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

            turma.nome = nome
            if escola_id:
                escola = get_object_or_404(Escola, id=escola_id)
                if not is_admin and escola not in escolas_escopo:
                    messages.error(request, "Escola selecionada fora do seu escopo.")
                    return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")
                turma.escola = escola

            turma.ano_escolar = AnoEscolar.objects.filter(id=ano_escolar_id).first() if ano_escolar_id else None
            turma.save()
            messages.success(request, f"Turma '{turma.nome}' atualizada com sucesso!")
            return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

        # 3. EXCLUIR TURMA COM CONFIRMAÇÃO DE DIGITAÇÃO
        elif acao == 'excluir_turma':
            if not pode_gerenciar_turmas:
                messages.error(request, "Você não tem permissão para excluir turmas.")
                return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

            turma_id = request.POST.get('turma_id')
            nome_confirmacao = request.POST.get('nome_confirmacao', '').strip()
            turma = get_object_or_404(Turma, id=turma_id)

            if not is_admin and turma not in turmas_escopo:
                messages.error(request, "Você não tem permissão sobre esta turma.")
                return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

            if nome_confirmacao.lower() != turma.nome.strip().lower():
                messages.error(request, f"Aviso de Segurança: Para excluir a turma, é necessário digitar exatamente o nome '{turma.nome}'. A confirmação digitada ('{nome_confirmacao}') não confere.")
                return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

            nome_excluido = turma.nome
            turma.delete()
            messages.success(request, f"A turma '{nome_excluido}' foi excluída com sucesso.")
            return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

        # 4. ATRIBUIR PROFESSOR À TURMA
        elif acao == 'atribuir_professor':
            if not pode_gerenciar_turmas:
                messages.error(request, "Sem permissão.")
                return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

            turma_id = request.POST.get('turma_id')
            professor_id = request.POST.get('professor_id')
            turma = get_object_or_404(Turma, id=turma_id)
            if not is_admin and turma not in turmas_escopo:
                messages.error(request, "Turma fora do seu escopo.")
                return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

            prof = get_object_or_404(User, id=professor_id, tipo='PROFESSOR')
            prof.turmas.add(turma)
            prof.escolas.add(turma.escola)
            messages.success(request, f"Professor {prof.get_full_name() or prof.username} atribuído à turma '{turma.nome}' com sucesso!")
            return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

        # 5. REMOVER PROFESSOR DA TURMA
        elif acao == 'remover_professor':
            if not pode_gerenciar_turmas:
                messages.error(request, "Sem permissão.")
                return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

            turma_id = request.POST.get('turma_id')
            professor_id = request.POST.get('professor_id')
            turma = get_object_or_404(Turma, id=turma_id)
            if not is_admin and turma not in turmas_escopo:
                messages.error(request, "Turma fora do seu escopo.")
                return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

            prof = get_object_or_404(User, id=professor_id)
            prof.turmas.remove(turma)
            messages.success(request, f"Professor {prof.get_full_name() or prof.username} desvinculado da turma '{turma.nome}'.")
            return redirect(f"{reverse('gestao_organizacao')}?aba={aba_ativa}")

        # 6. ATRIBUIR GESTOR ESCOLAR À ESCOLA (Gestor Regional+)
        elif acao == 'atribuir_gestor_escola':
            if not pode_gerenciar_escolas:
                messages.error(request, "Você não tem permissão para gerenciar gestores escolares.")
                return redirect(f"{reverse('gestao_organizacao')}?aba=escolas")

            escola_id = request.POST.get('escola_id')
            gestor_id = request.POST.get('gestor_id')
            escola = get_object_or_404(Escola, id=escola_id)
            if not is_admin and escola not in escolas_escopo:
                messages.error(request, "Escola fora do seu escopo.")
                return redirect(f"{reverse('gestao_organizacao')}?aba=escolas")

            gestor = get_object_or_404(User, id=gestor_id, tipo='GESTOR_LOCAL')
            gestor.escolas.add(escola)
            messages.success(request, f"Gestor {gestor.get_full_name() or gestor.username} associado à escola '{escola.nome}' com sucesso!")
            return redirect(f"{reverse('gestao_organizacao')}?aba=escolas")

        # 7. REMOVER GESTOR ESCOLAR DA ESCOLA
        elif acao == 'remover_gestor_escola':
            if not pode_gerenciar_escolas:
                messages.error(request, "Sem permissão.")
                return redirect(f"{reverse('gestao_organizacao')}?aba=escolas")

            escola_id = request.POST.get('escola_id')
            gestor_id = request.POST.get('gestor_id')
            escola = get_object_or_404(Escola, id=escola_id)
            if not is_admin and escola not in escolas_escopo:
                messages.error(request, "Escola fora do seu escopo.")
                return redirect(f"{reverse('gestao_organizacao')}?aba=escolas")

            gestor = get_object_or_404(User, id=gestor_id)
            gestor.escolas.remove(escola)
            messages.success(request, f"Gestor {gestor.get_full_name() or gestor.username} desvinculado da escola '{escola.nome}'.")
            return redirect(f"{reverse('gestao_organizacao')}?aba=escolas")

        # 8. ATRIBUIR GESTOR REGIONAL À CIDADE/REDE (Gestor de Rede+)
        elif acao == 'atribuir_gestor_regional':
            if not pode_gerenciar_rede:
                messages.error(request, "Você não tem permissão para gerenciar gestores regionais.")
                return redirect(f"{reverse('gestao_organizacao')}?aba=rede")

            cidade_id = request.POST.get('cidade_id')
            gestor_id = request.POST.get('gestor_id')
            cidade = get_object_or_404(Cidade, id=cidade_id)
            if not is_admin and cidade not in cidades_escopo:
                messages.error(request, "Cidade/Rede fora do seu escopo.")
                return redirect(f"{reverse('gestao_organizacao')}?aba=rede")

            gestor = get_object_or_404(User, id=gestor_id, tipo='GESTOR_REGIONAL')
            gestor.cidades_gestao.add(cidade)
            messages.success(request, f"Gestor Regional {gestor.get_full_name() or gestor.username} associado à rede '{cidade.nome}' com sucesso!")
            return redirect(f"{reverse('gestao_organizacao')}?aba=rede")

        # 9. REMOVER GESTOR REGIONAL DA CIDADE/REDE
        elif acao == 'remover_gestor_regional':
            if not pode_gerenciar_rede:
                messages.error(request, "Sem permissão.")
                return redirect(f"{reverse('gestao_organizacao')}?aba=rede")

            cidade_id = request.POST.get('cidade_id')
            gestor_id = request.POST.get('gestor_id')
            cidade = get_object_or_404(Cidade, id=cidade_id)
            if not is_admin and cidade not in cidades_escopo:
                messages.error(request, "Cidade/Rede fora do seu escopo.")
                return redirect(f"{reverse('gestao_organizacao')}?aba=rede")

            gestor = get_object_or_404(User, id=gestor_id)
            gestor.cidades_gestao.remove(cidade)
            messages.success(request, f"Gestor Regional {gestor.get_full_name() or gestor.username} desvinculado da rede '{cidade.nome}'.")
            return redirect(f"{reverse('gestao_organizacao')}?aba=rede")

    # Montagem dos dados de exibição
    turmas_cards = []
    total_alunos_contados = 0
    for t in turmas_escopo:
        profs = t.user_set.filter(tipo='PROFESSOR', is_active=True).order_by('first_name', 'username')
        alunos = t.user_set.filter(tipo='ALUNO', is_active=True).order_by('first_name', 'username')
        total_alunos_contados += alunos.count()
        turmas_cards.append({
            'turma': t,
            'professores': profs,
            'alunos': alunos,
            'total_alunos': alunos.count()
        })

    escolas_cards = []
    if pode_gerenciar_escolas:
        for esc in escolas_escopo:
            gestores = esc.user_set.filter(tipo='GESTOR_LOCAL', is_active=True).order_by('first_name', 'username')
            escolas_cards.append({
                'escola': esc,
                'gestores': gestores,
                'total_turmas': esc.turma_set.count()
            })

    cidades_cards = []
    if pode_gerenciar_rede:
        for cid in cidades_escopo:
            gestores_reg = cid.user_set.filter(tipo='GESTOR_REGIONAL', is_active=True).order_by('first_name', 'username')
            cidades_cards.append({
                'cidade': cid,
                'gestores': gestores_reg,
                'total_escolas': cid.escola_set.count()
            })

    anos_escolares = AnoEscolar.objects.all().order_by('ordem')
    professores_disponiveis = User.objects.filter(tipo='PROFESSOR', is_active=True).order_by('first_name', 'username')
    gestores_locais_disponiveis = User.objects.filter(tipo='GESTOR_LOCAL', is_active=True).order_by('first_name', 'username') if pode_gerenciar_escolas else []
    gestores_regionais_disponiveis = User.objects.filter(tipo='GESTOR_REGIONAL', is_active=True).order_by('first_name', 'username') if pode_gerenciar_rede else []

    contexto = {
        'aba_ativa': aba_ativa,
        'pode_gerenciar_turmas': pode_gerenciar_turmas,
        'pode_gerenciar_escolas': pode_gerenciar_escolas,
        'pode_gerenciar_rede': pode_gerenciar_rede,
        'is_professor': is_professor,
        'is_gestor_local': is_gestor_local,
        'is_gestor_regional': is_gestor_regional,
        'is_gestor_rede': is_gestor_rede,
        'is_admin': is_admin,
        'turmas_cards': turmas_cards,
        'escolas_cards': escolas_cards,
        'cidades_cards': cidades_cards,
        'anos_escolares': anos_escolares,
        'escolas_disponiveis': escolas_escopo,
        'professores_disponiveis': professores_disponiveis,
        'gestores_locais_disponiveis': gestores_locais_disponiveis,
        'gestores_regionais_disponiveis': gestores_regionais_disponiveis,
        'total_turmas': len(turmas_cards),
        'total_alunos': total_alunos_contados,
        'total_escolas': len(escolas_cards) if pode_gerenciar_escolas else 0,
        'total_cidades': len(cidades_cards) if pode_gerenciar_rede else 0,
    }
    return render(request, 'core/gestao_organizacao.html', contexto)

def criar_turma_view(request):
    """ Redireciona a chamada da view legada criar_turma para a nova página de Gestão e Organização """
    return gestao_organizacao_view(request)



@login_required
def chat_view(request):
    # Pega o ID da sessão da URL (para quando o usuário clica no menu lateral)
    sessao_id = request.GET.get('sessao')
    nova_conversa = request.GET.get('nova')

    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            texto_usuario = dados.get('mensagem')
            sessao_post_id = dados.get('sessao_id') # Recebe o ID do JavaScript

            # 1. Identifica a conversa atual ou cria uma nova se for o primeiro envio
            if sessao_post_id:
                sessao = SessaoChat.objects.get(id=sessao_post_id, user=request.user)
            else:
                sessao = SessaoChat.objects.create(user=request.user)

            # 2. SISTEMA DE MEMÓRIA: Pega as últimas 10 mensagens
            ultimas_mensagens = sessao.mensagens.all().order_by('-criado_em')[:12]
            contexto_texto = ""
            # Inverte a ordem para que o histórico fique cronológico para a IA ler
            for msg in reversed(ultimas_mensagens):
                quem = "Professor" if msg.is_user else "Kai"


                contexto_texto += f"{quem}: {msg.texto}\n"
                

            # 3. Salva a nova pergunta no banco
            Mensagem.objects.create(sessao=sessao, is_user=True, texto=texto_usuario)

            nome_professor = request.user.first_name if request.user.first_name else request.user.username

            # 4. Envia para a IA passando o contexto do histórico
            resposta_ia_texto = enviar_mensagem_para_ia(texto_usuario, contexto_texto, nome_professor, request.user.tipo)

            # 5. Salva a resposta e converte para HTML (Markdown)
            Mensagem.objects.create(sessao=sessao, is_user=False, texto=resposta_ia_texto)
            resposta_html = markdown.markdown(resposta_ia_texto, extensions=['nl2br'])

            # Retorna a resposta e o ID da sessão para o JavaScript não se perder
            return JsonResponse({
                'status': 'sucesso', 
                'resposta': resposta_html,
                'sessao_id': sessao.id
            })

        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)

    # --- LÓGICA DE CARREGAMENTO DA PÁGINA (GET) ---
    
    # Busca todas as conversas antigas para montar o menu lateral
    todas_sessoes = SessaoChat.objects.filter(user=request.user).order_by('-criado_em')
    sessao_atual = None
    
    if nova_conversa == 'true':
        sessao_atual = None

    elif sessao_id:
        sessao_atual = SessaoChat.objects.filter(id=sessao_id, user=request.user).first()
        
    elif todas_sessoes.exists():
        sessao_atual = todas_sessoes.first()

    # Prepara o histórico da conversa aberta
    historico = sessao_atual.mensagens.all() if sessao_atual else []
    for msg in historico:
        msg.html_texto = markdown.markdown(msg.texto, extensions=['nl2br'])
    
    context = {
        'sessoes': todas_sessoes,
        'sessao_atual': sessao_atual,
        'historico': historico
    }
    return render(request, 'core/chat.html', context)

@login_required
def renomear_chat(request, sessao_id):
    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            novo_titulo = dados.get('titulo')
            
            # Busca a sessão garantindo que pertence ao usuário logado
            sessao = SessaoChat.objects.get(id=sessao_id, user=request.user)
            sessao.titulo = novo_titulo
            sessao.save()
            
            return JsonResponse({'status': 'sucesso'})
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)
    return JsonResponse({'status': 'metodo_invalido'}, status=405)

@login_required
def deletar_chat(request, sessao_id):
    if request.method == 'POST':
        try:
            sessao = SessaoChat.objects.get(id=sessao_id, user=request.user)
            sessao.delete()
            return JsonResponse({'status': 'sucesso'})
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)
    return JsonResponse({'status': 'metodo_invalido'}, status=405)


@login_required
@require_POST
def atualizar_localizacao_gps(request):
    # Ignora se não for conta DEMO
    if request.user.tipo != 'DEMO':
        return JsonResponse({'status': 'ignorado'})
    
    # Pega a sessão atual de navegação que o middleware e o signal criaram
    registro_id = request.session.get('registro_acesso_demo_id')
    if not registro_id:
        return JsonResponse({'status': 'sem_sessao'})
        
    try:
        dados = json.loads(request.body)
        lat = dados.get('latitude')
        lon = dados.get('longitude')
        
        if lat and lon:
            # Usamos a API gratuita do OpenStreetMap (Nominatim) para converter Lat/Lon em Cidade
            url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
            # O OpenStreetMap exige um User-Agent para não bloquear a requisição
            headers = {'User-Agent': 'MundoKaizoApp/1.0'}
            
            resp = requests.get(url, headers=headers, timeout=5).json()
            
            address = resp.get('address', {})
            cidade = address.get('city', address.get('town', address.get('village', '')))
            estado = address.get('state', '')
            
            if cidade and estado:
                # Colocamos um emoji de pino para você saber no Admin que essa info veio do GPS (alta precisão)
                localizacao_exata = f"📍 {cidade}, {estado} (GPS) [{lat}, {lon}]"
                
                # Atualiza o registro no banco de dados!
                from .models import RegistroAcessoDemo
                RegistroAcessoDemo.objects.filter(id=registro_id).update(localizacao=localizacao_exata)
                
                return JsonResponse({'status': 'sucesso', 'local': localizacao_exata})
                
    except Exception as e:
        print(f"Erro ao converter GPS: {e}")
        
    return JsonResponse({'status': 'erro'})

@login_required
def gerar_presigned_url_view(request):
    # A trava de segurança
    if not (request.user.is_superuser or request.user.is_staff or getattr(request.user, 'tipo', '') in ['GESTOR_GERAL', 'ADMIN']):
        return JsonResponse({'erro': 'Sem permissão.'}, status=403)

    nome_arquivo = request.GET.get('file_name')
    tipo_arquivo = request.GET.get('file_type') or 'application/octet-stream'
    pasta_jogo = request.GET.get('pasta_jogo')
    pasta_base = request.GET.get('pasta_base', 'jogos_web')

    if not nome_arquivo or not pasta_jogo:
        return JsonResponse({'erro': 'Faltam parâmetros'}, status=400)

    # --- O DETETIVE DA UNITY (Arruma a compressão e os tipos de arquivo) ---
    content_encoding = None
    
    # 1. Arruma o tipo principal (WASM e JS)
    if '.wasm' in nome_arquivo:
        tipo_arquivo = 'application/wasm'
    elif '.js' in nome_arquivo:
        tipo_arquivo = 'application/javascript'

    # 2. Descobre se está comprimido com Brotli (.br) ou Gzip (.gz)
    if nome_arquivo.endswith('.br'):
        content_encoding = 'br'
    elif nome_arquivo.endswith('.gz'):
        content_encoding = 'gzip'
    # ------------------------------------------------------------------------

    caminho_s3 = f"{pasta_base}/{pasta_jogo}/{nome_arquivo}"

    try:
        import boto3
        from django.conf import settings
        
        chave_acesso = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
        chave_secreta = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        regiao = getattr(settings, 'AWS_S3_REGION_NAME', getattr(settings, 'AWS_REGION', 'us-east-1'))
        bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)

        if not bucket:
            return JsonResponse({'erro': 'Bucket não configurado no settings.py'}, status=500)

        s3_client = boto3.client(
            's3',
            aws_access_key_id=chave_acesso,
            aws_secret_access_key=chave_secreta,
            region_name=regiao
        )

        # Montamos as regras base para a Amazon
        fields = {"Content-Type": tipo_arquivo}
        conditions = [{"Content-Type": tipo_arquivo}]

        # Se for um arquivo compactado, ADICIONA A ORDEM DE DESCOMPACTAÇÃO para a AWS!
        if content_encoding:
            fields["Content-Encoding"] = content_encoding
            conditions.append({"Content-Encoding": content_encoding})

        presigned_post = s3_client.generate_presigned_post(
            Bucket=bucket,
            Key=caminho_s3,
            Fields=fields,
            Conditions=conditions,
            ExpiresIn=3600
        )
        return JsonResponse(presigned_post)

    except Exception as e:
        import traceback
        print("\n" + "="*50)
        print("🚨 ERRO GRAVE AO GERAR PRESIGNED URL 🚨")
        traceback.print_exc()
        print("="*50 + "\n")
        return JsonResponse({'erro': f'Erro interno: {str(e)}'}, status=500)

@login_required
def salvar_registro_jogo(request):
    """ Chamado pelo JS após terminar o upload de todos os arquivos """
    if request.method == 'POST':
        import json
        dados = json.loads(request.body)
        
        # Cria o registro no banco de dados
        from .models import Jogo
        jogo = Jogo.objects.create(
            titulo=dados.get('titulo'),
            descricao=dados.get('descricao'),
            caminho_s3=f"jogos_web/{dados.get('pasta_jogo')}"
        )
        
        # Associa as habilidades selecionadas
        habilidades_ids = dados.get('habilidades', [])
        if habilidades_ids:
            jogo.habilidades_relacionadas.set(habilidades_ids)
            
        return JsonResponse({'status': 'sucesso', 'jogo_id': jogo.id})
    

@staff_member_required
def upload_jogos_view(request):
    # Essa view só pode ser acessada por quem tem o is_staff=True (quem acessa o admin)
    from .models import HabilidadeBNCC
    habilidades = HabilidadeBNCC.objects.all().order_by('codigo')
    return render(request, 'core/upload_jogos.html', {'habilidades_bncc': habilidades})

@login_required
def jogos_list_view(request):
    # Captura o que o usuário digitou na barra de busca (se houver)
    query = request.GET.get('q', '')
    
    # Traz apenas os jogos que estão com a caixinha "Ativo" marcada no painel Admin
    jogos = Jogo.objects.filter(ativo=True).order_by('-criado_em')
    
    if query:
        # Filtra pelo título ignorando maiúsculas/minúsculas (icontains)
        jogos = jogos.filter(titulo__icontains=query)
        
    estatisticas, created = EstatisticasUsuario.objects.get_or_create(user=request.user)
    ranking = EstatisticasUsuario.objects.filter(pontuacao_geral__gt=estatisticas.pontuacao_geral).count() + 1
        
    return render(request, 'core/jogos.html', {
        'jogos': jogos, 
        'query': query,
        'estatisticas': estatisticas,
        'ranking': ranking
    })


@login_required
def jogar_view(request, jogo_id):
    # Busca o jogo ou retorna página 404 se não existir
    jogo = get_object_or_404(Jogo, id=jogo_id, ativo=True)
    return render(request, 'core/jogar.html', {'jogo': jogo})


@login_required
def gerar_presigned_url_paginas(request):
    if not (request.user.is_superuser or request.user.is_staff or getattr(request.user, 'tipo', '') in ['GESTOR_GERAL', 'ADMIN']):
        return JsonResponse({'erro': 'Sem permissão.'}, status=403)

    nome_arquivo = request.GET.get('file_name')
    tipo_arquivo = request.GET.get('file_type') or 'image/webp'

    if not nome_arquivo:
        return JsonResponse({'erro': 'Faltam parâmetros'}, status=400)

    # 1. Imitamos o "upload_to='livros_source/%Y/%m/'" do Django
    hoje = datetime.date.today()
    caminho_relativo = f"livros_source/{hoje.strftime('%Y')}/{hoje.strftime('%m')}/{nome_arquivo}"

    # 2. O Pulo do Gato: A AWS precisa saber da pasta raiz (mundokaizo_media)
    aws_location = getattr(settings, 'AWS_LOCATION', '')
    if aws_location:
        caminho_s3_real = f"{aws_location}/{caminho_relativo}"
    else:
        caminho_s3_real = caminho_relativo

    try:
        import boto3
        chave_acesso = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
        chave_secreta = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        regiao = getattr(settings, 'AWS_S3_REGION_NAME', getattr(settings, 'AWS_REGION', 'us-east-1'))
        bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)

        s3_client = boto3.client(
            's3', aws_access_key_id=chave_acesso, aws_secret_access_key=chave_secreta, region_name=regiao
        )

        presigned_post = s3_client.generate_presigned_post(
            Bucket=bucket,
            Key=caminho_s3_real, # Vai para a Amazon COM o prefixo
            Fields={"Content-Type": tipo_arquivo},
            Conditions=[{"Content-Type": tipo_arquivo}],
            ExpiresIn=3600
        )
        
        # Devolvemos a URL da AWS e também o caminho curto para o JS guardar!
        return JsonResponse({
            'presigned_post': presigned_post,
            'caminho_relativo_db': caminho_relativo 
        })

    except Exception as e:
        return JsonResponse({'erro': f'Erro interno: {str(e)}'}, status=500)


@login_required
@require_POST
def salvar_paginas_em_massa(request):
    """ Recebe a lista de caminhos do JS e cria as páginas no PostgreSQL """
    dados = json.loads(request.body)
    livro_id = dados.get('livro_id')
    arquivos_enviados = dados.get('arquivos') # Lista de caminhos relativos
    
    livro = get_object_or_404(Livro, id=livro_id)
    
    # Descobre qual é a última página atual para continuar a numeração
    ultima_pagina = livro.paginas.order_by('numero').last()
    proximo_numero = ultima_pagina.numero + 1 if ultima_pagina else 1
    
    paginas_para_salvar = []
    
    # Cria os objetos na memória
    for caminho in arquivos_enviados:
        paginas_para_salvar.append(Pagina(
            livro=livro,
            numero=proximo_numero,
            imagem_original=caminho # Passamos a string limpa direto para o ImageField!
        ))
        proximo_numero += 1
        
    # Salva todos de uma vezada só no PostgreSQL (Ultra rápido)
    Pagina.objects.bulk_create(paginas_para_salvar)
    
    return JsonResponse({'status': 'sucesso', 'total_salvas': len(paginas_para_salvar)})

from .models import EstatisticasUsuario, SessaoJogo
from django.utils import timezone
import datetime

@login_required
@require_POST
def api_salvar_sessao_jogo(request):
    try:
        dados = json.loads(request.body)
        jogo_id = dados.get('jogo_id')
        tempo_jogo = float(dados.get('tempo_jogo', 0))
        
        # A pontuação vai até 10 pontos por chamada
        pontuacao_recebida = float(dados.get('score', dados.get('pontuacao', 0)))
        pontuacao_sessao = min(pontuacao_recebida, 10.0)
        
        rubrica_enviada = dados.get('rubrica', '')

        jogo = get_object_or_404(Jogo, id=jogo_id)
        
        habilidades_recebidas = dados.get('habilidades', [])
        # Tratamento caso o frontend envie como dicionário (retrocompatibilidade)
        if isinstance(habilidades_recebidas, dict):
            habilidades_recebidas = list(habilidades_recebidas.keys())

        # Verifica se as habilidades recebidas já estão listadas no jogo e, se não, adiciona
        from .models import HabilidadeBNCC
        for codigo_hab in habilidades_recebidas:
            if not jogo.habilidades_relacionadas.filter(codigo=codigo_hab).exists():
                hab_obj = HabilidadeBNCC.objects.filter(codigo=codigo_hab).first()
                if hab_obj:
                    jogo.habilidades_relacionadas.add(hab_obj)
        
        sessao, created = SessaoJogo.objects.get_or_create(
            user=request.user,
            jogo=jogo,
            defaults={
                'pontuacao': pontuacao_sessao,
                'tempo_jogo': tempo_jogo,
                'rubrica': rubrica_enviada
            }
        )

        if not created:
            sessao.pontuacao += pontuacao_sessao
            sessao.tempo_jogo += tempo_jogo
            sessao.rubrica = rubrica_enviada
            
            if sessao.pontuacao > sessao.recorde_pontuacao:
                sessao.recorde_pontuacao = sessao.pontuacao
            sessao.save()
        else:
            sessao.recorde_pontuacao = pontuacao_sessao
            sessao.save()
        # Atualiza as habilidades na Sessão do Jogo
        for codigo_hab in habilidades_recebidas:
            hab_obj = HabilidadeBNCC.objects.filter(codigo=codigo_hab).first()
            if hab_obj:
                sessao.habilidades_conquistadas.add(hab_obj)

        estatisticas, created_est = EstatisticasUsuario.objects.get_or_create(user=request.user)
        
        # Soma pontuação eterna
        estatisticas.pontuacao_eterna += pontuacao_sessao

        hoje = timezone.localdate()
        if estatisticas.ultima_jogada != hoje:
            if estatisticas.ultima_jogada == hoje - datetime.timedelta(days=1):
                estatisticas.dias_ofensiva += 1
            else:
                estatisticas.dias_ofensiva = 1
            if estatisticas.dias_ofensiva > estatisticas.maior_ofensiva:
                estatisticas.maior_ofensiva = estatisticas.dias_ofensiva
            estatisticas.ultima_jogada = hoje

        # Atualiza Estatística de Habilidade do Usuário (só carimba a habilidade)
        for codigo_hab in habilidades_recebidas:
            hab_obj = HabilidadeBNCC.objects.filter(codigo=codigo_hab).first()
            if hab_obj:
                estatisticas.habilidades_conquistadas.add(hab_obj)

        # Atualiza a pontuação geral com base na eterna
        estatisticas.pontuacao_geral = estatisticas.pontuacao_eterna
        estatisticas.save()

        return JsonResponse({'status': 'sucesso'})
    except Exception as e:
        return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)


@login_required
def estatisticas_view(request):
    estatisticas, created = EstatisticasUsuario.objects.get_or_create(user=request.user)
    sessoes = request.user.sessoes_jogos.all().order_by('-atualizado_em')
    
    # Ranking
    ranking = EstatisticasUsuario.objects.filter(pontuacao_geral__gt=estatisticas.pontuacao_geral).count() + 1
    
    # Busca o ano do aluno
    ano_usuario = None
    turma_aluno = request.user.turmas.filter(ano_escolar__isnull=False).first()
    if turma_aluno:
        ano_usuario = turma_aluno.ano_escolar

    from .models import HabilidadeBNCC
    # Pega todas as habilidades daquele ano e mostra se o aluno as conquistou
    habilidades_ano = []
    if ano_usuario:
        habilidades_db = HabilidadeBNCC.objects.filter(anos_escolares=ano_usuario).order_by('codigo')
        
        habilidades_conquistadas_ids = estatisticas.habilidades_conquistadas.values_list('id', flat=True)
        
        for hab in habilidades_db:
            conquistou = hab.id in habilidades_conquistadas_ids
            habilidades_ano.append({
                'codigo': hab.codigo,
                'descricao': hab.descricao,
                'pontuacao': 100 if conquistou else 0 # Mock visual para o template que esperava pontuação
            })
            
    sessoes_aulas = request.user.sessoes_aulas_interativas_novo.all().order_by('-atualizado_em')
    
    context = {
        'estatisticas': estatisticas,
        'sessoes': sessoes,
        'sessoes_aulas': sessoes_aulas,
        'habilidades_ano': habilidades_ano,
        'ano_usuario': ano_usuario,
        'ranking': ranking,
    }
    return render(request, 'core/estatisticas.html', context)



@login_required
def relatorios_desempenho_view(request):
    if request.user.tipo not in ['PROFESSOR', 'GESTOR_LOCAL', 'GESTOR_GERAL', 'ADMIN']:
        return redirect('home')
        
    # Inicialmente simples, carregando turmas do usuário
    if request.user.tipo == 'PROFESSOR':
        turmas = request.user.turmas.all()
    elif request.user.tipo == 'GESTOR_LOCAL':
        turmas = Turma.objects.filter(escola__in=request.user.escolas.all())
    else:
        turmas = Turma.objects.all()
        
    # Para cada turma, podemos calcular estatísticas básicas
    # Como as estatísticas são complexas, passamos as turmas para o template
    # Opcionalmente, processamos estatísticas por turma aqui.
    
    turmas_stats = []
    for turma in turmas:
        alunos = User.objects.filter(turmas=turma, tipo='ALUNO')
        total_alunos = alunos.count()
        pontuacao_media = 0
        
        if total_alunos > 0:
            estatisticas_alunos = EstatisticasUsuario.objects.filter(user__in=alunos)
            total_pontos = sum(e.pontuacao_geral for e in estatisticas_alunos)
            pontuacao_media = total_pontos / total_alunos
            
        turmas_stats.append({
            'turma': turma,
            'total_alunos': total_alunos,
            'pontuacao_media': pontuacao_media
        })
        
    context = {
        'turmas_stats': turmas_stats
    }
    return render(request, 'core/relatorios_desempenho.html', context)



from django.db.models import Q

@login_required
def bncc_list_view(request):
    if request.user.tipo not in ['PROFESSOR', 'GESTOR_LOCAL', 'GESTOR_REGIONAL', 'GESTOR_KAIZO', 'ADMIN']:
        return redirect('home')
        
    query = request.GET.get('q', '')
    from .models import HabilidadeBNCC
    
    if query:
        habilidades = HabilidadeBNCC.objects.filter(
            Q(codigo__icontains=query) | 
            Q(descricao__icontains=query) |
            Q(anos_escolares__nome__icontains=query)
        ).distinct().order_by('codigo')
    else:
        habilidades = HabilidadeBNCC.objects.all().order_by('codigo')
    
    context = {
        'habilidades': habilidades,
        'query': query,
    }
    return render(request, 'core/bncc_list.html', context)

@login_required
def bncc_detail_view(request, bncc_id):
    if request.user.tipo not in ['PROFESSOR', 'GESTOR_LOCAL', 'GESTOR_REGIONAL', 'GESTOR_KAIZO', 'ADMIN']:
        return redirect('home')
        
    from .models import HabilidadeBNCC
    habilidade = get_object_or_404(HabilidadeBNCC, id=bncc_id)
    return render(request, 'core/bncc_detail.html', {'habilidade': habilidade})
