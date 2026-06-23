from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError


class Command(BaseCommand):
    help = "Create or update a deploy superuser from environment variables."

    def add_arguments(self, parser):
        parser.add_argument(
            "--required",
            action="store_true",
            help="Fail if the required superuser environment variables are missing.",
        )

    def _env_first(self, *names):
        import os

        for name in names:
            value = os.getenv(name, "").strip()
            if value:
                return value
        return ""

    def handle(self, *args, **options):
        email = self._env_first("DJANGO_SUPERUSER_EMAIL", "DJANGO_SUPERUSER_USERNAME")
        password = self._env_first("DJANGO_SUPERUSER_PASSWORD")
        first_name = self._env_first("DJANGO_SUPERUSER_FIRST_NAME") or "System"
        last_name = self._env_first("DJANGO_SUPERUSER_LAST_NAME") or "Administrator"

        if not email or not password:
            message = (
                "Skipping superuser creation; set DJANGO_SUPERUSER_EMAIL "
                "and DJANGO_SUPERUSER_PASSWORD."
            )
            if options["required"]:
                raise CommandError(message)
            self.stdout.write(self.style.WARNING(message))
            return

        User = get_user_model()
        email = User.objects.normalize_email(email)
        try:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": "ADMIN",
                    "is_staff": True,
                    "is_superuser": True,
                    "is_active": True,
                },
            )

            changed_fields = []
            for field, value in {
                "first_name": first_name,
                "last_name": last_name,
                "role": "ADMIN",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            }.items():
                if getattr(user, field) != value:
                    setattr(user, field, value)
                    changed_fields.append(field)

            if created or password:
                user.set_password(password)
                changed_fields.append("password")

            if changed_fields:
                user.save(update_fields=sorted(set(changed_fields)))
        except DatabaseError as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"Superuser creation failed: {exc.__class__.__name__}: {exc}"
                )
            )
            self.stderr.write("=== Account schema diagnostics ===")
            call_command(
                "db_diagnostics",
                app="accounts",
                verbose=True,
                stdout=self.stderr,
                stderr=self.stderr,
            )
            raise

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} deploy superuser: {email}"))
