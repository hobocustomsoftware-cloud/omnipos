# Hand ProductStock Django state off to inventory app — table rows kept as-is.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_order_inventory_committed_flag"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="ProductStock"),
            ],
            database_operations=[],
        ),
    ]
