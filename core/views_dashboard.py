import csv
import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Avg, Sum, Count, F, ExpressionWrapper, fields
from django.utils import timezone
from datetime import timedelta
from core.models import User, Turma, Escola, Cidade, Estado, Pais, EstatisticasUsuario, SessaoJogo, RegistroAcessoDemo

@login_required
# ==============================================================
# NOVA VIEW DE GERENCIAMENTO (Antigo Relatórios Unificados)
# ==============================================================
@login_required
def relatorios_avancados_view(request):
    tipo = request.user.tipo
    
    # Restringe acesso apenas para Professores e Gestores
    if tipo not in ['PROFESSOR', 'GESTOR_LOCAL', 'GESTOR_REGIONAL', 'GESTOR_KAIZO', 'ADMIN'] and not request.user.is_superuser:
        return redirect('estante')
        
    turmas_base = Turma.objects.all()
    escolas_base = Escola.objects.all()
    cidades_base = Cidade.objects.all()
    estados_base = Estado.objects.all()
    
    # Restringe opções de filtro baseado no papel (Role-Based Access Control)
    if tipo == 'PROFESSOR':
        turmas_base = turmas_base.filter(id__in=request.user.turmas.values_list('id', flat=True))
        escolas_base = escolas_base.filter(turma__in=turmas_base).distinct()
        cidades_base = Cidade.objects.none()
        estados_base = Estado.objects.none()
    elif tipo == 'GESTOR_LOCAL':
        escolas_base = escolas_base.filter(id__in=request.user.escolas.values_list('id', flat=True))
        turmas_base = turmas_base.filter(escola__in=escolas_base)
        cidades_base = Cidade.objects.none()
        estados_base = Estado.objects.none()
    elif tipo == 'GESTOR_REGIONAL':
        cidades_base = cidades_base.filter(id__in=request.user.cidades_gestao.values_list('id', flat=True))
        estados_base = estados_base.filter(id__in=request.user.estados_gestao.values_list('id', flat=True))
        escolas_base = escolas_base.filter(cidade__in=cidades_base)
        turmas_base = turmas_base.filter(escola__in=escolas_base)

    # Pegando filtros aplicados via GET form
    sel_estado = request.GET.get('estado')
    sel_cidade = request.GET.get('cidade')
    sel_escola = request.GET.get('escola')
    sel_turma = request.GET.get('turma')
    
    # Filtrando hierarquicamente para baixo
    if sel_estado:
        cidades_base = cidades_base.filter(estado_id=sel_estado)
        escolas_base = escolas_base.filter(cidade__estado_id=sel_estado)
        turmas_base = turmas_base.filter(escola__cidade__estado_id=sel_estado)
    if sel_cidade:
        escolas_base = escolas_base.filter(cidade_id=sel_cidade)
        turmas_base = turmas_base.filter(escola__cidade_id=sel_cidade)
    if sel_escola:
        turmas_base = turmas_base.filter(escola_id=sel_escola)
    if sel_turma:
        turmas_base = turmas_base.filter(id=sel_turma)
        
    alunos = User.objects.filter(tipo='ALUNO', turmas__in=turmas_base).distinct()
    total_alunos = alunos.count()
    
    # Agregação de Estatísticas
    stats = EstatisticasUsuario.objects.filter(user__in=alunos)
    media_eterna = stats.aggregate(Avg('pontuacao_eterna'))['pontuacao_eterna__avg'] or 0.0
    

    
    # 1. Tempo Médio de Acesso
    ag = RegistroAcessoDemo.objects.filter(user__in=alunos).aggregate(
        avg_time=Avg(ExpressionWrapper(F('ultima_atividade') - F('data_login'), output_field=fields.DurationField()))
    )
    tempo_medio_minutos = (ag['avg_time'].total_seconds() / 60.0) if ag['avg_time'] else 0.0
    
    # 2. Engajamento (Ativos 30 dias)
    trinta_dias_atras = timezone.now() - timedelta(days=30)
    alunos_ativos = RegistroAcessoDemo.objects.filter(user__in=alunos, data_login__gte=trinta_dias_atras).values('user_id').distinct().count()
    alunos_inativos = total_alunos - alunos_ativos
    
    # 3. Habilidades BNCC (Agrupadas Jogos vs Livros)
    tempo_hab_jogos = {}
    tempo_hab_livros = {}
    
    sessoes_jogos = SessaoJogo.objects.filter(user__in=alunos).select_related('jogo').prefetch_related('jogo__habilidades_relacionadas')
    for sj in sessoes_jogos:
        minutos = sj.tempo_jogo / 60.0 if sj.tempo_jogo else 0
        if minutos > 0:
            for h in sj.jogo.habilidades_relacionadas.all():
                tempo_hab_jogos[h.codigo] = tempo_hab_jogos.get(h.codigo, 0) + minutos
                
    from livros_interativos.models import SessaoAulaInterativa
    sessoes_livros = SessaoAulaInterativa.objects.filter(user__in=alunos).select_related('aula').prefetch_related('aula__habilidades_relacionadas')
    for sl in sessoes_livros:
        minutos = sl.tempo_gasto / 60.0 if sl.tempo_gasto else 0
        if minutos > 0:
            for h in sl.aula.habilidades_relacionadas.all():
                tempo_hab_livros[h.codigo] = tempo_hab_livros.get(h.codigo, 0) + minutos
                
    todas_habs = set(tempo_hab_jogos.keys()).union(set(tempo_hab_livros.keys()))
    hab_ordenada = sorted(
        [(h, (tempo_hab_jogos.get(h, 0) + tempo_hab_livros.get(h, 0)) / (total_alunos if total_alunos > 0 else 1)) for h in todas_habs],
        key=lambda x: x[1], reverse=True)[:6]
        
    labels_hab = [h[0] for h in hab_ordenada]
    data_jogos_hab = [round(tempo_hab_jogos.get(h[0], 0) / (total_alunos if total_alunos > 0 else 1), 1) for h in hab_ordenada]
    data_livros_hab = [round(tempo_hab_livros.get(h[0], 0) / (total_alunos if total_alunos > 0 else 1), 1) for h in hab_ordenada]


    # 4 & 5. Heatmap (30d) e Gráfico (7d)
    hoje = timezone.now().date()
    dias_30 = [hoje - timedelta(days=i) for i in range(29, -1, -1)]
    dias_7 = [hoje - timedelta(days=i) for i in range(6, -1, -1)]
    
    acessos_30d = RegistroAcessoDemo.objects.filter(user__in=alunos, data_login__gte=trinta_dias_atras)
    
    acessos_por_dia = {}
    tempo_por_dia = {}
    
    for a in acessos_30d:
        d = a.data_login.date()
        acessos_por_dia[d] = acessos_por_dia.get(d, 0) + 1
        tempo_por_dia[d] = tempo_por_dia.get(d, 0) + a.tempo_navegacao_minutos
        
    max_acessos = max(acessos_por_dia.values()) if acessos_por_dia else 1
    
    mapa_30dias = []
    for d in dias_30:
        total_dia = acessos_por_dia.get(d, 0)
        intensidade = (total_dia / max_acessos) if max_acessos > 0 else 0
        intensidade_val = round(min(max(intensidade, 0.2), 1.0), 2) if total_dia > 0 else 0
        mapa_30dias.append({
            'data': d.strftime("%d/%m"),
            'total': total_dia,
            'intensidade': str(intensidade_val).replace(',', '.')
        })
        
    labels_7d = [d.strftime("%d/%m") for d in dias_7]
    data_7d = []
    for d in dias_7:
        if acessos_por_dia.get(d, 0) > 0:
            data_7d.append(round(tempo_por_dia.get(d, 0) / acessos_por_dia.get(d, 1), 1))
        else:
            data_7d.append(0)

    context = {
        'estados': estados_base,
        'cidades': cidades_base,
        'escolas': escolas_base,
        'turmas': turmas_base,
        'sel_estado': int(sel_estado) if sel_estado else '',
        'sel_cidade': int(sel_cidade) if sel_cidade else '',
        'sel_escola': int(sel_escola) if sel_escola else '',
        'sel_turma': int(sel_turma) if sel_turma else '',
        'total_alunos': total_alunos,
        'media_eterna': round(media_eterna, 1),
        'tempo_medio_minutos': round(tempo_medio_minutos, 1),
        'alunos_ativos': alunos_ativos,
        'alunos_inativos': alunos_inativos,
        'taxa_engajamento': round((alunos_ativos / total_alunos * 100) if total_alunos > 0 else 0, 1),
        'labels_hab': json.dumps(labels_hab),
        'data_jogos_hab': json.dumps(data_jogos_hab),
        'data_livros_hab': json.dumps(data_livros_hab),
        'mapa_30dias': mapa_30dias,
        'labels_7d': json.dumps(labels_7d),
        'data_7d': json.dumps(data_7d),
        'alunos_list': alunos[:50] # Top 50 para tabela de exemplo
    }
    
    # Renderiza na página mestre
    return render(request, 'dashboards/dashboard_master.html', context)
    
@login_required
def exportar_csv_dashboard(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="relatorio_mundokaizo.csv"'
    writer = csv.writer(response)
    
    tipo = request.user.tipo
    
    # Lógica unificada para CSV export: exporta o que o usuário gerencia.
    turmas_base = Turma.objects.all()
    if tipo == 'PROFESSOR':
        turmas_base = turmas_base.filter(id__in=request.user.turmas.values_list('id', flat=True))
    elif tipo == 'GESTOR_LOCAL':
        turmas_base = turmas_base.filter(escola__in=request.user.escolas.values_list('id', flat=True))
    elif tipo == 'GESTOR_REGIONAL':
        turmas_base = turmas_base.filter(escola__cidade__in=request.user.cidades_gestao.values_list('id', flat=True))
    elif tipo in ['GESTOR_KAIZO', 'ADMIN'] or request.user.is_superuser:
        pass
    else:
        writer.writerow(['Sem Permissao'])
        return response

    alunos = User.objects.filter(tipo='ALUNO', turmas__in=turmas_base).distinct()
    
    writer.writerow(['Nome Aluno', 'Usuario', 'Turma', 'Escola', 'Pontuacao Geral', 'Pontuacao Eterna', 'Dias Ofensiva'])
    for aluno in alunos:
        stats = getattr(aluno, 'estatisticas', None)
        pts = stats.pontuacao_geral if stats else 0
        eterna = stats.pontuacao_eterna if stats else 0
        ofs = stats.dias_ofensiva if stats else 0
        
        turma_obj = aluno.turmas.first()
        turma_nome = turma_obj.nome if turma_obj else 'Sem Turma'
        escola_nome = turma_obj.escola.nome if turma_obj else 'Sem Escola'
        
        writer.writerow([aluno.get_full_name() or aluno.username, aluno.username, turma_nome, escola_nome, pts, eterna, ofs])
        
    return response
