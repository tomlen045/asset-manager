from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0006_asset_asset_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='PdaDevice',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mac', models.CharField(db_index=True, max_length=17, unique=True, verbose_name='MAC地址')),
                ('name', models.CharField(blank=True, default='', max_length=60, verbose_name='设备名称')),
                ('device_no', models.CharField(blank=True, default='', max_length=40, verbose_name='设备编号')),
                ('device_model', models.CharField(blank=True, default='', max_length=60, verbose_name='型号')),
                ('android_ver', models.CharField(blank=True, default='', max_length=20, verbose_name='Android版本')),
                ('owner', models.CharField(blank=True, default='', max_length=40, verbose_name='责任人/班组')),
                ('ap_bssid', models.CharField(blank=True, default='', max_length=32, verbose_name='关联AP(BSSID)')),
                ('ap_name', models.CharField(blank=True, default='', max_length=60, verbose_name='AP名称')),
                ('zone', models.CharField(blank=True, default='', db_index=True, max_length=40, verbose_name='所在区域')),
                ('rssi', models.IntegerField(blank=True, null=True, verbose_name='信号强度(dBm)')),
                ('ssid', models.CharField(blank=True, default='', max_length=40, verbose_name='SSID')),
                ('battery', models.IntegerField(blank=True, null=True, verbose_name='电量%')),
                ('ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP')),
                ('last_seen', models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='最后心跳')),
                ('ring_command_at', models.DateTimeField(blank=True, null=True, verbose_name='响铃指令时间')),
                ('note', models.CharField(blank=True, default='', max_length=200, verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                            to='assets.Asset', verbose_name='关联资产')),
                ('department', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 to='assets.Department', verbose_name='责任部门')),
            ],
            options={'ordering': ['-last_seen']},
        ),
    ]
