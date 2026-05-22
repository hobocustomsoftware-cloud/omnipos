"""Admin registrations for tenant identity."""

from django.contrib import admin

from .models import Role, StaffProfile


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "created_at", "updated_at")
    search_fields = ("name", "description")
    filter_horizontal = ("permissions",)


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "primary_branch", "created_at")
    search_fields = ("user__username", "user__email", "role__name")
    list_filter = ("role", "primary_branch")
    autocomplete_fields = ("primary_branch", "role")
    filter_horizontal = ("assigned_branches",)
