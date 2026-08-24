from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.core.cache import cache
from django.core.files.storage import default_storage
from .models import Livro, Pagina, User, VideoAula, Turma, TokenCadastro, SessaoChat, Mensagem, Jogo, EstatisticasUsuario, RegistroAcessoDemo, SessaoJogo, SessaoLivroInterativo
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
def detalhes_aluno_view(request, aluno_id):
    user = request.user
    
    if user.tipo == 'ALUNO':
        return redirect('estante')
        
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
    estatisticas, _ = EstatisticasUsuario.objects.get_or_create(user=aluno)
    sessoes_jogos = SessaoJogo.objects.filter(user=aluno).order_by('-atualizado_em')[:50]
    sessoes_livros = SessaoLivroInterativo.objects.filter(user=aluno).order_by('-atualizado_em')[:50]
    
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
                
    sessoes_l_all = SessaoLivroInterativo.objects.filter(user=aluno).select_related('livro').prefetch_related('livro__habilidades_relacionadas')
    for sl in sessoes_l_all:
        minutos = sl.tempo_gasto / 60.0 if sl.tempo_gasto else 0
        if minutos > 0:
            for h in sl.livro.habilidades_relacionadas.all():
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
def livros_interativos_list_view(request):
    user = request.user
    query = request.GET.get('q', '')
    
    livros = Livro.objects.filter(formato='INTERATIVO').order_by('titulo')
    
    if user.tipo == 'ALUNO':
        # Busca a turma do aluno para saber o ano escolar atual
        turma = user.turmas.first()
        ano_atual = turma.ano_escolar if (turma and turma.ano_escolar) else None
        
        from django.db.models import Q
        if ano_atual:
            livros = livros.filter(Q(anos_escolares__isnull=True) | Q(anos_escolares__ordem__lte=ano_atual.ordem)).distinct()
        else:
            livros = livros.filter(anos_escolares__isnull=True)
            
        livros = livros.filter(is_versao_professor=False, is_demo=False)
        
    elif user.tipo == 'DEMO':
        livros = livros.filter(is_demo=True)
        
    if query:
        livros = livros.filter(titulo__icontains=query)
        
    estatisticas, _ = EstatisticasUsuario.objects.get_or_create(user=request.user)
    ranking = EstatisticasUsuario.objects.filter(pontuacao_geral__gt=estatisticas.pontuacao_geral).count() + 1
        
    return render(request, 'core/livros_interativos_list.html', {
        'livros': livros, 
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
            
    sessoes_livros = request.user.sessoes_livros_interativos.all().order_by('-atualizado_em')
    
    context = {
        'estatisticas': estatisticas,
        'sessoes': sessoes,
        'sessoes_livros': sessoes_livros,
        'habilidades_ano': habilidades_ano,
        'ano_usuario': ano_usuario,
        'ranking': ranking,
    }
    return render(request, 'core/estatisticas.html', context)


from .models import SessaoLivroInterativo

@login_required
def ler_livro_interativo_view(request, livro_id):
    livro = get_object_or_404(Livro, id=livro_id, formato='INTERATIVO')
    return render(request, 'core/ler_livro_interativo.html', {'livro': livro})


@login_required
@require_POST
def api_salvar_progresso_livro(request):
    try:
        dados = json.loads(request.body)
        livro_id = dados.get('livro_id')
        
        livro = get_object_or_404(Livro, id=livro_id, formato='INTERATIVO')
        
        # A pontuação vai até 150 pontos por chamada
        pontuacao_recebida = float(dados.get('pontuacao', dados.get('score', 0.0)))
        pontuacao_sessao = min(pontuacao_recebida, 150.0)
        
        rubrica_enviada = dados.get('rubrica', '')
        
        habilidades_recebidas = dados.get('habilidades', [])
        # Tratamento caso o frontend envie como dicionário (retrocompatibilidade)
        if isinstance(habilidades_recebidas, dict):
            habilidades_recebidas = list(habilidades_recebidas.keys())

        # Verifica se as habilidades recebidas já estão listadas no livro e, se não, adiciona
        from .models import HabilidadeBNCC
        for codigo_hab in habilidades_recebidas:
            if not livro.habilidades_relacionadas.filter(codigo=codigo_hab).exists():
                hab_obj = HabilidadeBNCC.objects.filter(codigo=codigo_hab).first()
                if hab_obj:
                    livro.habilidades_relacionadas.add(hab_obj)

        sessao, created = SessaoLivroInterativo.objects.get_or_create(
            user=request.user,
            livro=livro,
            defaults={
                'respostas_atividades': dados.get('answers', {}),
                'tentativas_atividades': dados.get('attempts', {}),
                'pontuacao': pontuacao_sessao,
                'tempo_gasto': float(dados.get('time', 0)),
                'rubrica': rubrica_enviada
            }
        )

        if not created:
            # Mescla as respostas
            respostas_atuais = sessao.respostas_atividades or {}
            respostas_novas = dados.get('answers', {})
            respostas_atuais.update(respostas_novas)
            sessao.respostas_atividades = respostas_atuais
            
            # Mescla as tentativas
            tentativas_atuais = sessao.tentativas_atividades or {}
            tentativas_novas = dados.get('attempts', {})
            for k, v in tentativas_novas.items():
                tentativas_atuais[k] = tentativas_atuais.get(k, 0) + v
            sessao.tentativas_atividades = tentativas_atuais
            
            sessao.tempo_gasto += float(dados.get('time', 0))
            sessao.rubrica = rubrica_enviada
                
            # Pontuação é sobrescrita apenas se for maior
            if pontuacao_sessao > sessao.pontuacao:
                diferenca = pontuacao_sessao - sessao.pontuacao
                sessao.pontuacao = pontuacao_sessao
                
                if sessao.pontuacao > sessao.recorde_pontuacao:
                    sessao.recorde_pontuacao = sessao.pontuacao
                    
                # Soma pontuação eterna (apenas a diferença para não duplicar)
                estatisticas, _ = EstatisticasUsuario.objects.get_or_create(user=request.user)
                estatisticas.pontuacao_eterna += diferenca
                estatisticas.save()
                
            sessao.save()
            
        else:
            sessao.recorde_pontuacao = sessao.pontuacao
            sessao.save()
            estatisticas, _ = EstatisticasUsuario.objects.get_or_create(user=request.user)
            estatisticas.pontuacao_eterna += sessao.pontuacao
            estatisticas.save()
            
        estatisticas, _ = EstatisticasUsuario.objects.get_or_create(user=request.user)

        # Atualiza a pontuação por habilidade (só carimba no M2M)
        for codigo_hab in habilidades_recebidas:
            hab_obj = HabilidadeBNCC.objects.filter(codigo=codigo_hab).first()
            if hab_obj:
                sessao.habilidades_conquistadas.add(hab_obj)
                estatisticas.habilidades_conquistadas.add(hab_obj)
            
        return JsonResponse({'status': 'sucesso'})
    except Exception as e:
        return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)


@login_required
def api_carregar_progresso_livro(request, livro_id):
    livro = get_object_or_404(Livro, id=livro_id, formato='INTERATIVO')
    sessao = SessaoLivroInterativo.objects.filter(user=request.user, livro=livro).first()
    
    if sessao:
        progress = {
            'answers': sessao.respostas_atividades,
            'attempts': sessao.tentativas_atividades,
            'time': sessao.tempo_gasto
        }
    else:
        progress = {
            'page': 1, 'answers': {}, 'attempts': {}, 'time': 0
        }
        
    return JsonResponse({'status': 'sucesso', 'progress': progress})


@login_required
def relatorios_desempenho_view(request):
    if request.user.tipo not in ['PROFESSOR', 'GESTOR_LOCAL', 'GESTOR_GERAL', 'ADMIN']:
        return redirect('estante')
        
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


@login_required
def api_salvar_livro_interativo(request):
    if not (request.user.is_superuser or request.user.is_staff or getattr(request.user, 'tipo', '') in ['GESTOR_GERAL', 'ADMIN']):
        return JsonResponse({'erro': 'Sem permissão.'}, status=403)

    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            livro = Livro.objects.create(
                titulo=dados.get('titulo'),
                descricao=dados.get('descricao', ''),
                caminho_s3=f"jogos_web/{dados.get('pasta_s3')}",
                formato='INTERATIVO',
                rubricas_atividades=dados.get('rubricas', {})
            )
            
            anos_ids = dados.get('anos_escolares', [])
            if anos_ids:
                livro.anos_escolares.set(anos_ids)
            
            # Constrói o modelo relacional para performance em relatórios
            from .models import AtividadeLivro, RubricaAlternativa
            rubricas_json = dados.get('rubricas', {})
            for key_atividade, alternativas in rubricas_json.items():
                if key_atividade.startswith('Atividade_'):
                    try:
                        num = int(key_atividade.split('_')[1])
                        atividade = AtividadeLivro.objects.create(livro=livro, numero=num)
                        
                        rubricas_para_salvar = []
                        for alt, texto in alternativas.items():
                            rubricas_para_salvar.append(RubricaAlternativa(
                                atividade=atividade,
                                alternativa=alt,
                                texto_rubrica=texto
                            ))
                        RubricaAlternativa.objects.bulk_create(rubricas_para_salvar)
                    except ValueError:
                        pass
                        
            # Associa as habilidades selecionadas
            habilidades_ids = dados.get('habilidades', [])
            if habilidades_ids:
                livro.habilidades_relacionadas.set(habilidades_ids)
                
            return JsonResponse({'status': 'sucesso', 'livro_id': livro.id})
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)
    return JsonResponse({'status': 'metodo_invalido'}, status=405)


from django.db.models import Q

@login_required
def bncc_list_view(request):
    if request.user.tipo not in ['PROFESSOR', 'GESTOR_LOCAL', 'GESTOR_REGIONAL', 'GESTOR_KAIZO', 'ADMIN']:
        return redirect('estante')
        
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
        return redirect('estante')
        
    from .models import HabilidadeBNCC
    habilidade = get_object_or_404(HabilidadeBNCC, id=bncc_id)
    return render(request, 'core/bncc_detail.html', {'habilidade': habilidade})

@staff_member_required
def upload_ferramentas_view(request):
    # Essa view só pode ser acessada por quem tem o is_staff=True (quem acessa o admin)
    return render(request, 'core/upload_ferramentas.html')

@login_required
def salvar_registro_ferramenta(request):
    """ Chamado pelo JS após terminar o upload de todos os arquivos """
    if request.method == 'POST':
        import json
        dados = json.loads(request.body)
        
        # Cria o registro no banco de dados
        from .models import Ferramenta
        ferramenta = Ferramenta.objects.create(
            nome=dados.get('nome'),
            descricao=dados.get('descricao'),
            caminho_s3=f"ferramentas_web/{dados.get('pasta_ferramenta')}"
        )
            
        return JsonResponse({'status': 'sucesso', 'ferramenta_id': ferramenta.id})

@login_required
def ferramenta_view(request, ferramenta_id):
    from .models import Ferramenta
    ferramenta = get_object_or_404(Ferramenta, id=ferramenta_id, ativo=True)
    return render(request, 'core/ferramenta.html', {'ferramenta': ferramenta})
