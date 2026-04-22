import csv
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db.models import Q

from aegis.models import Tenant


def create_or_update_tenant_admin(
    *,
    tenant_code: str,
    username: str,
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
):
    tenant_code = (tenant_code or "").strip().lower()
    username = (username or "").strip()
    email = (email or "").strip().lower()
    password = password or ""
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()

    if not tenant_code or not username or not email or not password:
        raise CommandError("tenant_code, username, email, and password are required.")

    tenant = Tenant.objects.filter(code=tenant_code, status=1).first()
    if not tenant:
        raise CommandError(f"Active tenant '{tenant_code}' was not found.")

    user_model = get_user_model()
    user = user_model.objects.filter(Q(username__iexact=username) | Q(email__iexact=email)).first()

    if user and user.tenant_id and user.tenant_id != tenant.id:
        raise CommandError(
            f"User '{user.username}' already belongs to tenant '{user.tenant.code}'. "
            f"Refusing to reassign to '{tenant.code}'."
        )

    created = False
    if not user:
        user = user_model.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        created = True
    else:
        user.username = username
        user.email = email
        user.first_name = first_name or user.first_name
        user.last_name = last_name or user.last_name
        user.set_password(password)

    user.tenant = tenant
    user.is_tenant_admin = True
    user.is_superuser = False
    user.is_staff = True
    user.is_active = True
    user.status = 1
    user.deleted_at = None
    user.save()

    return user, tenant, created


def load_tenant_admin_rows(csv_path: str):
    path = Path(csv_path)
    if not path.exists():
        raise CommandError(f"CSV file was not found: {path}")

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"tenant_code", "username", "email", "password"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise CommandError(
                f"CSV file is missing required columns: {', '.join(sorted(missing))}"
            )
        return list(reader)
