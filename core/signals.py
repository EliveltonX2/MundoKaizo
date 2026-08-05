import requests
import datetime
from django.utils import timezone
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import RegistroAcessoDemo, EstatisticasUsuario

def atualizar_ofensiva(user):
    estatisticas, _ = EstatisticasUsuario.objects.get_or_create(user=user)
    hoje = timezone.now().date()
    
    if getattr(estatisticas, 'ultima_jogada', None) != hoje:
        # Se acessou ontem, mantém a ofensiva, senão zera
        if getattr(estatisticas, 'ultima_jogada', None) == hoje - datetime.timedelta(days=1):
            estatisticas.dias_ofensiva += 1
        else:
            estatisticas.dias_ofensiva = 1
            
        # Recorde de ofensiva
        if estatisticas.dias_ofensiva > estatisticas.maior_ofensiva:
            estatisticas.maior_ofensiva = estatisticas.dias_ofensiva
            
        estatisticas.ultima_jogada = hoje
        estatisticas.save()

@receiver(user_logged_in)
def registrar_login_universal(sender, request, user, **kwargs):
    # Atualiza a ofensiva se for aluno
    if user.tipo == 'ALUNO':
        atualizar_ofensiva(user)
        
    # 1. Pega o IP Real (mesmo atrás de proxies)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')

    # 2. Pega a Localização usando uma API gratuita (ip-api.com)
    localizacao = "Desconhecida"
    if ip and ip != '127.0.0.1': # Ignora IP local de desenvolvimento
        try:
            resp = requests.get(f'http://ip-api.com/json/{ip}?fields=city,regionName,country', timeout=3).json()
            if resp.get('country'):
                localizacao = f"{resp.get('city', '')}, {resp.get('regionName', '')} - {resp.get('country', '')}"
        except:
            pass

    # 3. Pega o Navegador/Dispositivo
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:250]

    # 4. Salva no Banco de Dados (agora para TODOS os usuários)
    registro = RegistroAcessoDemo.objects.create(
        user=user,
        ip=ip,
        localizacao=localizacao,
        dispositivo=user_agent
    )
    
    # 5. Salva o ID deste registro na sessão do usuário para o Middleware atualizar o tempo depois
    request.session['registro_acesso_demo_id'] = registro.id