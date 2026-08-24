from .models import Ferramenta

def ferramentas_processor(request):
    """
    Context processor para injetar a lista de ferramentas ativas em todos os templates.
    Isso permite que a navbar mostre as ferramentas em qualquer página.
    """
    try:
        ferramentas = Ferramenta.objects.filter(ativo=True).order_by('nome')
    except Exception:
        # Evita erro de tabela não existente durante migrations
        ferramentas = []
        
    return {
        'ferramentas': ferramentas
    }
