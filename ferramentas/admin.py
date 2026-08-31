from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from .models import Ferramenta

@admin.register(Ferramenta)
class FerramentaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'caminho_s3', 'ativo', 'criado_em')
    search_fields = ('nome', 'caminho_s3', 'slug')
    list_filter = ('ativo', 'criado_em')
    readonly_fields = ('caminho_s3',)
    prepopulated_fields = {'slug': ('nome',)}
    
    # Custom template to show the "Upload Direto" button
    change_list_template = "admin/ferramentas/ferramenta/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload/', self.admin_site.admin_view(self.upload_ferramentas_view), name='ferramentas_upload_direto'),
        ]
        return custom_urls + urls

    def upload_ferramentas_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            'title': 'Upload de Ferramenta (S3)'
        }
        return render(request, 'admin/ferramentas/upload_ferramentas.html', context)
