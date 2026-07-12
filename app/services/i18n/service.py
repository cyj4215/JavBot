from __future__ import annotations

from . import en_US, ja_JP, zh_CN

_LANG_ZH = "zh_CN"
_LANG_EN = "en_US"
_LANG_JA = "ja_JP"

SUPPORTED_LANGUAGES = [_LANG_ZH, _LANG_EN, _LANG_JA]
LANGUAGE_NAMES = {
    _LANG_ZH: "中文",
    _LANG_EN: "English",
    _LANG_JA: "日本語",
}

_LANG_MAP: dict[str, dict[str, str]] = {}
_lang_modules = {
    _LANG_ZH: zh_CN,
    _LANG_EN: en_US,
    _LANG_JA: ja_JP,
}
for lang_code, module in _lang_modules.items():
    for key, text in module.TRANSLATIONS.items():
        if key not in _LANG_MAP:
            _LANG_MAP[key] = {}
        _LANG_MAP[key][lang_code] = text


_TRANSLATIONS = _LANG_MAP  # alias for test compatibility


class I18nService:
    """Translation service using dict-based lookup."""

    DEFAULT_LANG = _LANG_ZH

    def __init__(self, default_lang: str = _LANG_ZH):
        self._default_lang = default_lang if default_lang in SUPPORTED_LANGUAGES else _LANG_ZH

    def t(self, key: str, lang: str | None = None, *args) -> str:
        """Translate a key to the given language, with optional positional format args.

        Fallback chain: requested lang → default lang → key itself.
        """
        lang = lang if lang in SUPPORTED_LANGUAGES else self._default_lang

        entry = _LANG_MAP.get(key)
        if not entry:
            return key

        text = entry.get(lang) or entry.get(self._default_lang) or key

        if args:
            try:
                text = text.format(*args)
            except (KeyError, IndexError):
                pass

        return text

    def supported_languages(self) -> dict[str, str]:
        return dict(LANGUAGE_NAMES)

    def is_supported(self, lang: str) -> bool:
        return lang in SUPPORTED_LANGUAGES
