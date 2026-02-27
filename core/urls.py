from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.auth import views as auth_views
from . import views
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [

    path('livro/<int:livro_id>/ler/', views.visualizar_livro, name='ler_livro'),
    #URL DAS PAGINAS SECA
    # URL: /livro/1/pagina/5/
    path('livro/<int:livro_id>/pagina/<int:numero_pagina>/', views.pagina_livro_view, name='pagina_imagem'),
    path('livro/<int:livro_id>/aulas/', views.lista_aulas_view, name='lista_aulas'),
    path('aula/<int:aula_id>/', views.assistir_aula_view, name='assistir_aula'),
    path('videos/', views.galeria_videos, name='galeria_videos'),

    path('painel/', views.painel_gestao_view, name='painel_gestao'),
    path('painel/reset/<int:user_id>/', views.resetar_senha, name='resetar_senha'),

    path('', views.estante_view, name='estante'),
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('recuperar-senha/', TemplateView.as_view(template_name='core/password_reset_guide.html'), name='password_reset_guide'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('alterar-senha/', 
         auth_views.PasswordChangeView.as_view(
             template_name='core/alterar_senha.html', 
             success_url='/estante/'
         ), 
         name='alterar_senha'),
    path('ativar/', views.ativar_conta_view, name='ativar_conta'),
    path('api/turmas/<int:escola_id>/', views.api_turmas_por_escola, name='api_turmas'),
    path('gestao/vincular-cartoes/', views.vincular_cartoes_view, name='vincular_cartoes'),
    path('gestao/nova-turma/', views.criar_turma_view, name='criar_turma'),
    
    path('kai/', views.chat_view, name='kai_chat'),
    path('kai/renomear/<int:sessao_id>/', views.renomear_chat, name='renomear_chat'),
    path('kai/deletar/<int:sessao_id>/', views.deletar_chat, name='deletar_chat'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)