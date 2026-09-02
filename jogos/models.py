from django.db import models
from django.conf import settings
from core.models import AnoEscolar, HabilidadeBNCC

class Jogo(models.Model):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, null=True)
    caminho_s3 = models.CharField(max_length=500, help_text="Caminho base do jogo no S3")
    capa = models.ImageField(upload_to='capas_jogos/', blank=True, null=True)
    ativo = models.BooleanField(default=True)
    
    anos_escolares = models.ManyToManyField(AnoEscolar, blank=True, related_name='jogos_novo')
    habilidades_relacionadas = models.ManyToManyField(HabilidadeBNCC, blank=True, related_name='jogos_novo')
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
        return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{self.caminho_s3}/index.html"


class SessaoJogo(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sessoes_jogos_novo')
    jogo = models.ForeignKey(Jogo, on_delete=models.CASCADE, related_name='sessoes')
    pontuacao = models.FloatField(default=0.0)
    recorde_pontuacao = models.FloatField(default=0.0)
    tempo_jogo = models.FloatField(default=0.0) # Em segundos
    rubrica = models.TextField(blank=True, null=True, help_text="Rubrica do jogador nesta sessão")
    habilidades_conquistadas = models.ManyToManyField(HabilidadeBNCC, blank=True, related_name='sessoes_jogos_novo')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'jogo')

    def __str__(self):
        return f"{self.user.username} jogou {self.jogo.titulo} - Total: {self.pontuacao} pts / {self.tempo_jogo}s"
