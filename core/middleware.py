from django.utils import timezone
from .models import RegistroAcessoDemo

class MonitoramentoDemoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated and request.user.tipo == 'DEMO':
            registro_id = request.session.get('registro_acesso_demo_id')
            agora = timezone.now()

            if registro_id:
                try:
                    registro = RegistroAcessoDemo.objects.get(id=registro_id)
                    
                    # Se passou mais de 30 minutos (1800 segundos) inativo, 
                    # consideramos que é uma NOVA sessão de navegação (ex: voltou no dia seguinte)
                    if (agora - registro.ultima_atividade).total_seconds() > 600:
                        
                        # Cria um novo registro herdando os dados físicos do anterior 
                        # (para não precisar chamar a API de IP de novo)
                        novo_registro = RegistroAcessoDemo.objects.create(
                            user=request.user,
                            ip=registro.ip,
                            localizacao=registro.localizacao,
                            dispositivo=registro.dispositivo
                        )
                        # Atualiza a sessão com o ID novo
                        request.session['registro_acesso_demo_id'] = novo_registro.id
                    else:
                        # Se faz menos de 30 min, apenas atualiza o cronômetro da sessão atual
                        registro.ultima_atividade = agora
                        registro.save(update_fields=['ultima_atividade'])
                        
                except RegistroAcessoDemo.DoesNotExist:
                    pass

        return response