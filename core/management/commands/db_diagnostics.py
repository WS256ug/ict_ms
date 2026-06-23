from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Print deployment database diagnostics without modifying data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--app",
            default="assets",
            help="App label prefix to inspect. Defaults to assets.",
        )

    def handle(self, *args, **options):
        app_label = options["app"]
        prefix = f"{app_label}_"

        with connection.cursor() as cursor:
            self.stdout.write(f"Database vendor: {connection.vendor}")
            self.stdout.write(f"Database name: {connection.settings_dict.get('NAME')}")

            if "django_migrations" in connection.introspection.table_names():
                cursor.execute(
                    """
                    select app, name
                    from django_migrations
                    where app = %s
                    order by app, name
                    """,
                    [app_label],
                )
                migrations = cursor.fetchall()
            else:
                migrations = []

            self.stdout.write(f"\nRecorded migrations for {app_label}:")
            if migrations:
                for app, name in migrations:
                    self.stdout.write(f"  [x] {app}.{name}")
            else:
                self.stdout.write("  none")

            if connection.vendor != "postgresql":
                table_names = [
                    table
                    for table in connection.introspection.table_names()
                    if table.startswith(prefix)
                ]
                self.stdout.write(f"\nTables starting with {prefix}:")
                for table in table_names or ["none"]:
                    self.stdout.write(f"  {table}")
                return

            cursor.execute(
                """
                select tablename
                from pg_tables
                where schemaname = current_schema()
                  and tablename like %s
                order by tablename
                """,
                [f"{prefix}%"],
            )
            tables = [row[0] for row in cursor.fetchall()]
            self.stdout.write(f"\nTables starting with {prefix}:")
            for table in tables or ["none"]:
                self.stdout.write(f"  {table}")

            cursor.execute(
                """
                select indexname, tablename
                from pg_indexes
                where schemaname = current_schema()
                  and (tablename like %s or indexname like %s)
                order by tablename, indexname
                """,
                [f"{prefix}%", f"{prefix}%"],
            )
            indexes = cursor.fetchall()
            self.stdout.write(f"\nIndexes related to {prefix}:")
            for index, table in indexes or [("none", "")]:
                suffix = f" on {table}" if table else ""
                self.stdout.write(f"  {index}{suffix}")

            cursor.execute(
                """
                select conname, conrelid::regclass::text
                from pg_constraint
                where conrelid::regclass::text like %s
                   or conname like %s
                order by conrelid::regclass::text, conname
                """,
                [f"{prefix}%", f"{prefix}%"],
            )
            constraints = cursor.fetchall()
            self.stdout.write(f"\nConstraints related to {prefix}:")
            for constraint, table in constraints or [("none", "")]:
                suffix = f" on {table}" if table else ""
                self.stdout.write(f"  {constraint}{suffix}")
