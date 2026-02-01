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
echo "import os; from django.contrib.auth import get_user_model; User = get_user_model(); username = os.environ.get('ADMIN_USERNAME', 'admin'); email = os.environ.get('ADMIN_EMAIL', 'admin@example.com'); password = os.environ.get('ADMIN_PASSWORD'); User.objects.create_superuser(username, email, password) if password and not User.objects.filter(username=username).exists() else print('Superuser check complete')" | python manage.py shell