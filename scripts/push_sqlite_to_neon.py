#!/usr/bin/env python
"""
Copy the local SQLite database data into a Neon/Postgres database.

This script uses Django's serializers instead of raw SQL so it can move data
between SQLite and Postgres while keeping model-level relationships intact.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = ROOT / "tmp"
DEFAULT_FIXTURE = TMP_DIR / "sqlite_to_neon_data.json"
DB_ENV_NAMES = (
    "DATABASE_URL",
    "POSTGRES_URL",
    "POSTGRES_URL_NON_POOLING",
    "POSTGRES_PRISMA_URL",
    "POSTGRES_DATABASE",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "PGDATABASE",
    "PGUSER",
    "PGPASSWORD",
    "PGHOST",
    "PGPORT",
)
POSTGRES_URL_ENV_NAMES = {
    "DATABASE_URL",
    "NEON_DATABASE_URL",
    "POSTGRES_URL",
    "POSTGRES_URL_NON_POOLING",
    "POSTGRES_PRISMA_URL",
}
POSTGRES_SCHEMES = {
    "postgres",
    "postgresql",
    "pgsql",
    "postgis",
    "timescale",
    "timescalegis",
}
COMMON_DUMPDATA_ARGS = (
    "dumpdata",
    "--natural-foreign",
    "--natural-primary",
    "--exclude",
    "contenttypes",
    "--exclude",
    "auth.permission",
    "--exclude",
    "admin.logentry",
    "--exclude",
    "sessions.session",
    "--indent",
    "2",
)
COUNT_CODE = r"""
from django.apps import apps
from django.db import connection

tables = set(connection.introspection.table_names())
for model in apps.get_models():
    opts = model._meta
    if not opts.managed or opts.db_table not in tables:
        continue
    if opts.app_label in {"contenttypes", "sessions"}:
        continue
    if opts.label_lower in {"admin.logentry", "auth.permission"}:
        continue
    try:
        count = model.objects.count()
    except Exception as exc:
        count = f"ERROR:{exc.__class__.__name__}"
    print(f"{opts.label}\t{count}")
"""


def build_env_for_sqlite() -> dict[str, str]:
    env = os.environ.copy()
    for name in DB_ENV_NAMES:
        env.pop(name, None)
    env.pop("VERCEL", None)
    env.pop("VERCEL_ENV", None)
    env.setdefault("DJANGO_DEBUG", "1")
    return env


def build_env_for_target(database_url: str) -> dict[str, str]:
    env = os.environ.copy()
    for name in DB_ENV_NAMES:
        env.pop(name, None)
    env["DATABASE_URL"] = database_url
    env.setdefault("DATABASE_SSL_REQUIRE", "1")
    return env


def normalize_database_url(database_url: str) -> str:
    database_url = database_url.strip().strip('"').strip("'")
    if "=" in database_url:
        name, value = database_url.split("=", 1)
        if name.strip().upper() in POSTGRES_URL_ENV_NAMES:
            database_url = value.strip().strip('"').strip("'")
    return database_url


def validate_database_url(database_url: str) -> bool:
    parsed = urlsplit(database_url)
    if parsed.scheme.lower() not in POSTGRES_SCHEMES or not parsed.netloc:
        shown_scheme = parsed.scheme or "missing"
        print(
            "Invalid Neon/Postgres URL. It must start with postgresql:// "
            "or postgres:// and include the host and database name.\n"
            f"Detected scheme: {shown_scheme}\n\n"
            "PowerShell example:\n"
            "$env:NEON_DATABASE_URL='postgresql://USER:PASSWORD@HOST/DB?sslmode=require'\n"
            ".\\venv\\Scripts\\python.exe scripts\\push_sqlite_to_neon.py --flush-target",
            file=sys.stderr,
        )
        return False
    return True


def run_manage(args: list[str], env: dict[str, str]) -> None:
    display_args = [
        "<DATABASE_URL>" if "://" in arg and "@" in arg else arg
        for arg in args
    ]
    print("+ python manage.py " + " ".join(display_args), flush=True)
    subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=ROOT,
        env=env,
        check=True,
    )


def dump_counts(env: dict[str, str], title: str) -> None:
    print(f"\n=== {title} row counts ===", flush=True)
    run_manage(["shell", "-c", COUNT_CODE], env)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Push local db.sqlite3 data into a Neon/Postgres database."
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL") or "",
        help="Neon/Postgres connection URL. Defaults to NEON_DATABASE_URL.",
    )
    parser.add_argument(
        "--fixture",
        default=str(DEFAULT_FIXTURE),
        help="Temporary fixture path for exported SQLite data.",
    )
    parser.add_argument(
        "--flush-target",
        action="store_true",
        help="Delete target database rows before loading SQLite data.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Load SQLite data without flushing target first.",
    )
    parser.add_argument(
        "--skip-target-backup",
        action="store_true",
        help="When flushing, skip the pre-flush target dump backup.",
    )
    parser.add_argument(
        "--skip-source-dump",
        action="store_true",
        help="Reuse an existing fixture instead of exporting db.sqlite3 again.",
    )
    parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="Do not run deploy_migrate on the target before loading data.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    args.database_url = normalize_database_url(args.database_url)

    if not args.database_url:
        print(
            "Missing Neon/Postgres URL. Set NEON_DATABASE_URL or pass "
            "--database-url.",
            file=sys.stderr,
        )
        return 2
    if not validate_database_url(args.database_url):
        return 2

    if args.flush_target and args.append:
        print("Choose only one of --flush-target or --append.", file=sys.stderr)
        return 2

    if not args.flush_target and not args.append:
        print(
            "Choose --flush-target to replace Neon data, or --append to load "
            "without clearing Neon.",
            file=sys.stderr,
        )
        return 2

    sqlite_path = ROOT / "db.sqlite3"
    if not sqlite_path.exists():
        print(f"SQLite database not found: {sqlite_path}", file=sys.stderr)
        return 2

    fixture = Path(args.fixture)
    if not fixture.is_absolute():
        fixture = ROOT / fixture
    fixture.parent.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(exist_ok=True)

    sqlite_env = build_env_for_sqlite()
    target_env = build_env_for_target(args.database_url)

    dump_counts(sqlite_env, "SQLite source")

    if not args.skip_source_dump:
        run_manage([*COMMON_DUMPDATA_ARGS, "-o", str(fixture)], sqlite_env)
    elif not fixture.exists():
        print(f"Fixture does not exist: {fixture}", file=sys.stderr)
        return 2

    if not args.skip_migrate:
        run_manage(["deploy_migrate"], target_env)

    dump_counts(target_env, "Neon target before import")

    if args.flush_target:
        if not args.skip_target_backup:
            stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = TMP_DIR / f"neon_backup_before_sqlite_import_{stamp}.json"
            run_manage([*COMMON_DUMPDATA_ARGS, "-o", str(backup_path)], target_env)
            print(f"Saved target backup fixture: {backup_path}", flush=True)
        run_manage(["flush", "--noinput"], target_env)

    run_manage(["loaddata", str(fixture)], target_env)
    dump_counts(target_env, "Neon target after import")
    print("\nDone. SQLite data has been loaded into the target database.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
