import re
import uuid
from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.templatetags.static import static
from django.utils import timezone

# --- Estrutura Geográfica e Institucional ---
class AnoEscolar(models.Model):
    nome = models.CharField(max_length=20, unique=True, help_text="Ex: 1 Ano EF, 1 Ano EM")
    ordem = models.IntegerField(default=0, help_text="Define a ordenação nas listas (ex: 1 para 1º EF, 10 para 1º EM)")

    class Meta:
        ordering = ['ordem']
        verbose_name = "Ano Escolar"
        verbose_name_plural = "Anos Escolares"

    def __str__(self):
        return self.nome

class TokenCadastro(models.Model):
    TIPOS = (
        ('ALUNO', 'Aluno'),
        ('PROFESSOR', 'Professor'),
        ('GESTOR_LOCAL', 'Gestor Escolar'),
    )

    # O código curto para digitar (Ex: KZ-A9B2-X1Y2)
    codigo = models.CharField(max_length=20, unique=True, editable=False)
    
    # Qual o papel que esse token libera?
    tipo_usuario = models.CharField(max_length=20, choices=TIPOS)
    
    # Identificação do lote (Ex: "Prefeitura SP - Lote 1 - 2026")
    lote = models.CharField(max_length=100)
    

    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, null=True, blank=True)
    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, null=True, blank=True)

    # Controle de uso
    usado = models.BooleanField(default=False)
    usado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    data_uso = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.codigo:
            # Gera um código estilo Gift Card (12 digitos em blocos)
            raw = str(uuid.uuid4()).upper().replace('-', '')
            self.codigo = f"KZ-{raw[:4]}-{raw[4:8]}"
        super().save(*args, **kwargs)

    def __str__(self):
        status = "USADO" if self.usado else "DISPONÍVEL"
        return f"[{self.tipo_usuario}] {self.codigo} - {status}"


class Pais(models.Model):
    nome = models.CharField(max_length=100)

    def __str__(self):
        return self.nome

class Estado(models.Model):
    nome = models.CharField(max_length=100)
    sigla = models.CharField(max_length=2)
    pais = models.ForeignKey(Pais, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.nome} - {self.sigla}"

class Cidade(models.Model):
    nome = models.CharField(max_length=100)
    estado = models.ForeignKey(Estado, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.nome

class Escola(models.Model):
    nome = models.CharField(max_length=200)
    cidade = models.ForeignKey(Cidade, on_delete=models.CASCADE)

    def __str__(self):
        return self.nome

class Turma(models.Model):
    nome = models.CharField(max_length=100, help_text="Ex: 3º Ano A")
    escola = models.ForeignKey(Escola, on_delete=models.CASCADE)
    ano_escolar = models.ForeignKey(AnoEscolar, on_delete=models.SET_NULL, null=True, blank=True, related_name='turmas')
    
    def __str__(self):
        return f"{self.nome} - {self.escola.nome}"

# --- Usuários ---

class User(AbstractUser):
    class Tipos(models.TextChoices):
        ALUNO = 'ALUNO', 'Aluno'
        PROFESSOR = 'PROFESSOR', 'Professor'
        GESTOR_LOCAL = 'GESTOR_LOCAL', 'Gestor Escolar'
        GESTOR_REGIONAL = 'GESTOR_REGIONAL', 'Gestor Regional'
        GESTOR_KAIZO = 'GESTOR_KAIZO', 'Gestor Kaizo'
        ADMIN = 'ADMIN', 'Administrador'
        DEMO = 'DEMO', 'Conta de Demonstração'

    tipo = models.CharField(
        max_length=20, 
        choices=Tipos.choices, 
        default=Tipos.ALUNO
    )
    
    # Relacionamentos para hierarquia
    escolas = models.ManyToManyField(Escola, blank=True, help_text="Para Gestores Locais e Professores")
    turmas = models.ManyToManyField(Turma, blank=True, help_text="Para Professores e Alunos")
    
    cidades_gestao = models.ManyToManyField(Cidade, blank=True, help_text="Para Gestor Regional gerenciar cidades")
    estados_gestao = models.ManyToManyField(Estado, blank=True, help_text="Para Gestor Regional/Kaizo gerenciar estados")
    paises_gestao = models.ManyToManyField(Pais, blank=True, help_text="Para Gestor Kaizo gerenciar países")

    def __str__(self):
        return f"{self.username} ({self.get_tipo_display()})"

    # Helper para verificar permissões rapidamente
    @property
    def is_gestor_local(self):
        return self.tipo == self.Tipos.GESTOR_LOCAL

    @property
    def is_professor(self):
        return self.tipo == self.Tipos.PROFESSOR
        
    @property
    def is_gestor_regional(self):
        return self.tipo == self.Tipos.GESTOR_REGIONAL
        
    @property
    def is_gestor_kaizo(self):
        return self.tipo == self.Tipos.GESTOR_KAIZO

class Colecao(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome da Coleção")
    
    # NOVO CAMPO: Controla a ordem na tela (0, 1, 2, 3...)
    ordem = models.IntegerField(
        default=0, 
        help_text="Define qual coleção aparece primeiro na estante (números menores aparecem antes)."
    )

    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name = "Coleção"
        verbose_name_plural = "Coleções"
        # Já deixa a coleção ordenada por padrão no banco de dados
        ordering = ['ordem', 'nome']


# --- Livros ---
class Livro(models.Model):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    tags = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Digite as palavras-chave separadas por vírgula (ex: matemática, 7º ano, lógica)"
    )
    is_demo = models.BooleanField(default=False, help_text="Marque esta opção para liberar este livro para contas de demonstração.")
    capa = models.ImageField(upload_to='capas/', null=True, blank=True)
    is_versao_professor = models.BooleanField(default=False)
    
    anos_escolares = models.ManyToManyField(AnoEscolar, blank=True, related_name='livros')
    
    rubricas_atividades = models.JSONField(default=dict, blank=True, help_text="Estrutura de rubricas das atividades (usado para livros interativos)")
    
    FORMATOS = (
        ('ESTATICO', 'Estático'),
        ('INTERATIVO', 'Interativo'),
    )
    formato = models.CharField(max_length=20, choices=FORMATOS, default='ESTATICO')
    caminho_s3 = models.CharField(max_length=500, blank=True, null=True, help_text="Caminho base do livro interativo no S3")
    
    habilidades_relacionadas = models.ManyToManyField('HabilidadeBNCC', blank=True, related_name='livros')

    colecao = models.ForeignKey(
        Colecao, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='livros',
        verbose_name="Coleção"
    )
    
    

    volume = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        verbose_name="Volume",
        help_text="Número do volume (deixe em branco se for volume único)."
    )
    
    versao_professor_relacionada = models.OneToOneField(
        'self', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name='versao_aluno',
        help_text="Se este é um livro do aluno, selecione aqui a versão do professor correspondente."
    )
    
    criado_em = models.DateTimeField(auto_now_add=True)
    
    
    class Meta:
        # AQUI ESTÁ A MÁGICA DA UNICIDADE:
        constraints = [
            models.UniqueConstraint(
                fields=['colecao', 'volume'], 
                name='unique_volume_por_colecao'
            )
        ]
    

    def __str__(self):
        tipo = "Prof" if self.is_versao_professor else "Aluno"
        return f"{self.titulo} ({tipo})"

    @property
    def url_interativa(self):
        if self.formato == 'INTERATIVO' and self.caminho_s3:
            return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{self.caminho_s3}/index.html"
        return ""

class AtividadeLivro(models.Model):
    livro = models.ForeignKey(Livro, on_delete=models.CASCADE, related_name='atividades')
    numero = models.PositiveIntegerField(help_text="Número da atividade (ex: 1 para Atividade 1)")
    
    class Meta:
        ordering = ['numero']
        unique_together = ['livro', 'numero']

    def __str__(self):
        return f"Atividade {self.numero} - {self.livro.titulo}"


class RubricaAlternativa(models.Model):
    atividade = models.ForeignKey(AtividadeLivro, on_delete=models.CASCADE, related_name='rubricas')
    alternativa = models.CharField(max_length=10, help_text="Ex: A, B, C, D")
    texto_rubrica = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        unique_together = ['atividade', 'alternativa']
        ordering = ['alternativa']

    def __str__(self):
        return f"[{self.alternativa}] {self.texto_rubrica}"


class Pagina(models.Model):
    livro = models.ForeignKey(Livro, related_name='paginas', on_delete=models.CASCADE)
    numero = models.PositiveIntegerField()
    
    # Aqui está o segredo: upload para fora da pasta public
    # O caminho será relativo ao PROTECTED_MEDIA_ROOT configurado manualmente na View depois
    imagem_original = models.ImageField(upload_to='livros_source/%Y/%m/') 
    
    class Meta:
        ordering = ['numero']
        unique_together = ['livro', 'numero']

    def __str__(self):
        return f"{self.livro.titulo} - Pág {self.numero}"
    

# core/models.py

class VideoAula(models.Model):
    # Alteramos aqui: null=True, blank=True
    livro = models.ForeignKey(Livro, related_name='aulas', on_delete=models.CASCADE, null=True, blank=True)
    pagina_referencia = models.ForeignKey(Pagina, on_delete=models.SET_NULL, null=True, blank=True)
    
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    codigo_embed = models.TextField()

    thumbnail = models.ImageField(upload_to='thumbnails_videos/', blank=True, null=True)
    
    # Importante para a galeria: Data de criação para ordenar os "Mais Recentes"
    criado_em = models.DateTimeField(auto_now_add=True) 
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        # Ordenamos por data de criação (mais recente primeiro) se não tiver ordem definida
        ordering = ['-criado_em', 'ordem']

    @property
    def get_capa(self):
        """
        Versão Blindada: Busca thumb em upload manual, links do YouTube ou iframes de embed.
        """
        # 1. Prioridade total para capa manual (Upload)
        if self.thumbnail:
            return self.thumbnail.url
        
        # 2. Define onde procurar o link do YouTube.
        # O 'getattr' evita erro se o campo não existir.
        # Tenta pegar conteúdo dos campos: 'url', 'link', 'video_url' ou 'codigo_embed'
        textos_para_analise = [
            getattr(self, 'url', ''),
            getattr(self, 'link', ''),
            getattr(self, 'video_url', ''),
            getattr(self, 'link_video', ''),
            getattr(self, 'codigo_embed', '') # Pega até se for um <iframe> colado
        ]

        # 3. Regex Poderoso (O "Busca-Tudo")
        # Ele caça um ID de 11 letras do YouTube em qualquer lugar do texto
        regex_youtube = r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})'

        for texto in textos_para_analise:
            if not texto:
                continue
                
            match = re.search(regex_youtube, str(texto))
            if match:
                video_id = match.group(1)
                # Retorna a imagem de alta qualidade do YouTube
                return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

        # 4. Se não achou nada, retorna o placeholder
        return static('core/img/video_placeholder.png')
    

class SessaoChat(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    criado_em = models.DateTimeField(auto_now_add=True)
    titulo = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return f"Chat de {self.user.username} em {self.criado_em.strftime('%d/%m/%Y')}"

class Mensagem(models.Model):
    sessao = models.ForeignKey(SessaoChat, on_delete=models.CASCADE, related_name='mensagens')
    # True se a mensagem for do usuário, False se for da IA
    is_user = models.BooleanField(default=True) 
    texto = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criado_em'] # Garante que as mensagens fiquem na ordem certa
        

class RegistroAcessoDemo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='acessos_demo')
    ip = models.GenericIPAddressField(null=True, blank=True)
    localizacao = models.CharField(max_length=255, blank=True, null=True)
    dispositivo = models.CharField(max_length=255, blank=True, null=True)
    data_login = models.DateTimeField(auto_now_add=True)
    ultima_atividade = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Acesso de {self.user.username} em {self.data_login.strftime('%d/%m/%Y %H:%M')}"

    @property
    def tempo_navegacao_minutos(self):
        # Calcula a diferença entre o login e a última página que ele clicou
        diferenca = self.ultima_atividade - self.data_login
        minutos = int(diferenca.total_seconds() / 60)
        return minutos

class Jogo(models.Model):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, null=True)
    # Aqui não usamos um FileField, pois o upload não passa pelo Django!
    # Apenas salvamos o caminho onde o "index.html" do jogo ficou salvo no S3.
    caminho_s3 = models.CharField(max_length=500, help_text="Caminho base do jogo no S3")
    capa = models.ImageField(upload_to='capas_jogos/', blank=True, null=True)
    ativo = models.BooleanField(default=True)
    
    anos_escolares = models.ManyToManyField(AnoEscolar, blank=True, related_name='jogos')
    habilidades_relacionadas = models.ManyToManyField('HabilidadeBNCC', blank=True, related_name='jogos')
    rubrica_1 = models.CharField(max_length=255, blank=True, null=True, help_text="Rubrica opção 1")
    rubrica_2 = models.CharField(max_length=255, blank=True, null=True, help_text="Rubrica opção 2")
    rubrica_3 = models.CharField(max_length=255, blank=True, null=True, help_text="Rubrica opção 3")
    rubrica_4 = models.CharField(max_length=255, blank=True, null=True, help_text="Rubrica opção 4")
    rubrica_5 = models.CharField(max_length=255, blank=True, null=True, help_text="Rubrica opção 5")
    
    criado_em = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.titulo
    
    @property
    def url_jogar(self):
        # Retorna a URL completa para montar o iframe no Frontend
        return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{self.caminho_s3}/index.html"


class EstatisticasUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='estatisticas')
    pontuacao_geral = models.FloatField(default=0.0)
    pontuacao_eterna = models.FloatField(default=0.0, help_text="Soma de todas as pontuações adquiridas")
    habilidades_conquistadas = models.ManyToManyField('HabilidadeBNCC', blank=True, related_name='estatisticas_usuario')
    dias_ofensiva = models.IntegerField(default=0)
    maior_ofensiva = models.IntegerField(default=0)
    ultima_jogada = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Estatísticas de {self.user.username}"


class HabilidadeBNCC(models.Model):
    codigo = models.CharField(max_length=20, unique=True, help_text="Ex: EF01MA01")
    anos_escolares = models.ManyToManyField(AnoEscolar, blank=True, related_name='habilidades')
    descricao = models.TextField(help_text="Descrição da habilidade")
    explicacao = models.TextField(blank=True, null=True, help_text="Explicação da habilidade")
    exemplo_uso = models.TextField(blank=True, null=True, help_text="Exemplo de uso da habilidade")

    def __str__(self):
        return self.codigo


class SessaoJogo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessoes_jogos')
    jogo = models.ForeignKey(Jogo, on_delete=models.CASCADE, related_name='sessoes')
    pontuacao = models.FloatField(default=0.0)
    recorde_pontuacao = models.FloatField(default=0.0)
    tempo_jogo = models.FloatField(default=0.0) # Em segundos
    rubrica = models.TextField(blank=True, null=True, help_text="Rubrica do jogador nesta sessão")
    habilidades_conquistadas = models.ManyToManyField('HabilidadeBNCC', blank=True, related_name='sessoes_jogos')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'jogo')

    def __str__(self):
        return f"{self.user.username} jogou {self.jogo.titulo} - Total: {self.pontuacao} pts / {self.tempo_jogo}s"