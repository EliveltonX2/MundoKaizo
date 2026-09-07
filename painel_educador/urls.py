from django.urls import path
from . import views

app_name = 'painel_educador'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
]
