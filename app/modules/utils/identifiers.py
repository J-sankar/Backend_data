from ...extensions import mongo
import re
import unicodedata
from typing import Optional

def _clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return text.encode("ascii", "ignore").decode("ascii")

def slugify(value: Optional[str]) -> str:
    """Lowercase, remove non-alnum, collapse spaces -> hyphens."""
    if not value:
        return ""
    s = _clean_text(value).lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-")


def get_brand_id(prefix="BR", padding=3):
    counter = mongo.db.counters.find_one_and_update(
        {"_id": "brand_id"},
        {"$inc": {"sequence_value": 1}},
        upsert=True,
        return_document=True
    )
    number = counter["sequence_value"]
    return f"{prefix}-{str(number).zfill(padding)}"


def get_product_id(prefix="PD", padding=3):
    counter = mongo.db.counters.find_one_and_update(
        {"_id": "product_id"},
        {"$inc": {"sequence_value": 1}},
        upsert=True,
        return_document=True
    )
    number = counter["sequence_value"]
    return f"{prefix}-{str(number).zfill(padding)}"
