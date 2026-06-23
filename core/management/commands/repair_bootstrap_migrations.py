from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = (
        "Remove stale django_migrations rows for apps whose migration history "
        "exists but whose physical app tables are absent."
    )

    def add_arguments(self, parser):
        parser.add_argument("apps", nargs="+")

    def handle(self, *args, **options):
        table_names = set(connection.introspection.table_names())
        if "django_migrations" not in table_names:
            self.stdout.write("No django_migrations table yet; nothing to repair.")
            return

        with connection.cursor() as cursor, transaction.atomic():
            for app_label in options["apps"]:
                prefix = f"{app_label}_"
                app_tables = sorted(table for table in table_names if table.startswith(prefix))

                cursor.execute(
                    """
                    select name
                    from django_migrations
                    where app = %s
                    order by name
                    """,
                    [app_label],
                )
                migration_names = [row[0] for row in cursor.fetchall()]

                if not migration_names:
                    self.stdout.write(
                        f"{app_label}: no recorded migrations; nothing to repair."
                    )
                    continue

                if app_tables:
                    self.stdout.write(
                        f"{app_label}: recorded migrations exist and physical "
                        f"tables exist; leaving migration history unchanged."
                    )
                    self.stdout.write(f"{app_label}: tables: {', '.join(app_tables)}")
                    continue

                cursor.execute(
                    "delete from django_migrations where app = %s",
                    [app_label],
                )
                self.stdout.write(
                    f"{app_label}: removed {len(migration_names)} stale migration "
                    "record(s) because no physical app tables exist."
                )
