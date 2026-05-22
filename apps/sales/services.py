"""Pricing and checkout-side monetary helpers (unit price + totals)."""



from __future__ import annotations



from decimal import ROUND_HALF_UP, Decimal

from typing import Any, Iterable



from django.core.exceptions import ValidationError

from catalog.models import Branch, Product, ProductBranchSettings



_TWO_PLACES = Decimal("0.01")





class PricingEngineService:

    """Retail vs wholesale unit pricing and dynamic order total sums."""



    @staticmethod

    def resolve_unit_price(

        *,

        product: Product,

        quantity: Decimal | float | str | int,

        branch: Branch | None = None,

    ) -> Decimal:

        """Return the monetary unit charge for ``quantity`` of ``product``.



        If ``product.wholesale_price`` is non-null **and**

        ``quantity >= product.wholesale_minimum_qty``, wholesale applies.



        Otherwise resolves **retail** using branch overrides when configured

        (:class:`~catalog.models.ProductBranchSettings`), else ``base_price``.

        """



        qty = PricingEngineService._coerce_quantity(quantity)

        wholesale = PricingEngineService._quantize_money(product.wholesale_price)

        min_qty = Decimal(product.wholesale_minimum_qty)



        if wholesale is not None and qty >= min_qty:

            return wholesale



        retail = PricingEngineService._retail_base(product, branch)

        quantized = PricingEngineService._quantize_money(retail)

        assert quantized is not None

        return quantized



    @staticmethod

    def _retail_base(product: Product, branch: Branch | None) -> Decimal:

        if branch is None:

            return Decimal(str(product.base_price))

        overrides = ProductBranchSettings.objects.filter(

            branch_id=branch.id,

            product_id=product.id,

        ).first()

        if overrides is None:

            return Decimal(str(product.base_price))

        return Decimal(str(overrides.effective_selling_price))



    @staticmethod

    def compute_order_total(*, lines: Iterable[Any]) -> Decimal:

        """Sum ``quantity * unit_price`` for checkout / draft previews.



        Each element may be a dict ``quantity`` / ``unit_price`` (case-insensitive

        keys), a ``(quantity, unit_price)`` tuple, or an object with matching

        attributes (``OrderItem``). Quantities preserve full Decimal precision;

        unit prices round to cents; returned total rounds to cents (half-up).

        """



        total = Decimal("0")

        for line in lines:

            qty, unit = PricingEngineService._extract_quantity_and_price(line)

            total += qty * unit

        quantized = PricingEngineService._quantize_money(total)

        assert quantized is not None

        return quantized



    @staticmethod

    def _extract_quantity_and_price(line: Any) -> tuple[Decimal, Decimal]:

        if isinstance(line, tuple) and len(line) == 2:

            qty_raw, unit_raw = line

            q = PricingEngineService._coerce_quantity(qty_raw)

            u = PricingEngineService._quantize_money(PricingEngineService._coerce_money(unit_raw))

            assert u is not None

            return q, u



        if isinstance(line, dict):

            try:

                q_raw = PricingEngineService._pick_line_mapping(line, "quantity")

                u_raw = PricingEngineService._pick_line_mapping(line, "unit_price")

            except KeyError:

                raise ValidationError(

                    "Each mapping line requires quantity and unit_price keys.",

                    code="invalid_line",

                ) from None

            q = PricingEngineService._coerce_quantity(q_raw)

            u = PricingEngineService._quantize_money(PricingEngineService._coerce_money(u_raw))

            assert u is not None

            return q, u



        qty_raw = getattr(line, "quantity", None)

        unit_raw = getattr(line, "unit_price", None)

        if qty_raw is None or unit_raw is None:

            raise ValidationError(

                "Lines must expose quantity/unit_price attributes, mapping keys, or a length-2 tuple.",

                code="invalid_line",

            )

        q = PricingEngineService._coerce_quantity(qty_raw)

        u = PricingEngineService._quantize_money(PricingEngineService._coerce_money(unit_raw))

        assert u is not None

        return q, u



    @staticmethod

    def _pick_line_mapping(data: dict[Any, Any], logical_name: str) -> Any:

        """Resolve key case-insensitively (helps JSON clients)."""



        target = logical_name.casefold()

        for key in data:

            if str(key).casefold() == target:

                return data[key]

        raise KeyError(logical_name)



    @staticmethod

    def _coerce_quantity(raw: Decimal | float | str | int | Any) -> Decimal:

        num = PricingEngineService._coerce_money(raw)

        if num >= Decimal("0"):

            return num

        raise ValidationError("Quantity must not be negative.", code="invalid_quantity")



    @staticmethod

    def _coerce_money(value: Decimal | float | str | Any) -> Decimal:

        if isinstance(value, Decimal):

            dec = value

        else:

            try:

                dec = Decimal(str(value))

            except ArithmeticError as exc:

                raise ValidationError("Invalid numeric literal.", code="invalid_amount") from exc

            except Exception as exc:

                raise ValidationError("Invalid numeric literal.", code="invalid_amount") from exc

        if dec.is_nan() or dec.is_infinite():

            raise ValidationError("Non-finite amount.", code="invalid_amount")

        return dec



    @staticmethod

    def _quantize_money(value: Decimal | None) -> Decimal | None:

        if value is None:

            return None

        normalized = PricingEngineService._coerce_money(value)

        return normalized.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
