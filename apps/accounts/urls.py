"""Routes under ``api/accounts/``."""

from django.urls import path

from accounts.api.views import UserBranchListAPIView, UserProfileAPIView

urlpatterns = [
    path(
        "user/branches/",
        UserBranchListAPIView.as_view(),
        name="accounts-user-branches",
    ),
    path(
        "user/profile/",
        UserProfileAPIView.as_view(),
        name="accounts-user-profile",
    ),
]
