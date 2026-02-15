from django.core.management.base import BaseCommand
from core.models import TokenCadastro

class Command(BaseCommand):
    help = 'Gera um lote de tokens de acesso'

    def add_arguments(self, parser):
        parser.add_argument('quantidade', type=int)
        parser.add_argument('tipo', type=str, help='ALUNO, PROFESSOR ou GESTOR_LOCAL')
        parser.add_argument('nome_lote', type=str)

    def handle(self, *args, **options):
        qtd = options['quantidade']
        tipo = options['tipo'].upper()
        lote = options['nome_lote']

        if tipo not in ['ALUNO', 'PROFESSOR', 'GESTOR_LOCAL']:
            self.stdout.write(self.style.ERROR('Tipo inválido! Use: ALUNO, PROFESSOR ou GESTOR_LOCAL'))
            return

        self.stdout.write(f'Gerando {qtd} tokens do tipo {tipo} para o lote "{lote}"...')

        tokens = [
            TokenCadastro(tipo_usuario=tipo, lote=lote)
            for _ in range(qtd)
        ]
        
        # Bulk Create é muito rápido
        TokenCadastro.objects.bulk_create(tokens)

        self.stdout.write(self.style.SUCCESS(f'Sucesso! {qtd} tokens gerados.'))
        
        # Dica: Aqui você poderia gerar um CSV ou PDF para impressão