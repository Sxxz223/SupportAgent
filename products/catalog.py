"""Load and query the single product catalog used by the application."""
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re


CATALOG_PATH = Path(__file__).with_name("catalog.json")


@dataclass(frozen=True)
class Product:
    product_id: str
    display_name: str
    model: str
    category: str
    rag_namespace: str
    aliases: tuple[str, ...]


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


@lru_cache(maxsize=1)
def list_products() -> tuple[Product, ...]:
    records = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return tuple(Product(**{**record, "aliases": tuple(record["aliases"])}) for record in records)


def get_product(product_id: str) -> Product | None:
    return next((item for item in list_products() if item.product_id == product_id), None)


def resolve_product(identifier: str | None) -> Product | None:
    if not identifier:
        return None
    candidate = _normalize(identifier)
    for product in list_products():
        values = (
            product.product_id,
            product.display_name,
            product.model,
            product.rag_namespace,
            *product.aliases,
        )
        normalized_values = {_normalize(value) for value in values}
        if candidate in normalized_values:
            return product
    return None
