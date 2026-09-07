from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.urls import reverse
from .models import Ticket, MensagemTicket

def is_admin(user):
    # Consideramos ADMIN ou superuser como suporte
    return user.tipo == 'ADMIN' or user.is_superuser

@login_required
def lista_tickets(request):
    if is_admin(request.user):
        tickets = Ticket.objects.all()
    else:
        tickets = Ticket.objects.filter(solicitante=request.user)
        
    # Anota a quantidade de mensagens não lidas para o usuário atual.
    # Se a mensagem tem lida=False e o autor NÃO é o usuário logado, é não lida pra ele.
    tickets = tickets.annotate(
        nao_lidas=Count('mensagens', filter=Q(mensagens__lida=False) & ~Q(mensagens__autor=request.user))
    )
    
    return render(request, 'suporte/lista.html', {'tickets': tickets, 'categorias': Ticket.CATEGORIAS})

@login_required
def novo_ticket(request):
    if request.method == 'POST':
        assunto = request.POST.get('assunto', '').strip()
        categoria = request.POST.get('categoria', '').strip()
        mensagem = request.POST.get('mensagem', '').strip()

        if assunto and categoria and mensagem:
            ticket = Ticket.objects.create(
                solicitante=request.user,
                assunto=assunto,
                categoria=categoria
            )
            MensagemTicket.objects.create(
                ticket=ticket,
                autor=request.user,
                texto=mensagem
            )
        return redirect('suporte:lista_tickets')
    return redirect('suporte:lista_tickets')

@login_required
@xframe_options_sameorigin
def detalhe_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    # Segurança de Visibilidade
    if not is_admin(request.user) and ticket.solicitante != request.user:
        raise PermissionDenied("Você não tem permissão para visualizar este ticket.")
        
    # Ao abrir, marca como lidas as mensagens onde ele não é o autor
    mensagens_nao_lidas = ticket.mensagens.filter(lida=False).exclude(autor=request.user)
    if mensagens_nao_lidas.exists():
        mensagens_nao_lidas.update(lida=True)
        
    if request.method == 'POST':
        # Bloqueio de novos chats se estiver resolvido
        if ticket.is_resolvido:
            raise PermissionDenied("Este ticket está resolvido e não aceita novas mensagens.")
        
        texto = request.POST.get('texto', '').strip()
        if texto:
            MensagemTicket.objects.create(
                ticket=ticket,
                autor=request.user,
                texto=texto
            )
            return redirect('suporte:detalhe_ticket', ticket_id=ticket.id)
            
    mensagens = ticket.mensagens.all()
    
    context = {
        'ticket': ticket,
        'mensagens': mensagens,
        'bloqueado': ticket.is_resolvido,
        'is_admin': is_admin(request.user)
    }
    return render(request, 'suporte/detalhe.html', context)
