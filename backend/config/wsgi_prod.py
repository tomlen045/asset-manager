"""生产 WSGI"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_prod')

application = get_wsgi_application()

# 启动后台预计算线程（报废分析每8分钟自动刷新）
try:
    from assets.views import _scrappage_bg_refresh
    _scrappage_bg_refresh()
except Exception:
    pass
