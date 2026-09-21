from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0008_pdascanlog_pdaheartbeathistory'),
    ]

    operations = [
        migrations.AddField(
            model_name='pdadevice',
            name='pos_x',
            field=models.FloatField(blank=True, null=True, verbose_name='平面图X%'),
        ),
        migrations.AddField(
            model_name='pdadevice',
            name='pos_y',
            field=models.FloatField(blank=True, null=True, verbose_name='平面图Y%'),
        ),
        migrations.CreateModel(
            name='PdaMapConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('floor_image', models.BinaryField(blank=True, null=True, verbose_name='平面图底图')),
                ('image_mime', models.CharField(blank=True, default='', max_length=40)),
                ('ap_coords', models.TextField(blank=True, default='[]', verbose_name='AP坐标JSON')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
