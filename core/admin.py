from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib.auth.admin import UserAdmin
from .models import User, Pais, Estado, Cidade, Escola, Turma, Livro, Pagina,TokenCadastro, Colecao, RegistroAcessoDemo, Jogo, AnoEscolar
from django import forms
import uuid

# Configuração customizada para o User
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Informações Escolares', {'fields': ('tipo', 'escolas', 'turmas', 'cidades_gestao', 'estados_gestao', 'paises_gestao')}),
    )
    filter_horizontal = ('groups', 'user_permissions', 'escolas', 'turmas', 'cidades_gestao', 'estados_gestao', 'paises_gestao')

@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'colecao', 'volume', 'formato', 'get_anos_escolares', 'is_versao_professor', 'is_demo', 'criado_em')
    list_editable = ('colecao', 'volume', 'formato', 'is_versao_professor','is_demo')
    
    def get_anos_escolares(self, obj):
        return ", ".join([a.nome for a in obj.anos_escolares.all()])
    get_anos_escolares.short_description = 'Anos Escolares'
    
    # ATUALIZAÇÃO: Aponta para o template que terá nosso botão azul!
    change_list_template = "admin/core/livro/change_list.html"

    # Criamos a rota interna do Admin
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-em-massa/', self.admin_site.admin_view(self.upload_em_massa_view), name='upload_paginas_massa'),
            path('upload-interativo/', self.admin_site.admin_view(self.upload_interativo_view), name='upload_livro_interativo'),
        ]
        return custom_urls + urls

    # A view que carrega a nossa tela de envio
    def upload_em_massa_view(self, request):
        livros = Livro.objects.all().order_by('titulo')
        context = {
            **self.admin_site.each_context(request),
            'livros': livros,
            'title': "Upload de Páginas em Massa (S3)"
        }
        return render(request, 'admin/upload_paginas_massa.html', context)

    # A view que carrega a tela de upload interativo
    def upload_interativo_view(self, request):
        from .models import HabilidadeBNCC
        habilidades = HabilidadeBNCC.objects.all().order_by('codigo')
        context = {
            **self.admin_site.each_context(request),
            'title': "Upload de Livro Interativo (S3)",
            'habilidades_bncc': habilidades
        }
        return render(request, 'admin/upload_livro_interativo.html', context)

# Registrar os outros modelos simples
admin.site.register(Pais)
admin.site.register(Estado)
admin.site.register(Cidade)
admin.site.register(Escola)
from .admin_demo_generator import gerador_demo_panel_view, gerar_dados_demo_view, apagar_dados_demo_view

@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    change_list_template = "admin/core/turma/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('gerador-demo/', self.admin_site.admin_view(gerador_demo_panel_view), name='gerador_demo_panel'),
            path('gerador-demo/gerar/', self.admin_site.admin_view(gerar_dados_demo_view), name='gerar_dados_demo'),
            path('gerador-demo/apagar/', self.admin_site.admin_view(apagar_dados_demo_view), name='apagar_dados_demo'),
        ]
        return custom_urls + urls

@admin.register(AnoEscolar)
class AnoEscolarAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ordem')
    list_editable = ('ordem',)
    ordering = ('ordem',)


@admin.register(Colecao)
class ColecaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ordem')
    search_fields = ('ordem',)

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
    

@admin.register(RegistroAcessoDemo)
class RegistroAcessoDemoAdmin(admin.ModelAdmin):
    # As colunas que vão aparecer na tabela
    list_display = ('user', 'data_login', 'tempo_navegacao', 'localizacao', 'dispositivo_curto')
    
    # Filtros laterais para você achar rápido se ele logou em dias diferentes
    list_filter = ('data_login', 'user')
    
    # Barra de pesquisa
    search_fields = ('user__username', 'ip', 'localizacao')
    
    # Impede que alguém altere os dados de rastreio manualmente
    readonly_fields = ('user', 'ip', 'localizacao', 'dispositivo', 'data_login', 'ultima_atividade', 'tempo_navegacao_minutos')

    # Deixa o texto do celular/PC menorzinho para não quebrar a tabela
    def dispositivo_curto(self, obj):
        if obj.dispositivo:
            return obj.dispositivo[:50] + "..." if len(obj.dispositivo) > 50 else obj.dispositivo
        return "Desconhecido"
    dispositivo_curto.short_description = 'Dispositivo'

    # Mostra o tempo já com o "min" escrito do lado
    def tempo_navegacao(self, obj):
        minutos = obj.tempo_navegacao_minutos
        if minutos == 0:
            return "Menos de 1 min"
        return f"{minutos} min"
    tempo_navegacao.short_description = 'Tempo Gasto'
    
    # Impede de adicionar acessos manualmente (só o sistema pode fazer isso)
    def has_add_permission(self, request):
        return False
    
@admin.register(Jogo)
class JogoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'caminho_s3', 'ativo', 'criado_em')
    search_fields = ('titulo', 'caminho_s3')
    list_filter = ('ativo', 'criado_em')
    
    # Isso deixa o campo caminho_s3 como leitura, já que o nosso JS é quem vai preencher isso!
    readonly_fields = ('caminho_s3',)

from .models import HabilidadeBNCC, EstatisticasUsuario, SessaoJogo

@admin.register(HabilidadeBNCC)
class HabilidadeBNCCAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'get_anos_escolares', 'descricao')
    list_filter = ('anos_escolares',)
    search_fields = ('codigo', 'descricao')

    def get_anos_escolares(self, obj):
        return ", ".join([a.nome for a in obj.anos_escolares.all()])
    get_anos_escolares.short_description = 'Anos Escolares'

@admin.register(EstatisticasUsuario)
class EstatisticasUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'pontuacao_geral', 'dias_ofensiva', 'ultima_jogada')
    search_fields = ('user__username',)

@admin.register(SessaoJogo)
class SessaoJogoAdmin(admin.ModelAdmin):
    list_display = ('user', 'jogo', 'pontuacao', 'tempo_jogo', 'atualizado_em')
    list_filter = ('jogo',)
    search_fields = ('user__username', 'jogo__titulo')

from .models import SessaoLivroInterativo

@admin.register(SessaoLivroInterativo)
class SessaoLivroInterativoAdmin(admin.ModelAdmin):
    list_display = ('user', 'livro', 'pontuacao', 'tempo_gasto', 'atualizado_em')
    list_filter = ('livro',)
    search_fields = ('user__username', 'livro__titulo')