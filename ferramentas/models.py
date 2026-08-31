from django.db import models
from django.conf import settings
from django.utils.text import slugify

class Ferramenta(models.Model):
    nome = models.CharField(max_length=200, verbose_name="Nome da Ferramenta")
    slug = models.SlugField(max_length=200, unique=True, blank=True, help_text="URL amigável (gerado automaticamente se deixado em branco)")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")
    caminho_s3 = models.CharField(max_length=500, help_text="Caminho base da ferramenta no S3 (ex: ferramentas/calculadora)")
    thumb = models.ImageField(upload_to='ferramentas_thumbs/', blank=True, null=True, help_text="Tamanho ideal: 600x400 pixels")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ferramenta Kaizo"
        verbose_name_plural = "Ferramentas Kaizo"
        ordering = ['-criado_em']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome

    @property
    def url_ferramenta(self):
        if self.caminho_s3:
            return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{self.caminho_s3}/index.html"
        return ""
