from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.core.cache import cache
from django.core.files.storage import default_storage
from .models import Livro, Pagina, User, VideoAula, Turma, TokenCadastro, SessaoChat, Mensagem, Jogo
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
def estante_view(request):
    
    user = request.user
    query = request.GET.get('q')

    if request.user.tipo == 'DEMO':
        # Filtra SÓ os livros marcados como demonstração
        livros = Livro.objects.filter(is_demo=True)

    elif request.user.tipo == 'ALUNO':
        livros = Livro.objects.filter(is_versao_professor=False, is_demo=False)
        #TODO: uma forma de filtrar apenas o livro do ano especifico do aluno.

        
    
    else:
        user = request.user
        livros = Livro.objects.filter(is_versao_professor=False)
        
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

    caminho_s3 = f"jogos_web/{pasta_jogo}/{nome_arquivo}"

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
        return JsonResponse({'status': 'sucesso', 'jogo_id': jogo.id})
    

@staff_member_required
def upload_jogos_view(request):
    # Essa view só pode ser acessada por quem tem o is_staff=True (quem acessa o admin)
    return render(request, 'core/upload_jogos.html')

@login_required
def jogos_list_view(request):
    # Captura o que o usuário digitou na barra de busca (se houver)
    query = request.GET.get('q', '')
    
    # Traz apenas os jogos que estão com a caixinha "Ativo" marcada no painel Admin
    jogos = Jogo.objects.filter(ativo=True).order_by('-criado_em')
    
    if query:
        # Filtra pelo título ignorando maiúsculas/minúsculas (icontains)
        jogos = jogos.filter(titulo__icontains=query)
        
    return render(request, 'core/jogos.html', {'jogos': jogos, 'query': query})

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
        pontuacao = float(dados.get('pontuacao', 0))
        tempo_jogo = float(dados.get('tempo_jogo', 0))
        codigo_habilidade = dados.get('codigo_habilidade', '')

        jogo = get_object_or_404(Jogo, id=jogo_id)
        
        # Cria a sessão do jogo
        SessaoJogo.objects.create(
            user=request.user,
            jogo=jogo,
            pontuacao=pontuacao,
            tempo_jogo=tempo_jogo,
            codigo_habilidade=codigo_habilidade
        )

        # Atualiza ou cria as estatísticas do usuário
        estatisticas, created = EstatisticasUsuario.objects.get_or_create(user=request.user)

        # Atualiza ofensiva de dias
        hoje = timezone.localdate()
        if estatisticas.ultima_jogada != hoje:
            if estatisticas.ultima_jogada == hoje - datetime.timedelta(days=1):
                estatisticas.dias_ofensiva += 1
            else:
                estatisticas.dias_ofensiva = 1
            
            if estatisticas.dias_ofensiva > estatisticas.maior_ofensiva:
                estatisticas.maior_ofensiva = estatisticas.dias_ofensiva
            
            estatisticas.ultima_jogada = hoje

        # Atualiza pontuação por habilidade
        if codigo_habilidade:
            habilidades = estatisticas.pontuacao_habilidades or {}
            # Se já tem pontuação, fazemos uma média simples para não inflacionar infinitamente, ou apenas soma.
            # O mais comum é somar a pontuação de XP, mas como o usuário mencionou "média", 
            # vamos somar as pontuações para compor a geral depois.
            # Vamos assumir que salva a maior pontuação daquela habilidade.
            pontuacao_atual = habilidades.get(codigo_habilidade, 0)
            if pontuacao > pontuacao_atual:
                habilidades[codigo_habilidade] = pontuacao
            estatisticas.pontuacao_habilidades = habilidades

            # Atualiza pontuação geral (média de todas as habilidades jogadas)
            valores = list(habilidades.values())
            if valores:
                estatisticas.pontuacao_geral = sum(valores) / len(valores)

        estatisticas.save()

        return JsonResponse({'status': 'sucesso'})
    except Exception as e:
        return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)


@login_required
def estatisticas_view(request):
    estatisticas, created = EstatisticasUsuario.objects.get_or_create(user=request.user)
    sessoes = request.user.sessoes_jogos.all().order_by('-criado_em')
    
    context = {
        'estatisticas': estatisticas,
        'sessoes': sessoes,
    }
    return render(request, 'core/estatisticas.html', context)