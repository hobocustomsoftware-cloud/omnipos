"""UnitOfMeasure: Single FK vertical tag -> Many-to-many Dynamic tags."""

from django.db import migrations, models


def forwards_copy_fk_to_m2m(apps, schema_editor):  # type: ignore[no-untyped-def]
    UnitOfMeasure = apps.get_model("catalog", "UnitOfMeasure")
    qs = UnitOfMeasure.objects.exclude(applicable_business_type_id=None)
    for um in qs.iterator(chunk_size=200):
        um.applicable_business_types.add(um.applicable_business_type_id)


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0007_unitofmeasure_business_type_fk"),
        ("tenants", "0004_businesstype_ui_schema"),
    ]

    operations = [
        migrations.AddField(
            model_name="unitofmeasure",
            name="applicable_business_types",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "Leave empty for GLOBAL units visible to **all** tenants. "
                    "Otherwise only tenants whose primary BusinessType is among these tags "
                    "will see this unit."
                ),
                related_name="tagged_units_of_measure",
                to="tenants.businesstype",
            ),
        ),
        migrations.RunPython(forwards_copy_fk_to_m2m, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="unitofmeasure",
            name="applicable_business_type",
        ),
    ]
