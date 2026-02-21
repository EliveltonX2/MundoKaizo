from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib.auth.admin import UserAdmin
from .models import User, Cidade, Escola, Turma, Livro, Pagina,TokenCadastro, Colecao
from django import forms
import uuid

# Configuração customizada para o User
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Informações Escolares', {'fields': ('tipo', 'escolas', 'turmas', 'cidades_gestao')}),
    )

# Inline para adicionar páginas direto na tela do Livro
class PaginaInline(admin.TabularInline):
    model = Pagina
    extra = 1

@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):
    inlines = [PaginaInline]
    list_display = ('titulo', 'is_versao_professor', 'criado_em')

# Registrar os outros modelos simples
admin.site.register(Cidade)
admin.site.register(Escola)
admin.site.register(Turma)

@admin.register(Colecao)
class ColecaoAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)

# core/admin.py
from .models import VideoAula # Adicione VideoAula na importação

@admin.register(VideoAula)
class VideoAulaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'livro', 'ordem', 'pagina_referencia')
    list_filter = ('livro',)
    search_fields = ('titulo', 'descricao')

# 1. Formulário Simples para o Admin preencher
class GerarTokensForm(forms.Form):
    quantidade = forms.IntegerField(min_value=1, max_value=1000, initial=50)
    tipo = forms.ChoiceField(choices=TokenCadastro.TIPOS)
    lote = forms.CharField(max_length=100, help_text="Ex: Escola Estadual SP - 2026")

@admin.register(TokenCadastro)
class TokenCadastroAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'tipo_usuario', 'lote', 'usado', 'usado_por')
    list_filter = ('tipo_usuario', 'lote', 'usado')
    search_fields = ('codigo', 'lote')
    
    # Aponta para o template que tem o botão "Gerar Lote"
    change_list_template = "admin/token_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('gerar-lote/', self.admin_site.admin_view(self.gerar_lote_view), name='gerar_lote'),
        ]
        return custom_urls + urls

    def gerar_lote_view(self, request):
        if request.method == "POST":
            form = GerarTokensForm(request.POST)
            if form.is_valid():
                qtd = form.cleaned_data['quantidade']
                tipo = form.cleaned_data['tipo']
                lote = form.cleaned_data['lote']
                
                tokens_para_salvar = []
                
                # Loop para criar a quantidade desejada
                for _ in range(qtd):
                    codigo_unico_encontrado = False
                    
                    # Tenta gerar até achar um que não exista no banco
                    while not codigo_unico_encontrado:
                        raw = str(uuid.uuid4()).upper().replace('-', '')
                        # KZ + 4 letras + 4 letras (Ex: KZ-A1B2-C3D4)
                        candidato_codigo = f"KZ-{raw[:4]}-{raw[4:8]}"
                        
                        # Verifica no banco se já existe (Essa é a blindagem)
                        if not TokenCadastro.objects.filter(codigo=candidato_codigo).exists():
                            codigo_unico_encontrado = True
                            
                            # Adiciona na lista para salvar depois
                            tokens_para_salvar.append(TokenCadastro(
                                tipo_usuario=tipo, 
                                lote=lote,
                                codigo=candidato_codigo
                            ))

                # Salva todos de uma vez (Agora seguro!)
                TokenCadastro.objects.bulk_create(tokens_para_salvar)
                
                self.message_user(request, f"Sucesso! {qtd} cartões gerados e verificados para '{lote}'.")
                return redirect('admin:core_tokencadastro_changelist')
        else:
            form = GerarTokensForm()

        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'title': "Gerar Lote de Cartões"
        }
        return render(request, 'admin/gerar_tokens.html', context)