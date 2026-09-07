from django.db import models
from django.conf import settings

class Ticket(models.Model):
    CATEGORIAS = (
        ('RESET_SENHA', 'Resetar Senha'),
        ('DUVIDAS_PEDAGOGICAS', 'Dúvidas Pedagógicas'),
        ('PROBLEMAS_TECNICOS', 'Problemas Técnicos'),
        ('COMERCIAL', 'Comercial'),
    )

    STATUS_CHOICES = (
        ('ABERTO', 'Aberto'),
        ('EM_ANALISE', 'Em Análise'),
        ('RESOLVIDO', 'Resolvido'),
    )

    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tickets_solicitados'
    )
    assunto = models.CharField(max_length=200)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ABERTO')
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-atualizado_em']

    def __str__(self):
        return f"[{self.get_status_display()}] {self.assunto} - {self.solicitante.username}"

    @property
    def is_resolvido(self):
        return self.status == 'RESOLVIDO'

class MensagemTicket(models.Model):
    ticket = models.ForeignKey(
        Ticket, 
        on_delete=models.CASCADE, 
        related_name='mensagens'
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='mensagens_suporte'
    )
    texto = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)
    lida = models.BooleanField(default=False)

    class Meta:
        ordering = ['criado_em']

    def __str__(self):
        return f"Mensagem de {self.autor.username} em {self.ticket.assunto}"
