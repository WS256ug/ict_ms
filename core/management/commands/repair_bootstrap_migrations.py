from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


REQUIRED_INITIAL_TABLES = {
    "accounts": {"accounts_department", "accounts_user"},
    "assets": {"assets_asset", "assets_assetcategory"},
}

REQUIRED_TABLE_COLUMNS = {
    "accounts_department": {
        "id",
        "name",
        "code",
        "description",
        "created_at",
        "updated_at",
    },
    "accounts_user": {
        "id",
        "password",
        "is_superuser",
        "email",
        "first_name",
        "last_name",
        "phone_number",
        "role",
        "department_id",
        "is_active",
        "is_staff",
        "date_joined",
        "last_login",
    },
}

INCOMPATIBLE_TABLE_COLUMNS = {
    "accounts_user": {"username"},
}

DEPENDENT_APPS = {
    "accounts": (
        "admin",
        "assets",
        "checkouts",
        "tickets",
        "maintenance",
        "iot_monitoring",
        "notifications",
    ),
    "assets": (
        "checkouts",
        "tickets",
        "maintenance",
        "iot_monitoring",
        "notifications",
    ),
}

EXACT_APP_TABLES = {
    "admin": {"django_admin_log"},
}


class Command(BaseCommand):
    help = (
        "Remove stale django_migrations rows for apps whose migration history "
        "exists but whose physical app tables are absent."
    )

    def _table_count(self, cursor, table_name):
        quoted_table = connection.ops.quote_name(table_name)
        cursor.execute(f"select count(*) from {quoted_table}")
        return cursor.fetchone()[0]

    def _drop_empty_tables(self, cursor, app_label, table_names):
        non_empty = []
        for table_name in table_names:
            row_count = self._table_count(cursor, table_name)
            if row_count:
                non_empty.append((table_name, row_count))

        if non_empty:
            details = ", ".join(
                f"{table} has {row_count} row(s)"
                for table, row_count in non_empty
            )
            raise CommandError(
                f"{app_label}: cannot auto-repair because existing app tables "
                f"contain data: {details}"
            )

        for table_name in table_names:
            quoted_table = connection.ops.quote_name(table_name)
            cascade = " cascade" if connection.vendor == "postgresql" else ""
            cursor.execute(f"drop table {quoted_table}{cascade}")
            self.stdout.write(f"{app_label}: dropped empty table {table_name}.")

    def _table_columns(self, cursor, table_name):
        description = connection.introspection.get_table_description(cursor, table_name)
        return {column.name for column in description}

    def _quote(self, name):
        return connection.ops.quote_name(name)

    def _add_column_if_missing(self, cursor, table_name, column_name, definition):
        if column_name in self._table_columns(cursor, table_name):
            return
        cursor.execute(
            f"alter table {self._quote(table_name)} "
            f"add column {self._quote(column_name)} {definition}"
        )
        self.stdout.write(f"{table_name}: added missing column {column_name}.")

    def _drop_column_if_exists(self, cursor, table_name, column_name):
        if column_name not in self._table_columns(cursor, table_name):
            return
        suffix = " cascade" if connection.vendor == "postgresql" else ""
        cursor.execute(
            f"alter table {self._quote(table_name)} "
            f"drop column {self._quote(column_name)}{suffix}"
        )
        self.stdout.write(f"{table_name}: dropped legacy column {column_name}.")

    def _repair_accounts_in_place(self, cursor, table_names, reason):
        if not {"accounts_department", "accounts_user"}.issubset(set(table_names)):
            return False

        self.stdout.write(f"accounts: attempting in-place schema repair: {reason}")

        timestamp_type = (
            "timestamp with time zone"
            if connection.vendor == "postgresql"
            else "datetime"
        )
        now_sql = "NOW()" if connection.vendor == "postgresql" else "CURRENT_TIMESTAMP"
        id_text = "id::text" if connection.vendor == "postgresql" else "CAST(id AS text)"

        self._add_column_if_missing(
            cursor, "accounts_department", "code", "varchar(20)"
        )
        self._add_column_if_missing(
            cursor, "accounts_department", "description", "text"
        )
        self._add_column_if_missing(
            cursor, "accounts_department", "created_at", timestamp_type
        )
        self._add_column_if_missing(
            cursor, "accounts_department", "updated_at", timestamp_type
        )
        cursor.execute(
            f"""
            update accounts_department
            set code = 'DEPT-' || {id_text}
            where code is null or code = ''
            """
        )
        cursor.execute(
            f"""
            update accounts_department
            set created_at = {now_sql}
            where created_at is null
            """
        )
        cursor.execute(
            f"""
            update accounts_department
            set updated_at = {now_sql}
            where updated_at is null
            """
        )
        cursor.execute(
            """
            create unique index if not exists accounts_department_code_unique
            on accounts_department(code)
            """
        )

        self._add_column_if_missing(cursor, "accounts_user", "password", "varchar(128)")
        self._add_column_if_missing(
            cursor,
            "accounts_user",
            "is_superuser",
            "boolean default false"
            if connection.vendor == "postgresql"
            else "bool default 0",
        )
        self._add_column_if_missing(cursor, "accounts_user", "email", "varchar(255)")
        self._add_column_if_missing(
            cursor, "accounts_user", "first_name", "varchar(100)"
        )
        self._add_column_if_missing(
            cursor, "accounts_user", "last_name", "varchar(100)"
        )
        self._add_column_if_missing(
            cursor, "accounts_user", "phone_number", "varchar(20)"
        )
        self._add_column_if_missing(cursor, "accounts_user", "role", "varchar(20)")
        self._add_column_if_missing(cursor, "accounts_user", "department_id", "bigint")
        self._add_column_if_missing(
            cursor,
            "accounts_user",
            "is_active",
            "boolean default true"
            if connection.vendor == "postgresql"
            else "bool default 1",
        )
        self._add_column_if_missing(
            cursor,
            "accounts_user",
            "is_staff",
            "boolean default false"
            if connection.vendor == "postgresql"
            else "bool default 0",
        )
        self._add_column_if_missing(
            cursor, "accounts_user", "date_joined", timestamp_type
        )
        self._add_column_if_missing(
            cursor, "accounts_user", "last_login", timestamp_type
        )

        user_columns = self._table_columns(cursor, "accounts_user")
        if "username" in user_columns:
            username_email_expr = (
                "case when username is not null and position('@' in username) > 1 "
                "then username else 'user' || id::text || '@example.com' end"
                if connection.vendor == "postgresql"
                else "case when username is not null and instr(username, '@') > 1 "
                "then username else 'user' || CAST(id AS text) || '@example.com' end"
            )
        else:
            username_email_expr = f"'user' || {id_text} || '@example.com'"

        cursor.execute(
            f"""
            update accounts_user
            set email = {username_email_expr}
            where email is null or email = ''
            """
        )
        cursor.execute(
            "update accounts_user set first_name = 'User' "
            "where first_name is null or first_name = ''"
        )
        cursor.execute(
            f"""
            update accounts_user
            set last_name = 'Account ' || {id_text}
            where last_name is null or last_name = ''
            """
        )
        cursor.execute(
            "update accounts_user set password = '!' "
            "where password is null or password = ''"
        )
        cursor.execute(
            f"""
            update accounts_user
            set date_joined = {now_sql}
            where date_joined is null
            """
        )
        cursor.execute(
            """
            update accounts_user
            set role = 'ADMIN'
            where is_superuser = true
              and (role is null or role = '' or role = 'USER')
            """
            if connection.vendor == "postgresql"
            else """
            update accounts_user
            set role = 'ADMIN'
            where is_superuser = 1
              and (role is null or role = '' or role = 'USER')
            """
        )
        cursor.execute(
            """
            update accounts_user
            set role = 'DEPARTMENT_USER'
            where role is null or role = '' or role = 'USER'
            """
        )
        cursor.execute(
            """
            create unique index if not exists accounts_user_email_unique
            on accounts_user(email)
            """
        )
        cursor.execute(
            """
            create index if not exists accounts_user_department_id_idx
            on accounts_user(department_id)
            """
        )

        if connection.vendor == "postgresql":
            cursor.execute(
                """
                do $$
                begin
                    if not exists (
                        select 1
                        from pg_constraint
                        where conname = 'accounts_user_department_id_fk'
                    ) then
                        alter table accounts_user
                        add constraint accounts_user_department_id_fk
                        foreign key (department_id)
                        references accounts_department(id)
                        deferrable initially deferred;
                    end if;
                end $$;
                """
            )

        self._drop_column_if_exists(cursor, "accounts_user", "username")

        remaining_problems = self._schema_problems(
            cursor,
            self._app_tables(set(connection.introspection.table_names()), "accounts"),
            "accounts",
        )
        if remaining_problems:
            self.stdout.write(
                "accounts: in-place repair incomplete: "
                + "; ".join(remaining_problems)
            )
            return False

        self.stdout.write("accounts: in-place schema repair completed.")
        return True

    def _schema_problems(self, cursor, table_names, app_label):
        problems = []
        app_table_set = set(table_names)

        for table_name, required_columns in REQUIRED_TABLE_COLUMNS.items():
            if table_name not in app_table_set:
                continue
            if not table_name.startswith(f"{app_label}_"):
                continue

            columns = self._table_columns(cursor, table_name)
            missing_columns = sorted(required_columns - columns)
            if missing_columns:
                problems.append(
                    f"{table_name} missing column(s): {', '.join(missing_columns)}"
                )

            incompatible_columns = sorted(
                INCOMPATIBLE_TABLE_COLUMNS.get(table_name, set()) & columns
            )
            if incompatible_columns:
                problems.append(
                    f"{table_name} has incompatible legacy column(s): "
                    f"{', '.join(incompatible_columns)}"
                )

        return problems

    def _app_tables(self, table_names, app_label):
        exact_tables = EXACT_APP_TABLES.get(app_label, set())
        prefix = f"{app_label}_"
        return sorted(
            table
            for table in table_names
            if table in exact_tables or table.startswith(prefix)
        )

    def _migration_names(self, cursor, app_label):
        cursor.execute(
            """
            select name
            from django_migrations
            where app = %s
            order by name
            """,
            [app_label],
        )
        return [row[0] for row in cursor.fetchall()]

    def _dependent_apps(self, app_labels):
        seen = set(app_labels)
        queue = list(app_labels)
        dependents = []

        while queue:
            app_label = queue.pop(0)
            for dependent in DEPENDENT_APPS.get(app_label, ()):
                if dependent in seen:
                    continue
                seen.add(dependent)
                dependents.append(dependent)
                queue.append(dependent)

        return dependents

    def _reset_app(self, cursor, table_names, app_label, reason):
        app_tables = self._app_tables(table_names, app_label)
        migration_names = self._migration_names(cursor, app_label)

        if not app_tables and not migration_names:
            self.stdout.write(f"{app_label}: {reason}; nothing to reset.")
            return table_names

        self.stdout.write(f"{app_label}: {reason}")

        if app_tables:
            self._drop_empty_tables(cursor, app_label, app_tables)

        if migration_names:
            cursor.execute(
                "delete from django_migrations where app = %s",
                [app_label],
            )
            self.stdout.write(
                f"{app_label}: removed {len(migration_names)} migration record(s)."
            )
        else:
            self.stdout.write(f"{app_label}: no migration records to remove.")

        return set(connection.introspection.table_names())

    def add_arguments(self, parser):
        parser.add_argument("apps", nargs="+")

    def handle(self, *args, **options):
        table_names = set(connection.introspection.table_names())
        if "django_migrations" not in table_names:
            self.stdout.write("No django_migrations table yet; nothing to repair.")
            return

        reset_roots = []
        forced_dependents = set()

        with connection.cursor() as cursor, transaction.atomic():
            for app_label in options["apps"]:
                if app_label in forced_dependents:
                    continue

                app_tables = self._app_tables(table_names, app_label)
                required_tables = REQUIRED_INITIAL_TABLES.get(app_label, set())
                missing_required_tables = sorted(required_tables - set(app_tables))
                migration_names = self._migration_names(cursor, app_label)
                schema_problems = self._schema_problems(cursor, app_tables, app_label)

                if not migration_names:
                    self.stdout.write(
                        f"{app_label}: no recorded migrations; nothing to repair."
                    )
                    continue

                if missing_required_tables:
                    table_names = self._reset_app(
                        cursor,
                        table_names,
                        app_label,
                        "missing required initial table(s): "
                        f"{', '.join(missing_required_tables)}",
                    )
                    reset_roots.append(app_label)
                    forced_dependents.update(self._dependent_apps([app_label]))
                    continue

                if schema_problems:
                    if app_label == "accounts" and self._repair_accounts_in_place(
                        cursor,
                        table_names,
                        "incompatible table schema: " + "; ".join(schema_problems),
                    ):
                        table_names = set(connection.introspection.table_names())
                        continue

                    table_names = self._reset_app(
                        cursor,
                        table_names,
                        app_label,
                        "incompatible table schema: " + "; ".join(schema_problems),
                    )
                    reset_roots.append(app_label)
                    forced_dependents.update(self._dependent_apps([app_label]))
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
                reset_roots.append(app_label)
                forced_dependents.update(self._dependent_apps([app_label]))

            for app_label in self._dependent_apps(reset_roots):
                table_names = self._reset_app(
                    cursor,
                    table_names,
                    app_label,
                    "reset because it depends on repaired app schema",
                )
