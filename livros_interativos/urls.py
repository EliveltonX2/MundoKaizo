from django.urls import path
from . import views

app_name = 'livros_interativos'

urlpatterns = [
    path('', views.aulas_list_view, name='lista'),
    path('<int:aula_id>/', views.ler_aula_view, name='ler'),
    path('api/salvar-aula/', views.api_salvar_aula, name='api_salvar_aula'),
    path('api/progresso/salvar/', views.api_salvar_progresso, name='api_salvar_progresso'),
    path('api/progresso/carregar/<int:aula_id>/', views.api_carregar_progresso, name='api_carregar_progresso'),
]
