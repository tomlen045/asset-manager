#!/bin/sh
set -e
cd /app/backend
python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear

# 初始管理员：仅首次启动创建，默认 admin / admin123 —— 上线前请立即修改！
export INITIAL_ADMIN_PASSWORD="${INITIAL_ADMIN_PASSWORD:-admin123}"
python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
U = get_user_model()
if not U.objects.filter(username='admin').exists():
    U.objects.create_superuser('admin', 'admin@local', os.environ['INITIAL_ADMIN_PASSWORD'])
    print('superuser created: admin')
"
exec python manage.py runserver 0.0.0.0:8091 --noreload
