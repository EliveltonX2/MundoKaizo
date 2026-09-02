import json
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import Jogo, SessaoJogo
from core.models import EstatisticasUsuario, HabilidadeBNCC

@login_required
def jogos_list_view(request):
    query = request.GET.get('q', '')
    jogos = Jogo.objects.filter(ativo=True).order_by('-criado_em')
    
    if request.user.tipo == 'ALUNO':
        turma = request.user.turmas.first()
        if turma and turma.ano_escolar:
            jogos = jogos.filter(anos_escolares=turma.ano_escolar)
    
    if query:
        jogos = jogos.filter(titulo__icontains=query)
        
    estatisticas, created = EstatisticasUsuario.objects.get_or_create(user=request.user)
    ranking = EstatisticasUsuario.objects.filter(pontuacao_geral__gt=estatisticas.pontuacao_geral).count() + 1
        
    return render(request, 'jogos/jogos_list.html', {
        'jogos': jogos, 
        'query': query,
        'estatisticas': estatisticas,
        'ranking': ranking
    })


@login_required
def jogar_view(request, jogo_id):
    jogo = get_object_or_404(Jogo, id=jogo_id, ativo=True)
    return render(request, 'jogos/jogar.html', {'jogo': jogo})


@login_required
@require_POST
def api_salvar_jogo(request):
    if not request.user.is_staff:
        return JsonResponse({'status': 'erro', 'mensagem': 'Acesso negado.'}, status=403)
        
    try:
        dados = json.loads(request.body)
        jogo = Jogo.objects.create(
            titulo=dados.get('titulo'),
            descricao=dados.get('descricao'),
            caminho_s3=f"jogos_web/jogo_{dados.get('pasta_jogo')}"
        )
        
        # Associa as habilidades selecionadas
        habilidades_ids = dados.get('habilidades', [])
        if habilidades_ids:
            jogo.habilidades_relacionadas.set(habilidades_ids)
            
        return JsonResponse({'status': 'sucesso', 'jogo_id': jogo.id})
    except Exception as e:
        return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)


@login_required
@require_POST
def api_salvar_sessao(request):
    try:
        dados = json.loads(request.body)
        jogo_id = dados.get('jogo_id')
        tempo_jogo = float(dados.get('tempo_jogo', 0))
        
        pontuacao_recebida = float(dados.get('pontuacao', dados.get('score', 0.0)))
        
        rubrica_enviada = dados.get('rubrica', '')
        habilidades_recebidas = dados.get('habilidades', [])
        if isinstance(habilidades_recebidas, dict):
            habilidades_recebidas = list(habilidades_recebidas.keys())
            
        jogo = get_object_or_404(Jogo, id=jogo_id)
        
        for codigo_hab in habilidades_recebidas:
            if not jogo.habilidades_relacionadas.filter(codigo=codigo_hab).exists():
                hab_obj = HabilidadeBNCC.objects.filter(codigo=codigo_hab).first()
                if hab_obj:
                    jogo.habilidades_relacionadas.add(hab_obj)

        sessao, created = SessaoJogo.objects.get_or_create(
            user=request.user,
            jogo=jogo,
            defaults={
                'pontuacao': pontuacao_recebida,
                'tempo_jogo': tempo_jogo,
                'rubrica': rubrica_enviada
            }
        )

        estatisticas, _ = EstatisticasUsuario.objects.get_or_create(user=request.user)

        if not created:
            sessao.tempo_jogo += tempo_jogo
            sessao.rubrica = rubrica_enviada
            
            if pontuacao_recebida > sessao.pontuacao:
                diferenca = pontuacao_recebida - sessao.pontuacao
                sessao.pontuacao = pontuacao_recebida
                
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
def api_carregar_progresso(request, jogo_id):
    jogo = get_object_or_404(Jogo, id=jogo_id)
    sessao = SessaoJogo.objects.filter(user=request.user, jogo=jogo).first()
    
    if sessao:
        progress = {
            'time': sessao.tempo_jogo,
            'pontuacao': sessao.pontuacao,
            'recorde_pontuacao': sessao.recorde_pontuacao
        }
    else:
        progress = {
            'time': 0, 'pontuacao': 0, 'recorde_pontuacao': 0
        }
        
    return JsonResponse({'status': 'sucesso', 'progress': progress})
