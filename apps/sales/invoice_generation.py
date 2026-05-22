"""Thermal + A4 invoice/receipt payloads (JSON-oriented; ESC/POS drivers consume ``plain_text``)."""

from __future__ import annotations

import html
from decimal import Decimal
from typing import Any

from django.http import HttpRequest
from django.urls import reverse

from catalog.models import Order, OrderItem
from sales.models import InvoiceSetting


def _quantize_2(amount: Decimal) -> Decimal:
    return Decimal(str(amount)).quantize(Decimal("0.01"))


def _fmt_money(amount: Decimal) -> str:
    return format(_quantize_2(amount), "f")


def _truncate(text: str, max_len: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    if max_len < 4:
        return t[:max_len]
    return t[: max_len - 1] + "…"


def _qty_plain(qty: Decimal | str | float) -> str:
    raw = Decimal(str(qty)).normalize()
    txt = format(raw, "f")
    if "." in txt:
        txt = txt.rstrip("0").rstrip(".") or "0"
    return txt


class InvoiceGenerationService:
    """Compose POS thermal strings and structured A4 payloads from :class:`~catalog.models.Order`."""

    @classmethod
    def thermal_width_from_mm(cls, width_mm: int) -> int:
        """Rough column widths for monospace thermal fonts (narrow = 58 mm roll)."""

        if width_mm >= 76:
            return 48
        return 32

    @classmethod
    def render_thermal_text(cls, *, order: Order, width_chars: int = 32) -> str:
        """Plain-text ESC/POS friendly body (~32 chars / ~48 cols)."""

        w = max(24, min(64, width_chars))
        sep = "=" * w
        thin = "-" * w

        items = OrderItem.objects.filter(order_id=order.pk).select_related("product").order_by("created_at")

        lines: list[str] = []

        branch = order.branch
        lines.append(cls._thermal_center(branch.name or branch.code or "STORE", w))
        lines.append(cls._thermal_center(f"Branch: {branch.code}", w))
        lines.append(thin)
        lines.append(cls._thermal_center(str(order.pk), w))
        lines.append(cls._thermal_center(order.created_at.isoformat(timespec="seconds"), w))
        lines.append(thin)

        cust = getattr(order, "customer", None)
        if cust is not None:
            lines.append(_truncate(cust.name, w))

        grand = Decimal("0")
        for row in items:
            qty = Decimal(str(row.quantity))
            unit = Decimal(str(row.unit_price))
            ext = _quantize_2(qty * unit)
            grand += ext
            lines.append(_truncate(row.product.name, w))
            detail = (
                f"{row.product.sku}"
                + f"  x{_qty_plain(qty)}"
                + f"  @{_fmt_money(unit)}"
                + f"  ={_fmt_money(ext)}"
            )
            lines.append(_truncate(detail, w))

        grand = _quantize_2(grand)
        lines.append(sep)

        pays_ordered = order.payments.select_related("payment_method").order_by("created_at")
        sum_tendered_raw = Decimal("0")
        sum_change_raw = Decimal("0")
        for p in pays_ordered:
            sum_tendered_raw += Decimal(str(p.tendered_amount))
            sum_change_raw += Decimal(str(p.change_amount))
        sum_tendered = _quantize_2(sum_tendered_raw)
        sum_change = _quantize_2(sum_change_raw)

        lines.append(thin)
        lines.append(cls._thermal_label_value("ကျသင့်ငွေ (Total):", f"{_fmt_money(grand)} MMK", w))
        lines.append(cls._thermal_label_value("ပေးငွေ (Tendered):", f"{_fmt_money(sum_tendered)} MMK", w))
        lines.append(cls._thermal_label_value("အမ်းငွေ (Change):", f"{_fmt_money(sum_change)} MMK", w))
        lines.append(thin)

        for p in pays_ordered:
            code = getattr(p.payment_method, "code", "?")
            amt = _quantize_2(Decimal(str(p.amount)))
            left = code + ": "
            amt_s = _fmt_money(amt)
            space = max(1, w - len(left) - len(amt_s))
            lines.append(left + (" " * space) + amt_s)

        notes = order.notes or ""
        if notes.strip():
            lines.append("")
            lines.extend(cls._thermal_wrap_lines(_truncate(notes, 500), w))

        footer = InvoiceSetting.objects.filter(is_active=True).order_by("-updated_at").first()
        if footer is not None and footer.invoice_footer_note.strip():
            lines.append("")
            lines.extend(cls._thermal_wrap_lines(footer.invoice_footer_note.strip(), w))

        lines.append(sep)
        lines.extend(["", ""])
        return "\n".join(lines)

    @staticmethod
    def _thermal_label_value(left: str, right: str, width: int) -> str:
        lw, rw = len(left), len(right)
        gap = width - lw - rw
        if gap >= 1:
            return (left + (" " * gap) + right)[:width]
        return _truncate(left + " " + right, width)

    @staticmethod
    def _thermal_center(text: str, width: int) -> str:
        t = (text or "").strip()
        if not t:
            return " " * width
        if len(t) >= width:
            return t[:width]
        pad_total = width - len(t)
        pad_left = pad_total // 2
        out = (" " * pad_left + t)[:width]
        return (out + " " * max(0, width - len(out)))[:width]

    @staticmethod
    def _thermal_wrap_lines(text: str, width: int) -> list[str]:
        out: list[str] = []
        for paragraph in text.splitlines():
            buf = paragraph.strip()
            while len(buf) > width:
                out.append(buf[:width])
                buf = buf[width:].strip()
            if buf:
                out.append(buf[:width])
        return out

    @classmethod
    def build_a4_invoice_payload(
        cls,
        *,
        order: Order,
        settings: InvoiceSetting | None,
        request: HttpRequest | None,
    ) -> dict[str, Any]:
        """Structured document for Flutter / HTML renderers / future PDF converters."""

        items = OrderItem.objects.filter(order_id=order.pk).select_related("product").order_by("created_at")
        pays = order.payments.select_related("payment_method").order_by("created_at")

        line_payload: list[dict[str, str]] = []
        subtotal = Decimal("0")
        for row in items:
            qty = Decimal(str(row.quantity))
            unit = Decimal(str(row.unit_price))
            ext = _quantize_2(qty * unit)
            subtotal += ext
            line_payload.append(
                {
                    "sku": row.product.sku,
                    "product_name": row.product.name,
                    "quantity": _qty_plain(qty),
                    "unit_price": _fmt_money(unit),
                    "line_total": _fmt_money(ext),
                },
            )

        subtotal = _quantize_2(subtotal)
        pay_payload: list[dict[str, str]] = []
        for p in pays:
            pay_payload.append(
                {
                    "method_code": str(p.payment_method.code),
                    "method_name": str(p.payment_method.name),
                    "amount": _fmt_money(Decimal(str(p.amount))),
                    "tendered_amount": _fmt_money(Decimal(str(p.tendered_amount))),
                    "change_amount": _fmt_money(Decimal(str(p.change_amount))),
                    "transaction_ref": p.transaction_ref or "",
                },
            )

        company = cls._company_block(settings=settings, order=order, request=request)
        cid = html.escape(str(order.pk))
        created = html.escape(order.created_at.isoformat(timespec="seconds"))
        branch = order.branch
        cust_name = ""
        if getattr(order, "customer", None) is not None:
            cust_name = order.customer.name

        tot_tendered = _quantize_2(sum(Decimal(str(p.tendered_amount)) for p in pays))
        tot_change = _quantize_2(sum(Decimal(str(p.change_amount)) for p in pays))
        totals_map = {
            "subtotal": _fmt_money(subtotal),
            "grand_total": _fmt_money(subtotal),
            "tendered_total": _fmt_money(tot_tendered),
            "change_total": _fmt_money(tot_change),
        }
        footer_note_html = ""
        if settings is not None and settings.invoice_footer_note.strip():
            footer_note_html = html.escape(settings.invoice_footer_note.strip())

        payload: dict[str, Any] = {
            "document_type": "company_invoice",
            "format": "A4",
            "generated_at": order.updated_at.isoformat(timespec="seconds"),
            "company": company,
            "invoice_footer_note_html": footer_note_html,
            "order": {
                "id": str(order.pk),
                "branch_code": branch.code,
                "branch_name": branch.name,
                "status": order.status,
                "notes_plain": order.notes or "",
                "customer_name": cust_name,
                "created_at": order.created_at.isoformat(timespec="seconds"),
            },
            "lines": line_payload,
            "payments": pay_payload,
            "totals": totals_map,
            "pdf_generation_hint_url": cls._hint_url(request, str(order.pk)),
            "rendering_hints": {"primary_channel": "html_skeleton", "pdf_backend": "not_configured"},
        }
        payload["html_skeleton"] = cls._minimal_a4_html(
            order_pk=cid,
            created=created,
            branch_name=html.escape(branch.name),
            branch_code=html.escape(branch.code),
            company_html=company,
            lines_txt=line_payload,
            totals=totals_map,
            footer_txt=footer_note_html,
            customer_name=html.escape(cust_name) if cust_name else "",
            notes_plain=html.escape(order.notes or ""),
        )
        return payload

    @staticmethod
    def _company_block(*, settings: InvoiceSetting | None, order: Order, request: HttpRequest | None) -> dict[str, Any]:
        name = getattr(settings, "company_name", None) if settings is not None else None
        if not name:
            name = order.branch.name or order.branch.code
        logo_url = ""
        if settings is not None and request is not None and getattr(settings.company_logo, "name", ""):
            try:
                logo_url = request.build_absolute_uri(settings.company_logo.url)
            except Exception:
                logo_url = ""
        return {
            "name": html.escape(str(name)),
            "tax_identifier": html.escape(settings.tax_identifier) if settings and settings.tax_identifier else "",
            "address_html": html.escape(settings.registered_address) if settings and settings.registered_address else "",
            "phone": html.escape(settings.contact_phone) if settings and settings.contact_phone else "",
            "logo_url": logo_url,
        }

    @staticmethod
    def _hint_url(request: HttpRequest | None, order_id: str) -> str:
        if request is None:
            path = reverse("sales-order-invoice", kwargs={"order_id": order_id})
            return f"{path}?format=A4"
        rel = reverse("sales-order-invoice", kwargs={"order_id": order_id}) + "?format=A4"
        return request.build_absolute_uri(rel)

    @staticmethod
    def _minimal_a4_html(
        *,
        order_pk: str,
        created: str,
        branch_name: str,
        branch_code: str,
        company_html: dict[str, str],
        lines_txt: list[dict[str, str]],
        totals: dict[str, str],
        footer_txt: str,
        customer_name: str,
        notes_plain: str,
    ) -> str:
        body_rows = "".join(
            "<tr>"
            f"<td>{html.escape(row['sku'])}</td>"
            f"<td>{html.escape(row['product_name'])}</td>"
            f"<td>{html.escape(row['quantity'])}</td>"
            f"<td style='text-align:right'>{html.escape(row['unit_price'])}</td>"
            f"<td style='text-align:right'>{html.escape(row['line_total'])}</td>"
            "</tr>"
            for row in lines_txt
        )
        hdr = "".join(
            [
                "<header>",
                f"<h1>{company_html['name']}</h1>",
                "<div>",
                company_html["address_html"],
                "</div>",
                f"<div>Tax/VAT: {company_html['tax_identifier']}</div>",
                f"<div>Tel: {company_html['phone']}</div>",
                "</header>",
            ],
        )
        buyer = ""
        if customer_name:
            buyer = f"<p><strong>Bill-to:</strong> {customer_name}</p>"
        note_block = ""
        if notes_plain:
            note_block = f"<aside><small><strong>Notes:</strong><br />{notes_plain}</small></aside>"

        return (
            "<!DOCTYPE html>"
            '<html lang="en"><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>'
            f"<title>Invoice #{order_pk}</title>"
            "<style>@page{margin:18mm;} body{font-family:system-ui;line-height:1.45;color:#222}"
            ".meta{margin-bottom:14px;} table{border-collapse:collapse;width:100%;font-size:.95rem}"
            " thead th{font-size:.82rem;color:#444;border-bottom:1px solid #999;padding:.45rem;text-align:left}"
            " tbody td{border-bottom:1px solid #eee;padding:.45rem;vertical-align:top}"
            " tbody td:last-child{font-variant-numeric:tabular-nums} .grand{border-top:2px solid #111;font-weight:bold}</style>"
            "<body>"
            f"{hdr}"
            "<main>"
            '<section class="meta">'
            f"<h2>Tax Invoice #{order_pk}</h2>"
            f"<small><strong>Branch:</strong> {branch_name} ({branch_code})<br/><strong>Dated:</strong> {created}</small>"
            f"{buyer}</section>"
            f"{note_block}"
            "<table><thead><tr><th>SKU</th><th>Description</th><th>Qty</th><th>Unit</th><th>Amount</th></tr></thead>"
            f"<tbody>{body_rows}<tr><td colspan='4' class='grand' style='text-align:right'>Grand Total</td>"
            f"<td class='grand' style='text-align:right'>{html.escape(totals['grand_total'])}</td></tr>"
            "</tbody></table>"
            "</main>"
            f"<footer><small>{footer_txt}</small></footer></body></html>"
        )
