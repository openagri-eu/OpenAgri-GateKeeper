from django.db import migrations, models
import django.db.models.deletion


def seed_service_roles(apps, schema_editor):
    ServiceMaster = apps.get_model("aegis", "ServiceMaster")
    PermissionMaster = apps.get_model("aegis", "PermissionMaster")
    ServiceRole = apps.get_model("aegis", "ServiceRole")
    ServiceScopeAssignment = apps.get_model("aegis", "ServiceScopeAssignment")

    role_map = {
        "viewer": ["view"],
        "moderator": ["view", "add", "edit"],
        "admin": ["view", "add", "edit", "delete"],
    }

    for service in ServiceMaster.objects.filter(status=1):
        service_permissions = {
            permission.action: permission
            for permission in PermissionMaster.objects.filter(service=service, status=1)
        }

        created_roles = {}
        for role_code, actions in role_map.items():
            role_name = role_code.title()
            role, _ = ServiceRole.objects.get_or_create(
                service=service,
                role_code=role_code,
                defaults={
                    "role_name": role_name,
                    "description": f"{role_name} role for {service.service_name}",
                    "status": 1,
                },
            )
            permission_ids = [
                service_permissions[action].id
                for action in actions
                if action in service_permissions
            ]
            if permission_ids:
                role.permissions.set(permission_ids)
            created_roles[role_code] = role

        for assignment in ServiceScopeAssignment.objects.filter(service=service):
            if assignment.role_ref_id:
                continue
            role = created_roles.get((assignment.role or "").strip().lower())
            if role:
                assignment.role_ref_id = role.id
                assignment.save(update_fields=["role_ref"])


class Migration(migrations.Migration):

    dependencies = [
        ("aegis", "0009_restore_permissionmaster_uniqueness"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.SmallIntegerField(choices=[(1, "Active"), (0, "Inactive"), (2, "Deleted")], default=1, verbose_name="Status")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("role_code", models.CharField(max_length=50)),
                ("role_name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True, null=True)),
                ("permissions", models.ManyToManyField(blank=True, related_name="service_roles", to="aegis.permissionmaster")),
                ("service", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="roles", to="aegis.servicemaster")),
            ],
            options={
                "verbose_name": "Service Role",
                "verbose_name_plural": "Service Roles",
                "db_table": "service_role",
                "ordering": ("service__service_code", "role_name"),
                "unique_together": {("service", "role_code"), ("service", "role_name")},
            },
        ),
        migrations.AddField(
            model_name="servicescopeassignment",
            name="role_ref",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="scope_assignments", to="aegis.servicerole"),
        ),
        migrations.RunPython(seed_service_roles, migrations.RunPython.noop),
    ]
