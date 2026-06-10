from django.db import migrations


def fix_computer_category_flag(apps, schema_editor):
    AssetCategory = apps.get_model("assets", "AssetCategory")
    db_alias = schema_editor.connection.alias

    AssetCategory.objects.using(db_alias).update(is_computer_category=False)
    for name in ("Computer", "Computers"):
        AssetCategory.objects.using(db_alias).filter(name__iexact=name).update(
            is_computer_category=True
        )


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0012_assetcategory_is_computer_category_and_more"),
    ]

    operations = [
        migrations.RunPython(
            fix_computer_category_flag,
            migrations.RunPython.noop,
        ),
    ]
