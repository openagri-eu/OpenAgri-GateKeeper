from django.db import migrations


def dedupe_permission_rows(apps, schema_editor):
    PermissionMaster = apps.get_model("aegis", "PermissionMaster")
    CustomPermissions = apps.get_model("aegis", "CustomPermissions")
    GroupCustomPermissions = apps.get_model("aegis", "GroupCustomPermissions")
    permission_link_model = GroupCustomPermissions.permission_names.through

    permission_link_fields = [
        field for field in permission_link_model._meta.fields
        if getattr(field, "remote_field", None) is not None
    ]
    group_link_field = next(
        field for field in permission_link_fields
        if field.remote_field.model._meta.model_name == GroupCustomPermissions._meta.model_name
    )
    permission_link_field = next(
        field for field in permission_link_fields
        if field.remote_field.model._meta.model_name == PermissionMaster._meta.model_name
    )

    grouped_rows = {}
    for row in PermissionMaster.objects.order_by("service_id", "action", "id"):
        grouped_rows.setdefault((row.service_id, row.action), []).append(row)

    def sort_priority(permission):
        if permission.status == 1:
            priority = 0
        elif permission.status == 0:
            priority = 1
        else:
            priority = 2
        return priority, permission.id

    for duplicate_group in grouped_rows.values():
        if len(duplicate_group) < 2:
            continue

        survivor = sorted(duplicate_group, key=sort_priority)[0]

        for duplicate in duplicate_group:
            if duplicate.id == survivor.id:
                continue

            for custom_permission in CustomPermissions.objects.filter(permission_name_id=duplicate.id):
                if CustomPermissions.objects.filter(
                    user_id=custom_permission.user_id,
                    permission_name_id=survivor.id,
                ).exists():
                    custom_permission.delete()
                else:
                    custom_permission.permission_name_id = survivor.id
                    custom_permission.save(update_fields=["permission_name"])

            duplicate_links = permission_link_model.objects.filter(
                **{f"{permission_link_field.name}_id": duplicate.id}
            )
            for link in duplicate_links:
                existing_link_filter = {
                    f"{group_link_field.name}_id": getattr(link, f"{group_link_field.name}_id"),
                    f"{permission_link_field.name}_id": survivor.id,
                }
                if permission_link_model.objects.filter(**existing_link_filter).exists():
                    link.delete()
                else:
                    setattr(link, f"{permission_link_field.name}_id", survivor.id)
                    link.save(update_fields=[permission_link_field.name])

            duplicate.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("aegis", "0008_merge_0007_heads"),
    ]

    operations = [
        migrations.RunPython(dedupe_permission_rows, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="permissionmaster",
            unique_together={("service", "action")},
        ),
    ]
