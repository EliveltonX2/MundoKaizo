from django.urls import path
from . import views

app_name = 'jogos'

urlpatterns = [
    path('', views.jogos_list_view, name='lista'),
    path('<int:jogo_id>/', views.jogar_view, name='jogar'),
    
    # APIs para salvar dados do Admin S3
    path('api/salvar-jogo/', views.api_salvar_jogo, name='api_salvar_jogo'),
    
    # API do player
    path('api/salvar-sessao/', views.api_salvar_sessao, name='api_salvar_sessao'),
    path('api/carregar-progresso/<int:jogo_id>/', views.api_carregar_progresso, name='api_carregar_progresso'),
]
