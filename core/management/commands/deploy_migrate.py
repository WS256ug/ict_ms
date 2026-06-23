from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Run deployment migrations with verbose diagnostics on failure."

    def _write_exception_chain(self, exc):
        current = exc
        seen = set()
        depth = 0

        while current and id(current) not in seen:
            seen.add(id(current))
            indent = "  " * depth
            self.stderr.write(
                f"{indent}{current.__class__.__module__}."
                f"{current.__class__.__name__}: {current}"
            )

            diag = getattr(current, "diag", None)
            if diag:
                for name in (
                    "severity",
                    "sqlstate",
                    "message_primary",
                    "message_detail",
                    "message_hint",
                    "schema_name",
                    "table_name",
                    "column_name",
                    "constraint_name",
                ):
                    value = getattr(diag, name, None)
                    if value:
                        self.stderr.write(f"{indent}  {name}: {value}")

            current = getattr(current, "__cause__", None) or getattr(
                current, "__context__", None
            )
            depth += 1

    def handle(self, *args, **options):
        self.stdout.write("=== Pre-migration diagnostics ===")
        call_command("db_diagnostics", app="accounts")
        call_command("db_diagnostics", app="assets")

        self.stdout.write("\n=== Repairing stale bootstrap migration records ===")
        call_command("repair_bootstrap_migrations", "accounts", "assets")

        self.stdout.write("\n=== Post-repair diagnostics ===")
        call_command("db_diagnostics", app="accounts")
        call_command("db_diagnostics", app="assets")

        self.stdout.write("\n=== Migration plan ===")
        call_command("showmigrations", plan=True)

        self.stdout.write("\n=== Running migrate --fake-initial ===")
        try:
            call_command(
                "migrate",
                interactive=False,
                fake_initial=True,
                verbosity=2,
            )
        except Exception as exc:
            self.stderr.write("\n=== Migration failed ===")
            self._write_exception_chain(exc)

            if connection.vendor == "postgresql":
                self.stderr.write("\n=== Post-failure diagnostics ===")
                try:
                    call_command("db_diagnostics", app="accounts")
                    call_command("db_diagnostics", app="assets")
                except Exception as diagnostics_exc:
                    self.stderr.write(
                        "Diagnostics failed: "
                        f"{diagnostics_exc.__class__.__name__}: {diagnostics_exc}"
                    )

            raise
