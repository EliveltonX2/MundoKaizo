from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_ferramentas, name='ferramentas_index'),
    path('api/salvar-ferramenta/', views.salvar_registro_ferramenta, name='api_salvar_ferramenta'),
    path('<slug:slug>/', views.detalhe_ferramenta, name='ferramenta_detail'),
]
