from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_create_missing_user_table"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE accounts_department
            ADD COLUMN IF NOT EXISTS code varchar(20);

            ALTER TABLE accounts_department
            ADD COLUMN IF NOT EXISTS description text;

            ALTER TABLE accounts_department
            ADD COLUMN IF NOT EXISTS created_at timestamp with time zone DEFAULT NOW();

            ALTER TABLE accounts_department
            ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone DEFAULT NOW();

            UPDATE accounts_department
            SET code = 'DEPT-' || id
            WHERE code IS NULL OR code = '';

            ALTER TABLE accounts_department
            ALTER COLUMN code SET NOT NULL;

            CREATE UNIQUE INDEX IF NOT EXISTS accounts_department_code_unique
            ON accounts_department(code);


            ALTER TABLE accounts_user
            ADD COLUMN IF NOT EXISTS email varchar(255);

            UPDATE accounts_user
            SET email = username
            WHERE email IS NULL AND username IS NOT NULL;

            UPDATE accounts_user
            SET email = 'user' || id || '@example.com'
            WHERE email IS NULL OR email = '';

            ALTER TABLE accounts_user
            ALTER COLUMN email SET NOT NULL;

            CREATE UNIQUE INDEX IF NOT EXISTS accounts_user_email_unique
            ON accounts_user(email);


            ALTER TABLE accounts_user
            ADD COLUMN IF NOT EXISTS phone_number varchar(20);

            ALTER TABLE accounts_user
            ADD COLUMN IF NOT EXISTS department_id bigint;

            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'accounts_user_department_id_fk'
                ) THEN
                    ALTER TABLE accounts_user
                    ADD CONSTRAINT accounts_user_department_id_fk
                    FOREIGN KEY (department_id)
                    REFERENCES accounts_department(id)
                    DEFERRABLE INITIALLY DEFERRED;
                END IF;
            END $$;

            CREATE INDEX IF NOT EXISTS accounts_user_department_id_idx
            ON accounts_user(department_id);
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]