from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Cidade, Escola, Turma, Livro, Pagina

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



# core/admin.py
from .models import VideoAula # Adicione VideoAula na importação

@admin.register(VideoAula)
class VideoAulaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'livro', 'ordem', 'pagina_referencia')
    list_filter = ('livro',)
    search_fields = ('titulo', 'descricao')