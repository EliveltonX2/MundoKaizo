from django.urls import path
from . import views

app_name = 'suporte'

urlpatterns = [
    path('', views.lista_tickets, name='lista_tickets'),
    path('novo/', views.novo_ticket, name='novo_ticket'),
    path('<int:ticket_id>/', views.detalhe_ticket, name='detalhe_ticket'),
]
