from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

@login_required
def dashboard(request):
    tipos_permitidos = ['PROFESSOR', 'GESTOR_LOCAL', 'GESTOR_REGIONAL', 'GESTOR_KAIZO', 'ADMIN', 'GESTOR_GERAL']
    if request.user.tipo not in tipos_permitidos:
        raise PermissionDenied("Você não tem acesso a esta área.")
    
    return render(request, 'painel_educador/dashboard.html')
