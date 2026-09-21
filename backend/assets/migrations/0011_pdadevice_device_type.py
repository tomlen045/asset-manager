from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0010_pdaacconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='pdadevice',
            name='device_type',
            field=models.CharField(blank=True, default='pda', max_length=10, verbose_name='设备类型'),
        ),
    ]
