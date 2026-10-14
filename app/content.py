"""Read approved content; missing commercial facts never become invented prices."""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path


class Content:
    def __init__(self, root: Path):
        self.root = root / "content"

    def read(self, filename: str, default):
        path = self.root / filename
        if not path.exists():
            return default
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)

    @property
    def site(self) -> dict:
        return self.read("site.json", {})

    @property
    def products(self) -> list[dict]:
        data = self.read("products.json", [])
        if isinstance(data, dict):
            data = data.get("products", [])
        return [dict(item) for item in data if isinstance(item, dict) and isinstance(item.get("slug"), str)
                and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", item["slug"])]

    @property
    def articles(self) -> list[dict]:
        data = self.read("articles.json", [])
        if isinstance(data, dict):
            data = data.get("articles", [])
        return [dict(item) for item in data if isinstance(item, dict) and isinstance(item.get("slug"), str)
                and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", item["slug"])]

    def product(self, slug: str) -> dict | None:
        return next((p for p in self.products if p["slug"] == slug), None)

    @property
    def alternatives(self) -> list[dict]:
        """Reference families are never inventory, purchasable SKUs or feed offers."""
        data = self.read("alternatives.json", [])
        return [dict(item) for item in data if isinstance(item, dict)
                and isinstance(item.get("slug"), str)
                and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", item["slug"])
                and item.get("supply_status") == "not_supplied"] if isinstance(data, list) else []

    def alternative(self, slug: str) -> dict | None:
        return next((item for item in self.alternatives if item["slug"] == slug), None)


def price_kopecks(product: dict) -> int | None:
    value = product.get("price_rub")
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
        cents = amount * 100
        if not amount.is_finite() or amount <= 0 or amount > 1_000_000_000 or cents != cents.to_integral_value():
            return None
        return int(cents)
    except (InvalidOperation, ValueError):
        return None


def commercial_product(product: dict) -> bool:
    return (product.get("price_confirmed") is True
            and product.get("sku_confirmed") is True
            and product.get("purchasable") is True
            and isinstance(product.get("sku"), str)
            and bool(product["sku"].strip())
            and price_kopecks(product) is not None)


def format_rub(value) -> str:
    if value is None:
        return "По запросу"
    try:
        amount = Decimal(str(value))
        if not amount.is_finite():
            return "По запросу"
        digits = 0 if amount == amount.to_integral_value() else 2
        return f"{amount:,.{digits}f}".replace(",", " ").replace(".", ",")
    except (InvalidOperation, ValueError):
        return "По запросу"


def readiness(site: dict, settings) -> dict:
    legal = site.get("legal", {})
    seller = site.get("seller", {})
    forms_ready = (settings.forms_enabled and legal.get("owner_confirmed") is True
                   and legal.get("privacy_ready") is True and bool(legal.get("privacy_contact")))
    seller_ready = (seller.get("confirmed") is True
                    and all(isinstance(seller.get(k), str) and bool(seller[k].strip()) for k in (
                        "legal_name", "inn", "address", "bank_name", "bank_bik", "bank_account", "correspondent_account"))
                    and bool(re.fullmatch(r"\d{10}|\d{12}", str(seller.get("inn", ""))))
                    and bool(re.fullmatch(r"\d{9}", str(seller.get("bank_bik", ""))))
                    and all(bool(re.fullmatch(r"\d{20}", str(seller.get(k, "")))) for k in ("bank_account", "correspondent_account")))
    commerce_ready = settings.commerce_enabled and forms_ready and seller_ready and legal.get("commerce_terms_ready") is True
    return {"forms_enabled": bool(forms_ready), "commerce_enabled": bool(commerce_ready),
            "seller_confirmed": bool(seller_ready), "analytics_enabled": False,
            "preview_mode": settings.preview_mode}
