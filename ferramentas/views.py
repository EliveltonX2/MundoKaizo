import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Ferramenta

def index_ferramentas(request):
    ferramentas = Ferramenta.objects.filter(ativo=True).order_by('-criado_em')
    return render(request, 'ferramentas/index.html', {'ferramentas': ferramentas})

def detalhe_ferramenta(request, slug):
    ferramenta = get_object_or_404(Ferramenta, slug=slug, ativo=True)
    return render(request, 'ferramentas/detail.html', {'ferramenta': ferramenta})

@login_required
@require_POST
def salvar_registro_ferramenta(request):
    """ Chamado pelo JS após terminar o upload de todos os arquivos no Admin """
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({'erro': 'Sem permissão.'}, status=403)
        
    try:
        nome = request.POST.get('nome')
        descricao = request.POST.get('descricao', '')
        pasta_ferramenta = request.POST.get('pasta_ferramenta')
        thumb = request.FILES.get('thumb')
        
        ferramenta = Ferramenta.objects.create(
            nome=nome,
            descricao=descricao,
            caminho_s3=f"ferramentas_web/{pasta_ferramenta}",
            thumb=thumb
        )
        return JsonResponse({'status': 'sucesso', 'ferramenta_id': ferramenta.id})
    except Exception as e:
        return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)
