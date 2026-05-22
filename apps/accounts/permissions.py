"""Authorization primitives for OmniPOS (helpers + REST branch scoping)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.permissions import BasePermission

from .models import (
    DEFAULT_ROLE_SLUG,
    ROLE_SLUG_MANAGER,
    ROLE_SLUG_OWNER,
    StaffProfile,
)

_DETAIL_BRANCH_MISMATCH_MM = (
    "သင်သည် ဤဆိုင်ခွဲ၏ ဒေတာများကို ဝင်ရောက်ကိုင်တွယ်ခွင့်မရှိပါ"
)

_DETAIL_BRANCH_SCOPE_REQUIRED_MM = (
    "ဆိုင်ခွဲကို ဖော်ပြပါ — "
    "`X-Branch-Id` ခေါင်းစည်း သို့မဟုတ် `branch_id` query parameter လိုပါသည်။"
)


if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser


def _branch_hint_request(request):  # type: ignore[no-untyped-def]
    hdr = request.META.get("HTTP_X_BRANCH_ID")
    if hdr is not None and str(hdr).strip() != "":
        return str(hdr).strip()
    params = getattr(request, "query_params", request.GET)
    q = params.get("branch_id")
    if q is not None and str(q).strip() != "":
        return str(q).strip()
    return None


def _resolve_branch_uuid(raw: str) -> UUID | None:
    try:
        return UUID(str(raw).strip())
    except (AttributeError, TypeError, ValueError):
        return None


def staff_may_act_on_branch(profile: StaffProfile, branch_uuid: UUID) -> bool:
    """True when ``branch_uuid`` matches primary or floated assignments."""

    if profile.primary_branch_id == branch_uuid:
        return True
    return profile.assigned_branches.filter(pk=branch_uuid).exists()


def user_can_manage_branch_pricing(user: AbstractBaseUser | None) -> bool:
    """Return True when the user may create/edit branch-level selling prices.

    Uses canonical role slug on :class:`~accounts.models.Role` (`owner`,
    `manager`). Additional Django permissions on the Role M2M are optional and
    not consulted here unless you extend this helper later.
    """

    if user is None or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    profile = getattr(user, "staff_profile", None)
    if profile is None:
        return False
    slug = profile.role.name
    return slug in {ROLE_SLUG_OWNER, ROLE_SLUG_MANAGER}


class IsBranchEmployee(BasePermission):
    """Ensure the caller is authorised for the branch named on the request.

    Branch context is resolved in order:

    #. ``HTTP_X_BRANCH_ID`` (``X-Branch-Id``)
    #. ``query_params`` / ``GET['branch_id']``

    Django staff (:attr:`~django.contrib.auth.models.User.is_staff`) and
    superusers bypass tenant branch scoping.
    """

    message = _DETAIL_BRANCH_MISMATCH_MM

    def has_permission(self, request, view) -> bool:  # type: ignore[no-untyped-def]
        user = request.user
        if not user.is_authenticated:
            return False
        # Admin / elevated accounts bypass scoped branch gates.
        if user.is_superuser or user.is_staff:
            return True

        hint = _branch_hint_request(request)
        if hint is None:
            raise DRFPermissionDenied(detail=_DETAIL_BRANCH_SCOPE_REQUIRED_MM)

        branch_uuid = _resolve_branch_uuid(hint)
        if branch_uuid is None:
            raise DRFPermissionDenied(detail=_DETAIL_BRANCH_MISMATCH_MM)

        profile = getattr(user, "staff_profile", None)
        if profile is None:
            raise DRFPermissionDenied(detail=_DETAIL_BRANCH_MISMATCH_MM)

        if not staff_may_act_on_branch(profile, branch_uuid):
            raise DRFPermissionDenied(detail=_DETAIL_BRANCH_MISMATCH_MM)

        return True


def get_or_create_default_cashier_role():  # type: ignore[no-untyped-def]
    """Return the persisted default cashier role (bootstrap)."""

    from .models import Role

    role, _ = Role.objects.get_or_create(
        name=DEFAULT_ROLE_SLUG,
        defaults={
            "description": "Point-of-sale operator; limited catalog pricing privilege.",
        },
    )
    return role
