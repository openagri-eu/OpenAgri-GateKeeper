from django.db import migrations


TENANTS = [
    ("sip06", "sip06-pois", "Precise Olive Irrigation Solution"),
    ("sip07", "sip07-coagriads", "Collaborative Development of Open-Source Aerial Detection ADS"),
    ("sip08", "sip08-agritwin", "Agricultural Digital Twin for Intelligent Decision-Making"),
    ("sip09", "sip09-spotifly", "Smart Pest Observation and Tracking for Identifying Flying Insects"),
    ("sip10", "sip10-smartcherry", "Smartphone-based DSS for Cherry Orchards"),
    ("sip11", "sip11-sheepcare", "Smart Health and Efficiency Enhancement through Prediction and Conductimetry"),
    ("sip12", "sip12-bugfinderai", "Identifying Insect Pests in Leafy Green Vegetables Using AI Image Recognition"),
    ("sip13", "sip13-smartfeed", "Smart Feed System"),
    ("sip14", "sip14-scibee", "Smart Community Integrated Beehive"),
]


def seed_tenants(apps, schema_editor):
    Tenant = apps.get_model("aegis", "Tenant")
    for code, slug, name in TENANTS:
        Tenant.objects.update_or_create(
            code=code,
            defaults={
                "slug": slug,
                "name": name,
                "status": 1,
                "deleted_at": None,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("aegis", "0011_tenant_defaultauthuserextend_is_tenant_admin_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_tenants, migrations.RunPython.noop),
    ]
