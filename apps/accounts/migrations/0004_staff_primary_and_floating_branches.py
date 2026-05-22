# Primary + floating Branch assignment (preserve legacy StaffProfile.branch).

import django.db.models.deletion
from django.db import migrations, models


def migrate_legacy_branch_into_primary_and_links(apps, schema_editor):  # type: ignore[no-untyped-def]
    StaffProfile = apps.get_model("accounts", "StaffProfile")
    for row in StaffProfile.objects.exclude(branch_id__isnull=True).iterator(chunk_size=128):
        bid = row.branch_id
        if bid is None:
            continue
        row.primary_branch_id = bid
        row.save(update_fields=["primary_branch_id"])
        row.assigned_branches.add(bid)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_dynamic_role_rbac"),
        ("catalog", "0005_remove_productstock_catalog_state_transfer"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffprofile",
            name="primary_branch",
            field=models.ForeignKey(
                blank=True,
                help_text="Default / home branch. May be blank for roster-only floating staff.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="primary_staff_profiles",
                to="catalog.branch",
            ),
        ),
        migrations.AddField(
            model_name="staffprofile",
            name="assigned_branches",
            field=models.ManyToManyField(
                blank=True,
                help_text="All branches where this staff member may work (includes typical floaters).",
                related_name="floated_staff_profiles",
                to="catalog.branch",
            ),
        ),
        migrations.RunPython(
            migrate_legacy_branch_into_primary_and_links,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="staffprofile",
            name="branch",
        ),
    ]
