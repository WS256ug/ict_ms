import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0005_assetactivitylog_assetassignment_assetattribute_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="asset",
            name="asset_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assets",
                to="assets.assettype",
            ),
        ),
        migrations.AlterField(
            model_name="assetlocationhistory",
            name="location",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="asset_history",
                to="assets.location",
            ),
        ),
        migrations.AlterField(
            model_name="software",
            name="name",
            field=models.CharField(max_length=150),
        ),
    ]
