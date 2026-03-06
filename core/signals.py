import requests
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import RegistroAcessoDemo

@receiver(user_logged_in)
def registrar_login_demo(sender, request, user, **kwargs):
    # Só nos importamos se for conta DEMO
    if user.tipo == 'DEMO':
        
        # 1. Pega o IP Real (mesmo se estiver atrás de proxies como Cloudflare/Render)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

        # 2. Pega a Localização usando uma API gratuita (ip-api.com)
        localizacao = "Desconhecida"
        if ip and ip != '127.0.0.1': # Ignora IP local de desenvolvimento
            try:
                # Retorna Cidade, Estado - País
                resp = requests.get(f'http://ip-api.com/json/{ip}?fields=city,regionName,country', timeout=3).json()
                if resp.get('country'):
                    localizacao = f"{resp.get('city', '')}, {resp.get('regionName', '')} - {resp.get('country', '')}"
            except:
                pass # Se a API falhar, não trava o login do usuário

        # 3. Pega o Navegador/Dispositivo
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:250]

        # 4. Salva no Banco de Dados
        registro = RegistroAcessoDemo.objects.create(
            user=user,
            ip=ip,
            localizacao=localizacao,
            dispositivo=user_agent
        )
        
        # 5. Salva o ID deste registro na sessão do usuário para o Middleware atualizar o tempo depois
        request.session['registro_acesso_demo_id'] = registro.id