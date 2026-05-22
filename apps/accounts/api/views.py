"""Authenticated staff discovery endpoints."""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import StaffProfile
from catalog.models import Branch


class UserBranchListAPIView(APIView):
    """Branches the signed-in clerk may attach to POS scope."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):  # type: ignore[no-untyped-def]
        user = request.user

        if user.is_superuser or user.is_staff:
            rows = Branch.objects.filter(is_active=True).order_by("code")
            return Response(
                {
                    "branches": [
                        {
                            "id": str(b.pk),
                            "code": b.code,
                            "name": b.name,
                            "is_primary": False,
                            "scope_kind": "admin_bypass_all_active",
                        }
                        for b in rows
                    ],
                },
            )

        profile = getattr(user, "staff_profile", None)
        if profile is None:
            return Response({"branches": [], "detail": "No staff_profile on this login."})

        profile = StaffProfile.objects.select_related("primary_branch").get(pk=profile.pk)
        pk_seen: set[str] = set()
        assembled: list[dict] = []

        def push(branch: Branch, *, is_primary: bool, scope_kind: str) -> None:
            if branch is None or not branch.is_active:
                return
            bid = str(branch.pk)
            if bid in pk_seen:
                return
            pk_seen.add(bid)
            assembled.append(
                {
                    "id": bid,
                    "code": branch.code,
                    "name": branch.name,
                    "is_primary": is_primary,
                    "scope_kind": scope_kind,
                },
            )

        push(profile.primary_branch, is_primary=True, scope_kind="primary")
        for b in profile.assigned_branches.filter(is_active=True).order_by("code"):
            push(b, is_primary=False, scope_kind="assigned")

        return Response({"branches": assembled})


class UserProfileAPIView(APIView):
    """Return role slug + flattened Django permission keys for kiosk authorization."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):  # type: ignore[no-untyped-def]
        user = request.user

        payload: dict = {
            "user_id": str(user.pk),
            "username": user.get_username(),
            "email": getattr(user, "email", "") or "",
            "is_staff": getattr(user, "is_staff", False),
            "is_superuser": getattr(user, "is_superuser", False),
            "staff_profile": None,
            "permissions": [],
        }

        profile = getattr(user, "staff_profile", None)
        if profile is None:
            return Response(payload)

        profile = StaffProfile.objects.select_related("role", "primary_branch").prefetch_related(
            "role__permissions",
            "role__permissions__content_type",
        ).get(pk=profile.pk)
        role = profile.role

        perm_keys: list[str] = []
        for perm in role.permissions.select_related("content_type").order_by(
            "content_type__app_label",
            "codename",
        ):
            perm_keys.append(f"{perm.content_type.app_label}.{perm.codename}")

        primary = profile.primary_branch
        payload["staff_profile"] = {
            "primary_branch_id": str(primary.pk) if primary else None,
            "primary_branch_code": getattr(primary, "code", "") if primary else "",
            "role": {
                "name": role.name,
                "description": role.description,
            },
        }
        payload["permissions"] = perm_keys

        return Response(payload)
