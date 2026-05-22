"""Cascade hooks that keep aggregate balances aligned with persisted ledger facts."""

from django.db.models.signals import post_delete
from django.dispatch import receiver

from accounting.models import DebtLedgerEntry
from accounting.services import customer_debt_ledger_cleanup_hook


@receiver(post_delete, sender=DebtLedgerEntry)
def _restore_customer_aggregate_on_delete(sender, instance, **kwargs):  # type: ignore[no-untyped-def]
    customer_debt_ledger_cleanup_hook(instance)
