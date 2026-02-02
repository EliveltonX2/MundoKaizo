import re
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.templatetags.static import static

# --- Estrutura Geográfica e Institucional ---

class Cidade(models.Model):
    nome = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)

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
    
    def __str__(self):
        return f"{self.nome} - {self.escola.nome}"

# --- Usuários ---

class User(AbstractUser):
    class Tipos(models.TextChoices):
        ALUNO = 'ALUNO', 'Aluno'
        PROFESSOR = 'PROFESSOR', 'Professor'
        GESTOR_LOCAL = 'GESTOR_LOCAL', 'Gestor Local'
        GESTOR_GERAL = 'GESTOR_GERAL', 'Gestor Geral'
        ADMIN = 'ADMIN', 'Administrador'

    tipo = models.CharField(
        max_length=20, 
        choices=Tipos.choices, 
        default=Tipos.ALUNO
    )
    
    # Relacionamentos para hierarquia
    escolas = models.ManyToManyField(Escola, blank=True, help_text="Para Gestores Locais e Professores")
    turmas = models.ManyToManyField(Turma, blank=True, help_text="Para Professores e Alunos")
    
    # Para Gestor Geral (pode ser responsável por várias cidades ou escolas específicas)
    cidades_gestao = models.ManyToManyField(Cidade, blank=True, help_text="Para Gestor Geral gerenciar cidades inteiras")

    def __str__(self):
        return f"{self.username} ({self.get_tipo_display()})"

    # Helper para verificar permissões rapidamente
    @property
    def is_gestor_local(self):
        return self.tipo == self.Tipos.GESTOR_LOCAL

    @property
    def is_professor(self):
        return self.tipo == self.Tipos.PROFESSOR

# --- Livros ---
class Livro(models.Model):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    capa = models.ImageField(upload_to='capas/', null=True, blank=True)
    is_versao_professor = models.BooleanField(default=False)
    
    versao_professor_relacionada = models.OneToOneField(
        'self', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name='versao_aluno',
        help_text="Se este é um livro do aluno, selecione aqui a versão do professor correspondente."
    )
    
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        tipo = "Prof" if self.is_versao_professor else "Aluno"
        return f"{self.titulo} ({tipo})"



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
        Retorna a URL da capa:
        1. Se tiver upload manual, usa ele.
        2. Se for link do YouTube, pega do YouTube.
        3. Se não tiver nada, retorna um placeholder padrão.
        """
        if self.thumbnail:
            return self.thumbnail.url
        
        # Tenta extrair do link (se o campo se chamar 'link_video' ou 'url')
        # Ajuste 'self.link_video' para o nome real do seu campo de URL
        url_alvo = getattr(self, 'link_video', '') or getattr(self, 'url', '')
        
        if url_alvo:
            # Regex para pegar o ID do YouTube (funciona com youtube.com e youtu.be)
            youtube_regex = (
                r'(https?://)?(www\.)?'
                '(youtube|youtu|youtube-nocookie)\.(com|be)/'
                '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
            )
            match = re.match(youtube_regex, url_alvo)
            if match:
                video_id = match.group(6)
                # Retorna a imagem de alta qualidade do YouTube
                return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

        # Retorna uma imagem padrão se não achar nada
        # Você precisa ter essa imagem na pasta static
        return static('core/img/video_placeholder.svg')

    def __str__(self):
        origem = self.livro.titulo if self.livro else "Vídeo Avulso"
        return f"[{origem}] {self.titulo}"