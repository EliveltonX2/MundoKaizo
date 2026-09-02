from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from .models import Jogo, SessaoJogo

@admin.register(Jogo)
class JogoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'ativo', 'criado_em')
    search_fields = ('titulo', 'caminho_s3')
    list_filter = ('ativo', 'anos_escolares')
    readonly_fields = ('caminho_s3',)
    filter_horizontal = ('anos_escolares', 'habilidades_relacionadas')
    
    change_list_template = "admin/jogos/jogo/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload/', self.admin_site.admin_view(self.upload_jogos_view), name='jogos_upload_direto'),
        ]
        return custom_urls + urls

    def upload_jogos_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            'title': 'Upload de Jogo Web (S3)',
        }
        return render(request, 'admin/jogos/upload_jogo.html', context)


@admin.register(SessaoJogo)
class SessaoJogoAdmin(admin.ModelAdmin):
    list_display = ('user', 'jogo', 'pontuacao', 'tempo_jogo', 'atualizado_em')
    search_fields = ('user__username', 'jogo__titulo')
    list_filter = ('atualizado_em',)
    readonly_fields = ('user', 'jogo', 'pontuacao', 'recorde_pontuacao', 'tempo_jogo', 'rubrica', 'habilidades_conquistadas')
    filter_horizontal = ('habilidades_conquistadas',)
