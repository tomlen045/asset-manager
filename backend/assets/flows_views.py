"""P2-1/P2-2 流程与盘点 API 视图"""
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers

from .flows import AssetFlow, Stocktake, StocktakeItem


class AssetFlowSerializer(serializers.ModelSerializer):
    asset_tag = serializers.CharField(source='asset.asset_tag', read_only=True)
    # 台账口径的资产编号（sn 即原始台账表格的「资产号」，如 NBB-2805/BG001-861）
    asset_display = serializers.SerializerMethodField()
    asset_name = serializers.SerializerMethodField()
    to_user_name = serializers.CharField(source='to_user.username', read_only=True, default='')
    to_department_name = serializers.CharField(source='to_department.name', read_only=True, default='')
    applicant_name = serializers.CharField(source='applicant.username', read_only=True)
    approver_name = serializers.CharField(source='approver.username', read_only=True, default='')

    class Meta:
        model = AssetFlow
        fields = '__all__'
        read_only_fields = ['flow_no', 'applicant', 'approver', 'status',
                            'approve_remark', 'finished_at']

    def get_asset_name(self, obj):
        return f'{obj.asset.brand} {obj.asset.model_spec}'

    def get_asset_display(self, obj):
        return obj.asset.sn or obj.asset.asset_tag


class AssetFlowViewSet(viewsets.ModelViewSet):
    queryset = AssetFlow.objects.select_related(
        'asset', 'to_user', 'to_department', 'to_location',
        'applicant', 'approver')
    serializer_class = AssetFlowSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        st = self.request.query_params.get('status')
        if st:
            qs = qs.filter(status=st)
        ft = self.request.query_params.get('flow_type')
        if ft:
            qs = qs.filter(flow_type=ft)
        return qs

    def perform_create(self, serializer):
        # 自动生成流程单号 LC-{类型}-{日期}-{流水}
        from django.utils import timezone
        ft = serializer.validated_data.get('flow_type', 'assign')
        d = timezone.localdate().strftime('%Y%m%d')
        prefix = f'LC-{ft.upper()}-{d}-'
        seq = AssetFlow.objects.filter(flow_no__startswith=prefix).count() + 1
        instance = serializer.save(flow_no=f'{prefix}{seq:03d}',
                                   applicant=self.request.user)
        # 领用/调拨单自动填当前持有人信息缺省
        return instance

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        flow = self.get_object()
        if flow.status != 'pending':
            return Response({'error': '流程已处理'}, status=400)
        if flow.applicant_id == request.user.id and not request.user.is_superuser:
            return Response({'error': '不能审批自己的申请'}, status=403)
        flow.approve(request.user, request.data.get('remark', ''))
        return Response(AssetFlowSerializer(flow).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        flow = self.get_object()
        if flow.status != 'pending':
            return Response({'error': '流程已处理'}, status=400)
        flow.reject(request.user, request.data.get('remark', '驳回'))
        return Response(AssetFlowSerializer(flow).data)


class StocktakeSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source='created_by.username', read_only=True)
    stats = serializers.SerializerMethodField()

    class Meta:
        model = Stocktake
        fields = ['id', 'name', 'status', 'creator_name', 'created_at',
                  'finished_at', 'category', 'department', 'custom_filter', 'stats']

    def get_stats(self, obj):
        return obj.stats()


class StocktakeViewSet(viewsets.ModelViewSet):
    queryset = Stocktake.objects.prefetch_related('items')
    serializer_class = StocktakeSerializer

    def perform_create(self, serializer):
        st = serializer.save(created_by=self.request.user)
        # 生成本次范围明细快照
        from assets.models import LifecycleLog
        for a in st.scope_queryset():
            StocktakeItem.objects.get_or_create(stocktake=st, asset=a)

    @action(detail=True, methods=['post'])
    def scan(self, request, pk=None):
        """扫码确认：body {code: 资产编号或序列号, location?: 实盘位置}"""
        st = self.get_object()
        if st.status != 'ongoing':
            return Response({'error': '任务已结束'}, status=400)
        code = (request.data.get('code') or '').strip()
        if not code:
            return Response({'error': '扫码内容为空'}, status=400)

        from assets.models import Asset
        asset = None
        # 1. 任务范围内找
        try:
            item = st.items.select_related('asset').get(
                Q_asset_tag__asset_tag=code) if False else None
        except Exception:
            item = None
        # 兼容：编号或序列号
        item = st.items.select_related('asset').filter(
            asset__asset_tag=code).first() or \
            st.items.select_related('asset').filter(asset__sn=code).first()
        if item:
            item.found = True
            item.found_at = timezone.now()
            item.found_location = request.data.get('location', '')
            item.save()
            return Response({'result': 'found',
                             'asset_tag': item.asset.asset_tag,
                             'name': f'{item.asset.brand} {item.asset.model_spec}',
                             'status': item.asset.status})

        # 2. 账外资产（扫到但不在范围）
        asset = Asset.objects.filter(Q_tag(code)).first()
        if asset:
            StocktakeItem.objects.create(stocktake=st, asset=asset,
                                         found=True, unexpected=True,
                                         found_at=timezone.now(),
                                         found_location=request.data.get('location', ''))
            return Response({'result': 'unexpected',
                             'asset_tag': asset.asset_tag,
                             'name': f'{asset.brand} {asset.model_spec}'})
        return Response({'result': 'not_found', 'code': code}, status=404)

    @action(detail=True, methods=['post'])
    def finish(self, request, pk=None):
        st = self.get_object()
        st.status = 'finished'
        st.finished_at = timezone.now()
        st.save()
        return Response(StocktakeSerializer(st).data)

    @action(detail=True, methods=['get'])
    def diff(self, request, pk=None):
        """差异报表：未盘到 + 账外"""
        st = self.get_object()
        missing = (st.scope_queryset().exclude(
            id__in=st.items.filter(found=True).values('asset_id'))
            .values('asset_tag', 'sn', 'brand', 'model_spec', 'status'))
        unexpected = (st.items.filter(unexpected=True)
                      .select_related('asset')
                      .values('asset__asset_tag', 'asset__brand',
                              'asset__model_spec', 'found_location'))
        return Response({'missing_list': list(missing),
                         'unexpected_list': list(unexpected), **st.stats()})


def Q_tag(code):
    return (Q(asset_tag=code) | Q(sn=code))
