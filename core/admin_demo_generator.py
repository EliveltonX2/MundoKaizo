from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
import random
import datetime
from .models import (
    User, Pais, Estado, Cidade, Escola, Turma, AnoEscolar, 
    Livro, EstatisticasUsuario
)
from jogos.models import Jogo, SessaoJogo

NOME_ANIMAIS = [
    "Naruto", "Sasuke", "Sakura", "Kakashi", "Goku", "Vegeta", "Gohan", "Piccolo", 
    "Luffy", "Zoro", "Nami", "Sanji", "Tanjiro", "Nezuko", "Zenitsu", "Inosuke",
    "Saitama", "Genos", "Tornado", "Midoriya", "Bakugo", "Todoroki", "Uraraka",
    "Eren", "Mikasa", "Armin", "Levi", "Gon", "Killua", "Kurapika", "Leorio",
    "Ichigo", "Rukia", "Renji", "Byakuya", "Edward", "Alphonse", "Roy", "Winry",
    "Asta", "Yuno", "Noelle", "Yami", "Gintoki", "Kagura", "Shinpachi", "Jotaro",
    "Dio", "Josuke", "Giorno", "Jolyne", "Guts", "Griffith", "Casca", "Spike"
]

PREFIXO_MOCK = "[MOCK]"
PREFIXO_USER = "mock_"

def gerar_dados_demo_view(request):
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Sem permissão.")
        return redirect('admin:index')

    if request.method == "POST":
        try:
            # 1. Cria a base Geográfica e Institucional
            pais, _ = Pais.objects.get_or_create(nome=f"{PREFIXO_MOCK} Japão (Anime)")
            estado, _ = Estado.objects.get_or_create(nome=f"{PREFIXO_MOCK} Shonen", sigla="SH", pais=pais)
            cidade, _ = Cidade.objects.get_or_create(nome=f"{PREFIXO_MOCK} Konoha City", estado=estado)
            escola, _ = Escola.objects.get_or_create(nome=f"{PREFIXO_MOCK} Academia Ninja Mundo Kaizo", cidade=cidade)

            # 2. Busca Anos Escolares
            anos_escolares = AnoEscolar.objects.all().order_by('ordem')
            if not anos_escolares.exists():
                messages.error(request, "Erro: Não há Anos Escolares cadastrados no banco.")
                return redirect('admin:gerador_demo_panel')

            jogos = list(Jogo.objects.filter(ativo=True))
            livros = list(Livro.objects.filter(formato='INTERATIVO'))
            
            total_alunos_criados = 0

            # 3. Para cada ano escolar, cria uma turma e alunos
            for ano in anos_escolares[:3]: # Limita a no máximo 3 turmas para evitar timeout
                nome_turma = f"{PREFIXO_MOCK} Turma {ano.nome}"
                turma, _ = Turma.objects.get_or_create(
                    nome=nome_turma, 
                    escola=escola, 
                    ano_escolar=ano
                )
                
                # Gera de 3 a 5 alunos por turma para evitar sobrecarga
                qnt_alunos = random.randint(3, 5)
                random.shuffle(NOME_ANIMAIS)
                nomes_selecionados = NOME_ANIMAIS[:qnt_alunos]
                
                for nome in nomes_selecionados:
                    # Slugifica o nome da turma para o username ficar limpo
                    turma_slug = ano.nome.replace(" ", "").lower()
                    username = f"{PREFIXO_USER}{turma_slug}_{nome.lower()}"
                    
                    if not User.objects.filter(username=username).exists():
                        aluno = User.objects.create_user(
                            username=username,
                            password="123456",
                            first_name=nome,
                            tipo='ALUNO'
                        )
                        aluno.turmas.add(turma)
                        
                        # 4. Gera Estatísticas Falsas
                        EstatisticasUsuario.objects.create(
                            user=aluno,
                            pontuacao_geral=random.randint(100, 1000),
                            pontuacao_eterna=random.randint(500, 5000),
                            dias_ofensiva=random.randint(1, 15),
                            maior_ofensiva=random.randint(5, 20),
                            ultima_jogada=timezone.now().date()
                        )
                        
                        # 5. Gera Sessões de Jogos Falsas
                        if jogos:
                            jogos_jogados = random.sample(jogos, min(len(jogos), random.randint(1, 3)))
                            for jogo in jogos_jogados:
                                SessaoJogo.objects.create(
                                    user=aluno,
                                    jogo=jogo,
                                    pontuacao=random.randint(50, 300),
                                    tempo_jogo=random.randint(120, 600), # 2 a 10 min
                                    recorde_pontuacao=random.randint(100, 500)
                                )
                                
                        # 6. Gera Sessões de Aulas Falsas (Nova Arquitetura)
                        from livros_interativos.models import AulaInterativa, SessaoAulaInterativa
                        todas_aulas = list(AulaInterativa.objects.all())
                        if todas_aulas:
                            aulas_sorteadas = random.sample(todas_aulas, min(len(todas_aulas), random.randint(1, 3)))
                            for aula_lida in aulas_sorteadas:
                                SessaoAulaInterativa.objects.create(
                                    user=aluno,
                                    aula=aula_lida,
                                    pontuacao=random.randint(10, 150),
                                    tempo_gasto=random.randint(300, 1800) # 5 a 30 min
                                )
                                
                        total_alunos_criados += 1

            messages.success(request, f"Sucesso! Foram criados {total_alunos_criados} alunos fictícios e distribuídos em suas turmas com dados preenchidos.")
        except Exception as e:
            messages.error(request, f"Erro ao gerar dados: {str(e)}")
            
        return redirect('admin:gerador_demo_panel')

    return redirect('admin:index')


def apagar_dados_demo_view(request):
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Sem permissão.")
        return redirect('admin:index')

    if request.method == "POST":
        try:
            # Apaga em cascata (Users, Turmas, Escolas, Cidades)
            users_apagados = User.objects.filter(username__startswith=PREFIXO_USER).delete()[0]
            turmas_apagadas = Turma.objects.filter(nome__startswith=PREFIXO_MOCK).delete()[0]
            escolas_apagadas = Escola.objects.filter(nome__startswith=PREFIXO_MOCK).delete()[0]
            cidades_apagadas = Cidade.objects.filter(nome__startswith=PREFIXO_MOCK).delete()[0]
            estados_apagados = Estado.objects.filter(nome__startswith=PREFIXO_MOCK).delete()[0]
            paises_apagados = Pais.objects.filter(nome__startswith=PREFIXO_MOCK).delete()[0]

            messages.success(request, f"Limpeza concluída! Foram apagados: {users_apagados} usuários, {turmas_apagadas} turmas e {escolas_apagadas} escolas (com suas cidades e históricos em cascata).")
        except Exception as e:
            messages.error(request, f"Erro ao apagar dados: {str(e)}")

        return redirect('admin:gerador_demo_panel')

    return redirect('admin:index')


def gerador_demo_panel_view(request):
    """ View principal que renderiza a página com os botões """
    if not (request.user.is_superuser or request.user.is_staff):
        return redirect('admin:index')
        
    context = {
        'title': 'Gerador de Demonstração Segura',
        'is_popup': False,
        'has_permission': True,
    }
    return render(request, 'admin/gerador_demo.html', context)
