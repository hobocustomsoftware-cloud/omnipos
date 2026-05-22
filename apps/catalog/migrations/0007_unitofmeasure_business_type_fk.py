"""UnitOfMeasure.applicable_business_type becomes FK to tenants.BusinessType."""

import django.db.models.deletion
from django.db import migrations, models
from django_tenants.utils import get_public_schema_name, schema_context


def forwards_map_uom_foreign_keys(apps, schema_editor):  # type: ignore[no-untyped-def]
    BusinessType = apps.get_model("tenants", "BusinessType")
    UnitOfMeasure = apps.get_model("catalog", "UnitOfMeasure")

    public = get_public_schema_name()

    raw_tags = list(
        UnitOfMeasure.objects.order_by().values_list("_legacy_uom_vertical_slug", flat=True).distinct(),
    )

    with schema_context(public):
        for raw in raw_tags:
            if raw is None:
                continue
            tag = str(raw).strip()
            if not tag or tag.upper() == "GLOBAL":
                continue
            code = tag.lower()
            BusinessType.objects.update_or_create(
                code=code,
                defaults={
                    "name": code.replace("-", " ").replace("_", " ").title(),
                    "is_active": True,
                },
            )
        code_to_pk = dict(BusinessType.objects.values_list("code", "pk"))

    batch = []
    for row in UnitOfMeasure.objects.iterator(chunk_size=128):
        raw = getattr(row, "_legacy_uom_vertical_slug", None)
        tag = str(raw or "").strip()
        upper = tag.upper()

        if not tag or upper == "GLOBAL":
            row.applicable_business_type_id = None
        else:
            code = tag.lower()
            row.applicable_business_type_id = code_to_pk.get(code)

        batch.append(row)

    if batch:
        UnitOfMeasure.objects.bulk_update(batch, ["applicable_business_type_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_unit_of_measure_business_scope"),
        ("tenants", "0003_dynamic_business_type_architecture"),
    ]

    operations = [
        migrations.RenameField(
            model_name="unitofmeasure",
            old_name="applicable_business_type",
            new_name="_legacy_uom_vertical_slug",
        ),
        migrations.AddField(
            model_name="unitofmeasure",
            name="applicable_business_type",
            field=models.ForeignKey(
                blank=True,
                help_text="When null this unit applies to **all** tenants (GLOBAL behaviour). Otherwise limit to tenants sharing this vertical.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="scoped_units_of_measure",
                to="tenants.businesstype",
            ),
        ),
        migrations.RunPython(forwards_map_uom_foreign_keys, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="unitofmeasure",
            name="_legacy_uom_vertical_slug",
        ),
    ]
