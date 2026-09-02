import json
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import Colecao, Livro, Capitulo, AulaInterativa, SessaoAulaInterativa
from core.models import EstatisticasUsuario, HabilidadeBNCC
from django.db.models import Prefetch

@login_required
def aulas_list_view(request):
    user = request.user
    query = request.GET.get('q', '')
    
    aulas_qs = AulaInterativa.objects.filter(ativo=True).order_by('numero_aula')
    capitulos_qs = Capitulo.objects.filter(ativo=True).prefetch_related(Prefetch('aulas', queryset=aulas_qs)).order_by('numero')
    livros_qs = Livro.objects.filter(ativo=True).prefetch_related(Prefetch('capitulos', queryset=capitulos_qs)).order_by('volume', 'titulo')
    
    ano_atual_id = None
    if user.tipo == 'ALUNO':
        turma = user.turmas.first()
        if turma and turma.ano_escolar:
            ano_atual_id = turma.ano_escolar.id
            aulas_qs = aulas_qs.filter(anos_escolares=turma.ano_escolar)
    
    if query:
        aulas_qs = aulas_qs.filter(titulo__icontains=query)

    colecoes = Colecao.objects.filter(ativo=True).prefetch_related(
        Prefetch('livros', queryset=livros_qs)
    ).order_by('ordem', 'nome')
    
    # Prepara sessoes para exibir progresso
    sessoes_dict = {s.aula_id: s for s in SessaoAulaInterativa.objects.filter(user=user)}
    
    for colecao in colecoes:
        for livro in colecao.livros.all():
            for capitulo in livro.capitulos.all():
                for aula in capitulo.aulas.all():
                    sessao = sessoes_dict.get(aula.id)
                    if sessao:
                        aula.status_progresso = 'completed' if sessao.pontuacao >= 100 else 'in-progress'
                    else:
                        aula.status_progresso = 'not-started'
                
    estatisticas, _ = EstatisticasUsuario.objects.get_or_create(user=request.user)
    ranking = EstatisticasUsuario.objects.filter(pontuacao_geral__gt=estatisticas.pontuacao_geral).count() + 1
        
    return render(request, 'livros_interativos/livros_list.html', {
        'colecoes': colecoes,
        'query': query,
        'estatisticas': estatisticas,
        'ranking': ranking,
        'ano_atual_id': ano_atual_id
    })


@login_required
def ler_aula_view(request, aula_id):
    aula = get_object_or_404(AulaInterativa, id=aula_id, ativo=True)
    return render(request, 'livros_interativos/ler_aula.html', {'aula': aula})


@login_required
@require_POST
def api_salvar_aula(request):
    """ Chamado pelo JS após terminar o upload de todos os arquivos do Admin S3 """
    if not request.user.is_staff:
        return JsonResponse({'status': 'erro', 'mensagem': 'Acesso negado.'}, status=403)
        
    try:
        capitulo_id = request.POST.get('capitulo_id')
        titulo = request.POST.get('titulo')
        numero_aula = request.POST.get('numero_aula')
        pasta_aula = request.POST.get('pasta_aula')
        
        capitulo = get_object_or_404(Capitulo, id=capitulo_id)
        
        aula = AulaInterativa.objects.create(
            capitulo=capitulo,
            titulo=titulo,
            numero_aula=numero_aula,
            caminho_s3=f"livros/{pasta_aula}"
        )
        return JsonResponse({'status': 'sucesso', 'aula_id': aula.id})
    except Exception as e:
        return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)


@login_required
@require_POST
def api_salvar_progresso(request):
    try:
        dados = json.loads(request.body)
        aula_id = dados.get('aula_id')
        
        aula = get_object_or_404(AulaInterativa, id=aula_id)
        
        pontuacao_recebida = float(dados.get('pontuacao', dados.get('score', 0.0)))
        pontuacao_sessao = min(pontuacao_recebida, 150.0)
        
        rubrica_enviada = dados.get('rubrica', '')
        
        habilidades_recebidas = dados.get('habilidades', [])
        if isinstance(habilidades_recebidas, dict):
            habilidades_recebidas = list(habilidades_recebidas.keys())

        for codigo_hab in habilidades_recebidas:
            if not aula.habilidades_bncc.filter(codigo=codigo_hab).exists():
                hab_obj = HabilidadeBNCC.objects.filter(codigo=codigo_hab).first()
                if hab_obj:
                    aula.habilidades_bncc.add(hab_obj)

        sessao, created = SessaoAulaInterativa.objects.get_or_create(
            user=request.user,
            aula=aula,
            defaults={
                'pontuacao': pontuacao_sessao,
                'tempo_gasto': float(dados.get('time', 0)),
                'rubrica': rubrica_enviada
            }
        )

        estatisticas, _ = EstatisticasUsuario.objects.get_or_create(user=request.user)

        if not created:
            sessao.tempo_gasto += float(dados.get('time', 0))
            sessao.rubrica = rubrica_enviada
                
            if pontuacao_sessao > sessao.pontuacao:
                diferenca = pontuacao_sessao - sessao.pontuacao
                sessao.pontuacao = pontuacao_sessao
                
                if sessao.pontuacao > sessao.recorde_pontuacao:
                    sessao.recorde_pontuacao = sessao.pontuacao
                    
                estatisticas.pontuacao_eterna += diferenca
                estatisticas.save()
                
            sessao.save()
            
        else:
            sessao.recorde_pontuacao = sessao.pontuacao
            sessao.save()
            estatisticas.pontuacao_eterna += sessao.pontuacao
            estatisticas.save()

        for codigo_hab in habilidades_recebidas:
            hab_obj = HabilidadeBNCC.objects.filter(codigo=codigo_hab).first()
            if hab_obj:
                sessao.habilidades_conquistadas.add(hab_obj)
                estatisticas.habilidades_conquistadas.add(hab_obj)
            
        return JsonResponse({'status': 'sucesso'})
    except Exception as e:
        return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)


@login_required
def api_carregar_progresso(request, aula_id):
    aula = get_object_or_404(AulaInterativa, id=aula_id)
    sessao = SessaoAulaInterativa.objects.filter(user=request.user, aula=aula).first()
    
    if sessao:
        progress = {
            'time': sessao.tempo_gasto,
            'pontuacao': sessao.pontuacao,
            'recorde_pontuacao': sessao.recorde_pontuacao
        }
    else:
        progress = {
            'time': 0, 'pontuacao': 0, 'recorde_pontuacao': 0
        }
        
    return JsonResponse({'status': 'sucesso', 'progress': progress})
