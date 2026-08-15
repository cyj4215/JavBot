"""Regression: every i18n key used in handlers exists in all three languages."""
import re
from pathlib import Path

from app.services.i18n import _TRANSLATIONS, SUPPORTED_LANGUAGES

HANDLERS_DIR = Path(__file__).resolve().parents[2] / "app" / "handlers"

_KEY_RE = re.compile(r"""_(?:t)?\(['"]([a-z_][a-z0-9_]*)['"]""")


def test_all_handler_keys_translated():
    missing = set()
    for path in sorted(HANDLERS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for key in _KEY_RE.findall(text):
            if key not in _TRANSLATIONS:
                missing.add(f"{path.name}:{key}")
    assert not missing, f"Untranslated keys: {sorted(missing)}"


def test_all_keys_have_all_languages():
    for key, langs in _TRANSLATIONS.items():
        for lang in SUPPORTED_LANGUAGES:
            assert langs.get(lang, "").strip(), f"{key}[{lang}] is empty"
