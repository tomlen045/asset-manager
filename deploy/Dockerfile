# 资产管理系统后端镜像（amd64）—— py3.6 + Django 3.2 LTS
FROM python:3.6-slim

WORKDIR /app

# 离线安装依赖（wheels 为 x86_64/py36）
COPY deploy/wheels /tmp/wheels
RUN pip install --no-index --find-links=/tmp/wheels \
    Django==3.2.25 djangorestframework==3.14.0 \
    djangorestframework-simplejwt==4.4.0 \
    django-cors-headers==3.10.0 openpyxl==3.1.1 PyJWT==1.7.1 && \
    rm -rf /tmp/wheels

# 后端代码 + 前端 dist
COPY backend /app/backend
COPY frontend/dist /app/frontend/dist

ENV DJANGO_SETTINGS_MODULE=config.settings_prod
ENV PYTHONUNBUFFERED=1

WORKDIR /app/backend
EXPOSE 8091

# /app/data 是 SQLite 数据库目录（生产挂载宿主机卷），必须存在且可写
RUN mkdir -p /app/data /app/staticfiles

COPY deploy/docker-entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
