from django.contrib import admin
from .models import Ticket, MensagemTicket

class MensagemTicketInline(admin.TabularInline):
    model = MensagemTicket
    extra = 1
    readonly_fields = ('criado_em',)

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'assunto', 'solicitante', 'categoria', 'status', 'criado_em', 'atualizado_em')
    list_filter = ('status', 'categoria', 'criado_em')
    search_fields = ('assunto', 'solicitante__username', 'solicitante__email')
    readonly_fields = ('criado_em', 'atualizado_em')
    inlines = [MensagemTicketInline]
    
    # Adicionando ações para fechar tickets facilmente
    actions = ['marcar_como_resolvido', 'marcar_em_analise']

    def marcar_como_resolvido(self, request, queryset):
        queryset.update(status='RESOLVIDO')
    marcar_como_resolvido.short_description = "Marcar tickets selecionados como Resolvidos"

    def marcar_em_analise(self, request, queryset):
        queryset.update(status='EM_ANALISE')
    marcar_em_analise.short_description = "Marcar tickets selecionados como Em Análise"

@admin.register(MensagemTicket)
class MensagemTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'autor', 'criado_em', 'lida')
    list_filter = ('lida', 'criado_em')
    search_fields = ('texto', 'autor__username', 'ticket__assunto')
    readonly_fields = ('criado_em',)
