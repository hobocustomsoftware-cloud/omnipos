# Dynamic RBAC Role model + migrate StaffProfile from legacy CharField slug to FK.

import django.db.models.deletion
import uuid
from django.db import migrations, models


def seed_roles_forwards(apps, schema_editor):  # type: ignore[no-untyped-def]
    Role = apps.get_model("accounts", "Role")
    seeds = (
        ("owner", "Tenant / store owner."),
        ("manager", "Operational manager."),
        ("cashier", "Point-of-sale cashier."),
        ("stock_keeper", "Receiving and stock keeper."),
    )
    for slug, description in seeds:
        Role.objects.get_or_create(name=slug, defaults={"description": description})


def assign_staff_profiles_to_roles_forwards(apps, schema_editor):  # type: ignore[no-untyped-def]
    StaffProfile = apps.get_model("accounts", "StaffProfile")
    Role = apps.get_model("accounts", "Role")

    slug_to_role = {r.name: r for r in Role.objects.all()}
    default = slug_to_role.get("cashier")
    assert default is not None  # seeded in prior step

    unknown: set[str] = set()
    batch = []

    for row in StaffProfile.objects.iterator(chunk_size=128):
        raw = getattr(row, "legacy_role_slug", "") or ""
        slug = raw.strip().lower()
        resolved = slug_to_role.get(slug)
        if not slug:
            resolved = default
        if resolved is None:
            unknown.add(slug or "<empty>")
            resolved = default
        row.role_id = resolved.id
        batch.append(row)

    if batch:
        StaffProfile.objects.bulk_update(batch, ["role_id"])

    if unknown:
        print(f"[accounts.0003] Unknown legacy_role_slug values folded to cashier: {sorted(unknown)}")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_staffprofile_userrole_branch"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Role",
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
                    "name",
                    models.CharField(
                        db_index=True,
                        help_text="Stable slug-like key (e.g. owner, cashier).",
                        max_length=64,
                        unique=True,
                    ),
                ),
                ("description", models.TextField(blank=True)),
                (
                    "permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Django permission entries granted alongside this tenant role.",
                        related_name="+",
                        to="auth.permission",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.RunPython(seed_roles_forwards, migrations.RunPython.noop),
        migrations.RenameField(
            model_name="staffprofile",
            old_name="role",
            new_name="legacy_role_slug",
        ),
        migrations.AddField(
            model_name="staffprofile",
            name="role",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="staff_profiles",
                to="accounts.role",
            ),
        ),
        migrations.RunPython(assign_staff_profiles_to_roles_forwards, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="staffprofile",
            name="legacy_role_slug",
        ),
        migrations.AlterField(
            model_name="staffprofile",
            name="role",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="staff_profiles",
                to="accounts.role",
            ),
        ),
    ]
