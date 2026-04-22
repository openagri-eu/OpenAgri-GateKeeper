from django.core.management.base import BaseCommand, CommandError

from aegis.services.tenant_admins import create_or_update_tenant_admin, load_tenant_admin_rows


class Command(BaseCommand):
    help = "Create or update tenant admin users in bulk from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            required=True,
            help="Path to a CSV file with tenant_code,username,email,password and optional first_name,last_name columns.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate the CSV and print the planned actions without creating users.",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        dry_run = bool(options.get("dry_run"))

        try:
            rows = load_tenant_admin_rows(csv_path)
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        if not rows:
            self.stdout.write(self.style.WARNING("No tenant admin rows were found in the CSV file."))
            return

        created_count = 0
        updated_count = 0

        for index, row in enumerate(rows, start=2):
            tenant_code = row.get("tenant_code", "")
            username = row.get("username", "")
            email = row.get("email", "")
            password = row.get("password", "")
            first_name = row.get("first_name", "")
            last_name = row.get("last_name", "")

            if dry_run:
                self.stdout.write(
                    f"DRY RUN row={index} tenant={tenant_code} username={username} email={email}"
                )
                continue

            try:
                user, tenant, created = create_or_update_tenant_admin(
                    tenant_code=tenant_code,
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )
            except CommandError as exc:
                raise CommandError(f"CSV row {index}: {exc}") from exc
            except Exception as exc:
                raise CommandError(f"CSV row {index}: {exc}") from exc

            if created:
                created_count += 1
            else:
                updated_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"{'Created' if created else 'Updated'} tenant admin '{user.username}' for tenant '{tenant.code}'."
                )
            )

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"Validated {len(rows)} tenant admin row(s)."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Tenant admin bootstrap completed: created={created_count}, updated={updated_count}."
            )
        )
