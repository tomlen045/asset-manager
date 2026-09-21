"""
生产部署配置：
- 关 DEBUG
- ALLOWED_HOSTS = ['*']
- 静态文件由 collectstatic 收集后由 Django 自身服务（小流量场景够用）
- SQLite 独立库 /app/data/asset_db.sqlite3（挂载宿主机卷持久化）
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'please-change-me-in-prod')
DEBUG = False
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'accounts',
    'assets',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

# whitenoise 未安装时上面的中间件会报错——为避免额外依赖，这里改用 Django 内置静态服务：
MIDDLEWARE = [m for m in MIDDLEWARE if 'whitenoise' not in m]

ROOT_URLCONF = 'config.urls_prod'

# ── 统计口径开关：只统计这些资产类别（None = 全部类别）──
# 按本单位资产分类体系填写类别编码后即可启用口径过滤
# 影响范围：工作台全部面板、报废预测/经济寿命模型、数据大屏、台账列表
# 注意：只影响「统计与列表口径」，数据库数据一条不删，改回 None 即恢复全量统计
# 统计口径：只统计这些类别编码（None = 全部）。按本单位资产分类体系配置
STATS_CATEGORY_CODES = None

AUTH_USER_MODEL = 'accounts.User'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

WSGI_APPLICATION = 'config.wsgi_prod.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': Path('/app/data/asset_db.sqlite3'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 6}},
]

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = Path('/app/staticfiles')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',),
    'DEFAULT_PAGINATION_CLASS': 'config.pagination.DefaultPagination',
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DATETIME_FORMAT': '%Y-%m-%d %H:%M:%S',
}

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=12),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

CORS_ALLOW_ALL_ORIGINS = True

# ── P4 AI 报告（Ollama 内网服务）──
OLLAMA_BASE = os.environ.get('OLLAMA_BASE', 'http://ollama:11434')  # AI 报告服务地址
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen2.5:7b')
OLLAMA_TIMEOUT = 480

from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 500


# ── 移动设备（PDA）定位 ──
import os as _os
PDA_HEARTBEAT_TOKEN = os.environ.get('PDA_HEARTBEAT_TOKEN', 'change-me-pda-token')
PDA_MQTT_HOST = _os.environ.get('PDA_MQTT_HOST', '127.0.0.1')
PDA_MQTT_PORT = 1883
PDA_MQTT_USER = ''
PDA_MQTT_PASS = ''
PDA_AC_CONFIG = {'AC_HOST': '', 'AC_PORT': '22', 'AC_USER': 'admin', 'AC_PASS': ''}
