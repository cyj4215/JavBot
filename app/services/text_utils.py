from __future__ import annotations

import re
import unicodedata


def normalize_name(name: str) -> str:
    """Unicode NFKC normalize + strip."""
    return unicodedata.normalize("NFKC", name).strip()


def contains_cjk(text: str) -> bool:
    """Check if text contains CJK characters."""
    return bool(re.search(r"[\u3400-\u9fff]", text))
