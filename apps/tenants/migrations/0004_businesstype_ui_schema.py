"""Add BusinessType.ui_schema for zero-code Flutter payloads."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0003_dynamic_business_type_architecture"),
    ]

    operations = [
        migrations.AlterField(
            model_name="businesstype",
            name="code",
            field=models.CharField(
                db_index=True,
                help_text="Stable lowercase key (welding, retail, pharmacy, …).",
                max_length=64,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="businesstype",
            name="ui_schema",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Portable UI/layout payload consumed by OmniPOS Flutter (merged over built-in "
                    "presets — e.g. layout_preset, product_form_sections). Empty {} defers entirely "
                    "to coded fallbacks keyed by ``code``."
                ),
            ),
        ),
    ]
