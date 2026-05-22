"""Staff identity with dynamic RBAC roles (Django Permissions M2M)."""

from django.conf import settings
from django.db import models

from core.models import AbstractBaseModel

# Canonical role slugs (seed migrations + bootstrap helpers).
ROLE_SLUG_OWNER = "owner"
ROLE_SLUG_MANAGER = "manager"
ROLE_SLUG_CASHIER = "cashier"
ROLE_SLUG_STOCK_KEEPER = "stock_keeper"
DEFAULT_ROLE_SLUG = ROLE_SLUG_CASHIER


class Role(AbstractBaseModel):
    """Tenant-managed role attaching optional Django Permission rows."""

    name = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Stable slug-like key (e.g. owner, cashier).",
    )
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(
        "auth.Permission",
        blank=True,
        related_name="+",
        help_text="Django permission entries granted alongside this tenant role.",
    )

    def __str__(self) -> str:
        return self.name


class StaffProfile(AbstractBaseModel):
    """Tenant staffing row: dynamic Role RBAC plus home + floating branches."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="staff_profile",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="staff_profiles",
    )
    primary_branch = models.ForeignKey(
        "catalog.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_staff_profiles",
        help_text="Default / home branch. May be blank for roster-only floating staff.",
    )
    assigned_branches = models.ManyToManyField(
        "catalog.Branch",
        blank=True,
        related_name="floated_staff_profiles",
        help_text="All branches where this staff member may work (includes typical floaters).",
    )

    def __str__(self) -> str:
        return f"{self.user.get_username()} ({self.role.name})"
