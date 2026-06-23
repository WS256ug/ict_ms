from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_create_missing_user_table"),
    ]

    # Account table repair is handled before migrate by deploy_migrate. Keeping
    # this migration empty avoids duplicate schema operations in normal migrate.
    operations = []
