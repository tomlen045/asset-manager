from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0009_pdadevice_pos_pdamapconfig'),
    ]

    operations = [
        migrations.CreateModel(
            name='PdaAcConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ac_ip', models.CharField(blank=True, default='', max_length=60, verbose_name='AC 地址')),
                ('community', models.CharField(blank=True, default='public', max_length=60, verbose_name='SNMP 团体名')),
                ('ap_cache', models.TextField(blank=True, default='[]', verbose_name='AP缓存JSON')),
                ('last_sync', models.DateTimeField(blank=True, null=True, verbose_name='最近同步')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
