from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0007_pdadevice'),
    ]

    operations = [
        migrations.CreateModel(
            name='PdaScanLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=10, verbose_name='动作')),
                ('person', models.CharField(max_length=40, verbose_name='经手人')),
                ('note', models.CharField(blank=True, default='', max_length=200, verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                             related_name='scan_logs', to='assets.PdaDevice',
                                             verbose_name='设备')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='PdaHeartbeatHistory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ts', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='时间')),
                ('battery', models.IntegerField(blank=True, null=True, verbose_name='电量%')),
                ('online', models.BooleanField(default=True, verbose_name='在线')),
                ('zone', models.CharField(blank=True, default='', max_length=40, verbose_name='区域')),
                ('ap_name', models.CharField(blank=True, default='', max_length=60, verbose_name='AP')),
                ('rssi', models.IntegerField(blank=True, null=True, verbose_name='信号')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                             related_name='hb_history', to='assets.PdaDevice',
                                             verbose_name='设备')),
            ],
            options={'ordering': ['-ts']},
        ),
    ]
