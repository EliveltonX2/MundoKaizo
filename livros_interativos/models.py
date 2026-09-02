from django.db import models
from django.conf import settings
from django.utils.text import slugify
from core.models import AnoEscolar, HabilidadeBNCC

class Colecao(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome da Coleção")
    ordem = models.IntegerField(default=0, help_text="Define qual coleção aparece primeiro na estante (números menores aparecem antes).")
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name = "Coleção"
        verbose_name_plural = "Coleções"
        ordering = ['ordem', 'nome']


class Livro(models.Model):
    titulo = models.CharField(max_length=200, verbose_name="Título do Livro")
    colecao = models.ForeignKey(Colecao, on_delete=models.CASCADE, related_name='livros')
    volume = models.PositiveIntegerField(null=True, blank=True, verbose_name="Volume")
    capa = models.ImageField(upload_to='capas_livros_interativos/', blank=True, null=True, help_text="Capa do livro")
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.colecao.nome} - {self.titulo} (Vol. {self.volume or 1})"
    
    class Meta:
        verbose_name = "Livro"
        verbose_name_plural = "Livros"
        ordering = ['colecao__ordem', 'volume', 'titulo']


class Capitulo(models.Model):
    titulo = models.CharField(max_length=200, verbose_name="Título do Capítulo")
    livro = models.ForeignKey(Livro, on_delete=models.CASCADE, related_name='capitulos')
    numero = models.PositiveIntegerField(default=1, verbose_name="Número do Capítulo")
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"Cap {self.numero}: {self.titulo} ({self.livro.titulo})"
    
    class Meta:
        verbose_name = "Capítulo"
        verbose_name_plural = "Capítulos"
        ordering = ['livro__colecao__ordem', 'livro__volume', 'numero']


class AulaInterativa(models.Model):
    titulo = models.CharField(max_length=200, verbose_name="Título da Aula")
    capitulo = models.ForeignKey(Capitulo, on_delete=models.CASCADE, related_name='aulas')
    numero_aula = models.PositiveIntegerField(help_text="Número sequencial da Aula")
    
    caminho_s3 = models.CharField(max_length=500, blank=True, null=True, help_text="Caminho base da aula no S3 (ex: livros_web/aula_x)")
    ativo = models.BooleanField(default=True)
    
    anos_escolares = models.ManyToManyField(AnoEscolar, blank=True, related_name='aulas_interativas_novo')
    habilidades_bncc = models.ManyToManyField(HabilidadeBNCC, blank=True, related_name='aulas_interativas_novo')
    
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Aula Interativa"
        verbose_name_plural = "Aulas Interativas"
        ordering = ['capitulo__livro__colecao__ordem', 'capitulo__livro__volume', 'capitulo__numero', 'numero_aula']

    def __str__(self):
        return f"Aula {self.numero_aula} - {self.titulo} ({self.capitulo.titulo})"

    @property
    def url_interativa(self):
        if self.caminho_s3:
            return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{self.caminho_s3}/index.html"
        return ""


class SessaoAulaInterativa(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sessoes_aulas_interativas_novo')
    aula = models.ForeignKey(AulaInterativa, on_delete=models.CASCADE, related_name='sessoes')
    pontuacao = models.FloatField(default=0.0)
    recorde_pontuacao = models.FloatField(default=0.0)
    tempo_gasto = models.FloatField(default=0.0) # Em segundos
    rubrica = models.TextField(blank=True, null=True, help_text="Rubrica do aluno nesta aula")
    habilidades_conquistadas = models.ManyToManyField(HabilidadeBNCC, blank=True, related_name='sessoes_aulas_novo')
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'aula')
        verbose_name = "Sessão de Aula Interativa"
        verbose_name_plural = "Sessões de Aulas Interativas"

    def __str__(self):
        return f"{self.user.username} - {self.aula.titulo}"
