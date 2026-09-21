from django.urls import path, include
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

router = DefaultRouter()
router.register('departments', DepartmentViewSet)
router.register('locations', LocationViewSet)
router.register('categories', AssetCategoryViewSet)
router.register('assets', AssetViewSet, basename='asset')
router.register('repairs', RepairOrderViewSet)
router.register('flows', AssetFlowViewSet, basename='flow')
router.register('stocktakes', StocktakeViewSet, basename='stocktake')

urlpatterns = [
    path('api/auth/login/', login),
    path('api/auth/me/', me),
    path('api/users/', user_list),
    path('api/dashboard/overview/', dashboard_overview),
    path('api/dashboard/scrappage/', scrappage_forecast),
    path('api/dashboard/scrappage_slim/', scrappage_slim),
    path('api/dept_tree/', dept_tree),
    path('api/dashboard/repairs/', dashboard_repair_stats),
    path('api/dashboard/stocktakes/', dashboard_stocktake_stats),
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
]
