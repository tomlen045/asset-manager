from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0012_pdaacconfig_nac'),
    ]

    operations = [
        migrations.AddField(
            model_name='pdadevice',
            name='allowed_zones',
            field=models.JSONField(blank=True, default=list, verbose_name='允许区域'),
        ),
        migrations.AddField(
            model_name='pdadevice',
            name='linked_by',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='关联方式'),
        ),
        migrations.CreateModel(
            name='PdaZoneAlarm',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mac', models.CharField(db_index=True, max_length=17, verbose_name='MAC地址')),
                ('device_name', models.CharField(blank=True, default='', max_length=60, verbose_name='设备名称')),
                ('from_zone', models.CharField(blank=True, default='', max_length=40, verbose_name='原区域')),
                ('to_zone', models.CharField(blank=True, default='', max_length=40, verbose_name='新区域')),
                ('ap_name', models.CharField(blank=True, default='', max_length=60, verbose_name='接入点')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_read', models.BooleanField(default=False, db_index=True, verbose_name='已读')),
            ],
            options={
                'ordering': ['-created_at'],
                'verbose_name': '区域围栏告警',
            },
        ),
    ]
