import re
import uuid
from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.templatetags.static import static

# --- Estrutura Geográfica e Institucional ---
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
        DEMO = 'DEMO', 'Conta de Demonstração'

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
    is_demo = models.BooleanField(default=False, help_text="Marque esta opção para liberar este livro para contas de demonstração.")
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