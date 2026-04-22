from django.db import migrations, models


def migrate_service_roles_to_tenants(apps, schema_editor):
    ServiceRole = apps.get_model("aegis", "ServiceRole")
    ServiceScopeAssignment = apps.get_model("aegis", "ServiceScopeAssignment")

    for role in ServiceRole.objects.all().order_by("id"):
        tenant_ids = list(
            ServiceScopeAssignment.objects.filter(role_ref_id=role.id)
            .exclude(tenant_id__isnull=True)
            .values_list("tenant_id", flat=True)
            .distinct()
        )

        if len(tenant_ids) == 1:
            role.tenant_id = tenant_ids[0]
            role.save(update_fields=["tenant"])
            continue

        if len(tenant_ids) <= 1:
            continue

        permission_ids = list(role.permissions.values_list("id", flat=True))
        primary_tenant_id = tenant_ids[0]
        role.tenant_id = primary_tenant_id
        role.save(update_fields=["tenant"])

        for tenant_id in tenant_ids[1:]:
            clone = ServiceRole.objects.create(
                tenant_id=tenant_id,
                service_id=role.service_id,
                role_code=role.role_code,
                role_name=role.role_name,
                description=role.description,
                status=role.status,
                deleted_at=role.deleted_at,
            )
            if permission_ids:
                clone.permissions.set(permission_ids)

            ServiceScopeAssignment.objects.filter(
                role_ref_id=role.id,
                tenant_id=tenant_id,
            ).update(
                role_ref_id=clone.id,
                role=clone.role_code,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("aegis", "0012_seed_external_tenants"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicerole",
            name="tenant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="service_roles",
                to="aegis.tenant",
            ),
        ),
        migrations.RunPython(migrate_service_roles_to_tenants, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="servicerole",
            unique_together={("tenant", "service", "role_code"), ("tenant", "service", "role_name")},
        ),
    ]
