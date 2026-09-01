from django.db import migrations
from django.utils.text import slugify


def importar_ferramentas_legadas(apps, schema_editor):
    FerramentaAntiga = apps.get_model('core', 'Ferramenta')
    FerramentaNova = apps.get_model('ferramentas', 'Ferramenta')

    for antiga in FerramentaAntiga.objects.all().iterator():
        base = slugify(antiga.nome) or f'ferramenta-{antiga.pk}'
        slug = base
        sufixo = 2
        while FerramentaNova.objects.filter(slug=slug).exists():
            slug = f'{base}-{sufixo}'
            sufixo += 1

        FerramentaNova.objects.create(
            nome=antiga.nome,
            slug=slug,
            descricao=antiga.descricao,
            caminho_s3=antiga.caminho_s3,
            ativo=antiga.ativo,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0038_integrar_progresso_volume3'),
        ('ferramentas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(importar_ferramentas_legadas, migrations.RunPython.noop),
    ]
