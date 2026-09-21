from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0013_pdadevice_allowed_zones_pdazonealarm'),
    ]

    operations = [
        migrations.CreateModel(
            name='PdaHourlySnapshot',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hour', models.DateTimeField(db_index=True, verbose_name='整点')),
                ('mac', models.CharField(max_length=17, verbose_name='MAC')),
                ('zone', models.CharField(blank=True, default='', max_length=40, verbose_name='区域')),
                ('online', models.BooleanField(default=False, verbose_name='在线')),
            ],
            options={
                'ordering': ['hour'],
                'verbose_name': '终端每小时快照',
            },
        ),
    ]
