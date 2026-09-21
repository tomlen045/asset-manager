from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0005_deptnode_src_names'),
    ]

    operations = [
        migrations.AddField(
            model_name='asset',
            name='asset_name',
            field=models.CharField(blank=True, db_index=True, max_length=100, verbose_name='设备名称'),
        ),
    ]
