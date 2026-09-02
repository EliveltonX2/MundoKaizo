from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from .models import Colecao, Livro, Capitulo, AulaInterativa, SessaoAulaInterativa

@admin.register(Colecao)
class ColecaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ordem', 'ativo')
    list_editable = ('ordem', 'ativo')
    search_fields = ('nome',)


@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'colecao', 'volume', 'ativo')
    list_filter = ('colecao', 'ativo')
    search_fields = ('titulo',)


@admin.register(Capitulo)
class CapituloAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'livro', 'numero', 'ativo')
    list_filter = ('livro', 'ativo')
    search_fields = ('titulo', 'livro__titulo')


@admin.register(AulaInterativa)
class AulaInterativaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'capitulo', 'numero_aula', 'ativo', 'criado_em')
    search_fields = ('titulo', 'caminho_s3', 'capitulo__titulo', 'capitulo__livro__titulo')
    list_filter = ('ativo', 'anos_escolares', 'capitulo__livro')
    readonly_fields = ('caminho_s3',)
    filter_horizontal = ('anos_escolares', 'habilidades_bncc')
    
    change_list_template = "admin/livros_interativos/aulainterativa/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload/', self.admin_site.admin_view(self.upload_aulas_view), name='aulas_upload_direto'),
        ]
        return custom_urls + urls

    def upload_aulas_view(self, request):
        # Passa os capitulos para o template para o usuário selecionar na hora do upload
        capitulos = Capitulo.objects.filter(ativo=True).select_related('livro').order_by('livro__colecao__ordem', 'livro__volume', 'numero')
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'Upload de Aula Interativa (S3)',
            'capitulos': capitulos
        }
        return render(request, 'admin/livros_interativos/upload_aula.html', context)


@admin.register(SessaoAulaInterativa)
class SessaoAulaInterativaAdmin(admin.ModelAdmin):
    list_display = ('user', 'aula', 'pontuacao', 'tempo_gasto', 'atualizado_em')
    search_fields = ('user__username', 'aula__titulo')
    list_filter = ('atualizado_em',)
    readonly_fields = ('user', 'aula', 'pontuacao', 'recorde_pontuacao', 'tempo_gasto', 'rubrica', 'habilidades_conquistadas')
    filter_horizontal = ('habilidades_conquistadas',)
