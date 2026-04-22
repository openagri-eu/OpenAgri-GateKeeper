from django.core.management.base import BaseCommand, CommandError

from aegis.services.tenant_admins import create_or_update_tenant_admin


class Command(BaseCommand):
    help = "Create or promote a tenant admin user inside GK for a specific tenant."

    def add_arguments(self, parser):
        parser.add_argument("tenant_code", type=str, help="Tenant code, e.g. sip06")
        parser.add_argument("username", type=str, help="Username for the tenant admin")
        parser.add_argument("email", type=str, help="Email for the tenant admin")
        parser.add_argument("password", type=str, help="Password for the tenant admin")
        parser.add_argument("--first-name", dest="first_name", default="", help="Optional first name")
        parser.add_argument("--last-name", dest="last_name", default="", help="Optional last name")

    def handle(self, *args, **options):
        try:
            user, tenant, created = create_or_update_tenant_admin(
                tenant_code=options["tenant_code"],
                username=options["username"],
                email=options["email"],
                password=options["password"],
                first_name=options.get("first_name") or "",
                last_name=options.get("last_name") or "",
            )
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} tenant admin '{user.username}' for tenant '{tenant.code}' ({tenant.name})."
            )
        )
