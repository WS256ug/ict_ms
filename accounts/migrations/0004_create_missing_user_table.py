from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_create_department_table"),
    ]

    # User is created by 0001_initial. This migration is kept as a compatibility
    # placeholder for deployments that already include the 0004 migration name.
    operations = []
