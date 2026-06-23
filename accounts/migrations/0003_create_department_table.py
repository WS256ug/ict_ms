from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_alter_user_role"),
    ]

    # Department is created by 0001_initial. This migration is kept as a
    # compatibility placeholder so existing deployments can record it safely.
    operations = []
