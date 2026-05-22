"""Shared abstract models for OmniPOS."""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class IntegrationScope(models.TextChoices):
    """Where a credential bundle or compliance artifact applies."""

    SAAS = "saas", _("SaaS billing")
    POS = "pos", _("POS / storefront")


class UUIDTimestampedAbstract(models.Model):
    """Primary UUID + audit timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


AbstractBaseModel = UUIDTimestampedAbstract
