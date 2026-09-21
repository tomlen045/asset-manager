from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0011_pdadevice_device_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='pdaacconfig',
            name='nac_url',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='NAC 地址'),
        ),
        migrations.AddField(
            model_name='pdaacconfig',
            name='nac_user',
            field=models.CharField(blank=True, default='', max_length=60, verbose_name='NAC 账号'),
        ),
        migrations.AddField(
            model_name='pdaacconfig',
            name='nac_pass',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='NAC 密码'),
        ),
    ]
