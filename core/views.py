from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.core.cache import cache
from django.core.files.storage import default_storage
from .models import Livro, Pagina, User, VideoAula, Turma, TokenCadastro, SessaoChat, Mensagem
from .services import adicionar_watermark
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import login
from .forms import *
from .services import enviar_mensagem_para_ia
import json
import markdown


@login_required
def estante_view(request):
    
    user = request.user

    if request.user.tipo == 'DEMO':
        # Filtra SÓ os livros marcados como demonstração
        livros = Livro.objects.filter(is_demo=True)
    
    else:
        user = request.user
        livros = Livro.objects.filter(is_versao_professor=False)
        
        query = request.GET.get('q') # Pega o que foi digitado no input name="q"
        if query:
            livros = livros.filter(titulo__icontains=query) # Filtra pelo título
   
    
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
        return redirect('estante')

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
        return render(request, 'registration/ativar_codigo.html', {'form': form})

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
            return redirect('estante') 
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
    # Apenas Professores ou Gestores podem acessar
    if request.user.tipo not in ['PROFESSOR', 'GESTOR_LOCAL', 'GESTOR_GERAL', 'ADMIN']:
        return redirect('estante')

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
                
            return redirect('vincular_cartoes') # Atualize com o nome da sua URL de gestão
    else:
        form = VincularCartoesForm(professor=request.user)

    return render(request, 'core/vincular_cartoes.html', {'form': form})

@login_required
def criar_turma_view(request):
    # Apenas Gestores e Admins podem criar turmas
    if request.user.tipo not in ['GESTOR_LOCAL', 'ADMIN']:
        messages.error(request, "Você não tem permissão para acessar esta página.")
        return redirect('estante')

    if request.method == 'POST':
        # Passamos o request.user para o form aplicar a trava de segurança
        form = TurmaForm(request.POST, gestor=request.user)
        if form.is_valid():
            turma = form.save()
            messages.success(request, f"A turma '{turma.nome}' foi criada com sucesso na escola {turma.escola.nome}!")
            # Redireciona de volta para a mesma página para ele criar outra se quiser
            return redirect('criar_turma') 
    else:
        form = TurmaForm(gestor=request.user)

    # Pegamos as turmas que já existem nas escolas desse gestor para mostrar numa listinha
    turmas_existentes = Turma.objects.filter(escola__in=request.user.escolas.all()).order_by('escola__nome', 'nome')

    contexto = {
        'form': form,
        'turmas_existentes': turmas_existentes
    }
    return render(request, 'core/criar_turma.html', contexto)



@login_required
def chat_view(request):
    # Pega o ID da sessão da URL (para quando o usuário clica no menu lateral)
    sessao_id = request.GET.get('sessao')

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
            ultimas_mensagens = sessao.mensagens.all().order_by('-criado_em')[:10]
            contexto_texto = ""
            # Inverte a ordem para que o histórico fique cronológico para a IA ler
            for msg in reversed(ultimas_mensagens):
                quem = "Professor" if msg.is_user else "Kai"
                contexto_texto += f"{quem}: {msg.texto}\n"

            # 3. Salva a nova pergunta no banco
            Mensagem.objects.create(sessao=sessao, is_user=True, texto=texto_usuario)

            nome_professor = request.user.first_name if request.user.first_name else request.user.username

            # 4. Envia para a IA passando o contexto do histórico
            resposta_ia_texto = enviar_mensagem_para_ia(texto_usuario, contexto_texto, nome_professor)

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
    
    # Define qual conversa deve ser exibida no meio da tela
    sessao_atual = None
    if sessao_id:
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