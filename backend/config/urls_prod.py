"""生产 URL 配置：API + 前端 dist 静态服务 + P2 流程/盘点/大屏"""
from django.urls import path, include
from django.http import HttpResponse
from rest_framework.routers import DefaultRouter

from accounts.views import login, me, user_list
from assets.views import (DepartmentViewSet, LocationViewSet, AssetCategoryViewSet,
                          AssetViewSet, RepairOrderViewSet, dashboard_overview,
                          scrappage_forecast, scrappage_slim)
from assets.flows_views import AssetFlowViewSet, StocktakeViewSet
from assets.bigscreen import (bigscreen_data, dashboard_repair_stats,
                              dashboard_stocktake_stats, dept_tree)
from assets.reports import (repair_template, repair_batch_import,
                            export_assets, export_scrappage)
from assets.economy_chart import economy_chart
from assets.ai_report import ai_report, ai_report_status, ai_report_batch
from assets.pda import (pda_heartbeat, pda_devices, pda_update, pda_bulk_delete,
                        pda_ring, pda_bulk_import, pda_import_template, pda_ac_test,
                        pda_ac_script, pda_track, pda_map_data, pda_map_upload, pda_map_save)
from assets.pda_extra import (pda_labels, pda_scan_lookup, pda_scan_log,
                              pda_scan_logs, pda_history, pda_guide, pda_sundray_csv,
                              pda_snmp_test, pda_snmp_sync, pda_snmp_config, pda_snmp_aps,
                              pda_nac_test, pda_nac_sync, pda_nac_config, pda_nac_import,
                              pda_link_assets, pda_zone_alarms, pda_zone_alarms_read, pda_bulk_zone,
                              pda_online_report, pda_snapshot_tick, pda_bulk_enrich_preview, pda_bulk_enrich_apply,
                              pda_bigscreen)
import os

router = DefaultRouter()
router.register('departments', DepartmentViewSet)
router.register('locations', LocationViewSet)
router.register('categories', AssetCategoryViewSet)
router.register('assets', AssetViewSet, basename='asset')
router.register('repairs', RepairOrderViewSet)
router.register('flows', AssetFlowViewSet, basename='flow')
router.register('stocktakes', StocktakeViewSet, basename='stocktake')

DIST = '/app/frontend/dist'


def spa(request, path='index.html'):
    """SPA fallback：先按完整 URL 路径找静态文件，找不到回退 index.html
    性能：带 hash 的 assets 走一年强缓存；文本类型 gzip（862KB JS → ~250KB）"""
    import gzip as _gzip
    rel = request.path.lstrip('/')
    full = os.path.join(DIST, rel)
    if not os.path.isfile(full):
        full = os.path.join(DIST, 'index.html')
    ctype = 'text/html'
    if path.endswith('.js') or request.path.endswith('.js'):
        ctype = 'application/javascript'
    elif request.path.endswith('.css'):
        ctype = 'text/css'
    elif request.path.endswith('.svg'):
        ctype = 'image/svg+xml'
    elif request.path.endswith('.png'):
        ctype = 'image/png'
    with open(full, 'rb') as f:
        body = f.read()

    resp = None
    # ETag 协商缓存（文件未变 → 304 不传 body）
    import hashlib
    etag = '"' + hashlib.md5(body).hexdigest() + '"'
    if request.META.get('HTTP_IF_NONE_MATCH') == etag:
        resp = HttpResponse(status=304)
    else:
        ae = request.META.get('HTTP_ACCEPT_ENCODING', '')
        # vite 产物文件名带内容 hash（index-XXXX.js）→ 一年强缓存；index.html 不缓存
        is_hashed = '/assets/' in request.path
        if 'gzip' in ae and len(body) > 1024 and (
                ctype.startswith(('text/', 'application/javascript', 'image/svg'))):
            body = _gzip.compress(body, 6)
            resp = HttpResponse(body, content_type=ctype)
            resp['Content-Encoding'] = 'gzip'
        else:
            resp = HttpResponse(body, content_type=ctype)
        if is_hashed:
            resp['Cache-Control'] = 'public, max-age=31536000, immutable'
        else:
            resp['Cache-Control'] = 'no-cache'   # index.html 每次协商，拿最新 hash 引用
    resp['ETag'] = etag
    resp['Vary'] = 'Accept-Encoding'
    return resp


urlpatterns = [
    path('api/auth/login/', login),
    path('api/auth/me/', me),
    path('api/users/', user_list),
    path('api/dept_tree/', dept_tree),
    path('api/dashboard/overview/', dashboard_overview),
    path('api/dashboard/scrappage/', scrappage_forecast),
    path('api/dashboard/scrappage_slim/', scrappage_slim),
    path('api/dashboard/repairs/', dashboard_repair_stats),
    path('api/dashboard/stocktakes/', dashboard_stocktake_stats),
    # 大屏聚合必须放在 api/ include 之前？不——问题在 catch-all '<path:path>' 匹配了 api/bigscreen/
    # 因为 DefaultRouter 生成的 URL 全部带尾斜杠，/api/bigscreen/ 没有 router 路由 → 落到 catch-all
    path('api/bigscreen/', bigscreen_data),
    path('api/repairs/import_template/', repair_template),
    path('api/repairs/batch_import/', repair_batch_import),
    path('api/export/assets/', export_assets),
    path('api/export/scrappage/', export_scrappage),
    path('api/assets/<int:pk>/economy_chart/', economy_chart),
    path('api/assets/<int:pk>/ai_report/', ai_report),
    path('api/assets/<int:pk>/ai_report_status/', ai_report_status),
    path('api/ai_report_batch/', ai_report_batch),
    path('api/pda/heartbeat/', pda_heartbeat),
    path('api/pda/devices/', pda_devices),
    path('api/pda/devices/<int:pk>/update/', pda_update),
    path('api/pda/devices/<int:pk>/ring/', pda_ring),
    path('api/pda/import/', pda_bulk_import),
    path('api/pda/import_template/', pda_import_template),
    path('api/pda/delete/', pda_bulk_delete),
    path('api/pda/labels/', pda_labels),
    path('api/pda/sundray/csv/', pda_sundray_csv),
    path('api/pda/snmp/test/', pda_snmp_test),
    path('api/pda/snmp/sync/', pda_snmp_sync),
    path('api/pda/snmp/config/', pda_snmp_config),
    path('api/pda/snmp/aps/', pda_snmp_aps),
    path('api/pda/nac/test/', pda_nac_test),
    path('api/pda/nac/sync/', pda_nac_sync),
    path('api/pda/nac/config/', pda_nac_config),
    path('api/pda/nac/import/', pda_nac_import),
    path('api/pda/link_assets/', pda_link_assets),
    path('api/pda/zone_alarms/', pda_zone_alarms),
    path('api/pda/zone_alarms/read/', pda_zone_alarms_read),
    path('api/pda/bulk_zone/', pda_bulk_zone),
    path('api/pda/online_report/', pda_online_report),
    path('api/pda/snapshot_tick/', pda_snapshot_tick),
    path('api/pda/bulk_enrich/preview/', pda_bulk_enrich_preview),
    path('api/pda/bulk_enrich/apply/', pda_bulk_enrich_apply),
    path('api/pda/bigscreen/', pda_bigscreen),
    path('api/pda/scan/lookup/', pda_scan_lookup),
    path('api/pda/scan/log/', pda_scan_log),
    path('api/pda/scan/logs/', pda_scan_logs),
    path('api/pda/devices/<int:pk>/history/', pda_history),
    path('api/pda/guide/', pda_guide),
    path('api/pda/map/', pda_map_data),
    path('api/pda/map/upload/', pda_map_upload),
    path('api/pda/map/save/', pda_map_save),
    path('api/pda/ac/test/', pda_ac_test),
    path('api/pda/ac/script/', pda_ac_script),
    path('api/pda/devices/<int:pk>/track/', pda_track),
    path('api/', include(router.urls)),
    # vite 构建的静态资源目录（必须先于 SPA fallback 匹配）
    path('assets/<path:path>', spa),
    path('static/<path:path>', spa),
    path('favicon.svg', spa),
    path('icons.svg', spa),
    # SPA 路由
    path('', spa),
    path('<path:path>', spa),
]
