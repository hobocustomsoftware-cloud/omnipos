# ProductStock belongs to inventory; physical table unchanged (catalog_productstock).

import django.core.validators
import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("catalog", "0005_remove_productstock_catalog_state_transfer"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="ProductStock",
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
                            "quantity",
                            models.DecimalField(
                                decimal_places=4,
                                default=0,
                                help_text="On-hand amount in Product.base_uom_code units.",
                                max_digits=14,
                                validators=[django.core.validators.MinValueValidator(0)],
                            ),
                        ),
                        (
                            "branch",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="product_stocks",
                                to="catalog.branch",
                            ),
                        ),
                        (
                            "product",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="branch_stocks",
                                to="catalog.product",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "catalog_productstock",
                    },
                ),
                migrations.AddConstraint(
                    model_name="productstock",
                    constraint=models.UniqueConstraint(
                        fields=("branch", "product"),
                        name="catalog_productstock_unique_branch_product",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
