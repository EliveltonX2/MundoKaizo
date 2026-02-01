#!/usr/bin/env bash
# Sair se der erro
set -o errexit

# 1. Instalar dependências
pip install -r requirements.txt

# 2. Coletar arquivos estáticos
python manage.py collectstatic --no-input

# 3. Aplicar migrações (Cria as tabelas)
python manage.py migrate

# --- NOVO COMANDO MÁGICO ---
# Cria o superusuário automaticamente se ele não existir
echo "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.create_superuser('admin', 'admin@email.com', 'MundoKaizo2026') if not User.objects.filter(username='admin').exists() else print('Admin já existe')" | python manage.py shell