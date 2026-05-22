# UserRole RBAC + optional catalog.Branch assignment

import django.db.models.deletion
from django.db import migrations, models


def map_legacy_roles_forwards(apps, schema_editor):  # type: ignore[no-untyped-def]
    StaffProfile = apps.get_model("accounts", "StaffProfile")
    remap = {"admin": "owner", "manager": "manager", "staff": "cashier"}
    batch = []
    for row in StaffProfile.objects.filter(role__in=remap).iterator():
        new_role = remap[row.role]
        row.role = new_role
        batch.append(row)
    if batch:
        StaffProfile.objects.bulk_update(batch, ["role"])


def map_legacy_roles_backwards(apps, schema_editor):  # type: ignore[no-untyped-def]
    StaffProfile = apps.get_model("accounts", "StaffProfile")
    remap = {
        "owner": "admin",
        "manager": "manager",
        "cashier": "staff",
        "stock_keeper": "staff",
    }
    batch = []
    for row in StaffProfile.objects.filter(role__in=remap).iterator():
        row.role = remap[row.role]
        batch.append(row)
    if batch:
        StaffProfile.objects.bulk_update(batch, ["role"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("catalog", "0005_remove_productstock_catalog_state_transfer"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffprofile",
            name="branch",
            field=models.ForeignKey(
                blank=True,
                help_text="Preferred / assigned branch for cashier or stock workflows; nullable for roaming owners.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="staff_assignments",
                to="catalog.branch",
            ),
        ),
        migrations.RunPython(map_legacy_roles_forwards, map_legacy_roles_backwards),
        migrations.AlterField(
            model_name="staffprofile",
            name="role",
            field=models.CharField(
                choices=[
                    ("owner", "Owner"),
                    ("manager", "Manager"),
                    ("cashier", "Cashier"),
                    ("stock_keeper", "Stock keeper"),
                ],
                default="cashier",
                max_length=32,
            ),
        ),
    ]
