"""Dynamic BusinessType model + Client FK (replaces legacy CharField)."""

import uuid

import django.db.models.deletion
from django.db import migrations, models


def seed_business_types(apps, schema_editor):  # type: ignore[no-untyped-def]
    BusinessType = apps.get_model("tenants", "BusinessType")
    seeds = (
        ("retail", "Retail"),
        ("workshop", "Workshop"),
        ("services", "Services"),
    )
    for code, name in seeds:
        BusinessType.objects.update_or_create(
            code=code,
            defaults={"name": name, "is_active": True},
        )


def map_client_business_type_fk(apps, schema_editor):  # type: ignore[no-untyped-def]
    Client = apps.get_model("tenants", "Client")
    BusinessType = apps.get_model("tenants", "BusinessType")
    slug_to_row = {bt.code: bt for bt in BusinessType.objects.all()}
    default = slug_to_row.get("retail")
    if default is None:
        raise RuntimeError("Catalog migration requires seeded BusinessType 'retail'.")
    batch = []
    for row in Client.objects.all():
        slug = str(getattr(row, "_legacy_bt_slug", "") or "retail").strip().lower()
        target = slug_to_row.get(slug) or default
        row.business_type_id = target.id
        batch.append(row)
    if batch:
        Client.objects.bulk_update(batch, ["business_type_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0002_alter_client_options_alter_domain_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="BusinessType",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "code",
                    models.CharField(
                        db_index=True,
                        help_text="Stable lowercase key (retail, pharmacy, electronics, …).",
                        max_length=64,
                        unique=True,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "ordering": ("code",),
                "verbose_name": "Business type",
                "verbose_name_plural": "Business types",
            },
        ),
        migrations.RunPython(seed_business_types, migrations.RunPython.noop),
        migrations.RenameField(
            model_name="client",
            old_name="business_type",
            new_name="_legacy_bt_slug",
        ),
        migrations.AddField(
            model_name="client",
            name="business_type",
            field=models.ForeignKey(
                blank=True,
                help_text="Vertical driving catalogue units, presets, and partner UX divergences.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tenant_clients",
                to="tenants.businesstype",
            ),
        ),
        migrations.RunPython(map_client_business_type_fk, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="client",
            name="_legacy_bt_slug",
        ),
        migrations.AlterField(
            model_name="client",
            name="business_type",
            field=models.ForeignKey(
                help_text="Vertical driving catalogue units, presets, and partner UX divergences.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tenant_clients",
                to="tenants.businesstype",
            ),
        ),
    ]
