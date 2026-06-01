"""Tests for I18nService: translation keys, all languages, format args, fallback."""
import pytest

from app.services.i18n_service import I18nService, _TRANSLATIONS, SUPPORTED_LANGUAGES


class TestTranslationsComplete:
    """Every key must have a non-empty translation in every supported language."""

    def test_all_keys_have_all_languages(self):
        missing = []
        for key, langs in _TRANSLATIONS.items():
            for lang in SUPPORTED_LANGUAGES:
                val = langs.get(lang)
                if not val or not val.strip():
                    missing.append(f"{key}[{lang}]")
        assert not missing, f"Missing translations: {missing}"

    def test_no_empty_translations(self):
        empty = []
        for key, langs in _TRANSLATIONS.items():
            for lang, val in langs.items():
                if not val.strip():
                    empty.append(f"{key}[{lang}]")
        assert not empty, f"Empty translations: {empty}"

    def test_no_unexpected_language_keys(self):
        valid_langs = set(SUPPORTED_LANGUAGES)
        bad = []
        for key, langs in _TRANSLATIONS.items():
            for lang in langs:
                if lang not in valid_langs:
                    bad.append(f"{key}[{lang}]")
        assert not bad, f"Unexpected language codes: {bad}"

    def test_all_translation_keys_have_zh(self):
        missing = [key for key in _TRANSLATIONS if "zh_CN" not in _TRANSLATIONS[key]]
        assert not missing, f"Keys missing zh_CN: {missing}"


class TestI18nService:
    def test_default_language(self):
        svc = I18nService(default_lang="zh_CN")
        assert svc.t("bot_started") == "🚀 机器人已成功启动！"

    def test_language_switch(self):
        svc = I18nService(default_lang="zh_CN")
        assert svc.t("bot_started", "en_US") == "🚀 Bot successfully started!"

    def test_language_switch_ja(self):
        svc = I18nService(default_lang="zh_CN")
        assert svc.t("bot_started", "ja_JP") == "🚀 ボットが正常に起動しました！"

    def test_fallback_to_default(self):
        svc = I18nService(default_lang="zh_CN")
        # Key exists but not in fr (unsupported) → fallback to default
        result = svc.t("bot_started", "fr_FR")
        assert result == "🚀 机器人已成功启动！"

    def test_fallback_to_key(self):
        svc = I18nService(default_lang="zh_CN")
        # Key doesn't exist
        result = svc.t("nonexistent_key")
        assert result == "nonexistent_key"

    def test_format_args(self):
        svc = I18nService(default_lang="zh_CN")
        result = svc.t("search_no_result", "zh_CN", "三上悠亜")
        assert "三上悠亜" in result

    def test_format_args_en(self):
        svc = I18nService(default_lang="zh_CN")
        result = svc.t("search_no_result", "en_US", "Yua Mikami")
        assert "Yua Mikami" in result

    def test_format_args_with_multiple(self):
        svc = I18nService(default_lang="zh_CN")
        result = svc.t("works_page", "zh_CN", 3, 10)
        assert "3" in result
        assert "10" in result

    def test_custom_default_lang(self):
        svc = I18nService(default_lang="en_US")
        assert svc.t("bot_started") == "🚀 Bot successfully started!"

    def test_invalid_default_fallback_to_zh(self):
        svc = I18nService(default_lang="fr_FR")
        assert svc.DEFAULT_LANG == "zh_CN"

    def test_supported_languages(self):
        svc = I18nService()
        langs = svc.supported_languages()
        assert "zh_CN" in langs
        assert "en_US" in langs
        assert "ja_JP" in langs

    def test_is_supported(self):
        svc = I18nService()
        assert svc.is_supported("zh_CN")
        assert svc.is_supported("en_US")
        assert svc.is_supported("ja_JP")
        assert not svc.is_supported("fr_FR")
        assert not svc.is_supported("de_DE")


class TestTranslationContent:
    """Spot-check key translations have expected content."""

    def test_bot_welcome_contains_chinese(self):
        svc = I18nService()
        text = svc.t("bot_welcome", "zh_CN")
        assert "欢迎" in text
        assert "番号" in text

    def test_bot_welcome_contains_english(self):
        svc = I18nService()
        text = svc.t("bot_welcome", "en_US")
        assert "Welcome" in text
        assert "AV ID" in text or "magnets" in text

    def test_bot_welcome_contains_japanese(self):
        svc = I18nService()
        text = svc.t("bot_welcome", "ja_JP")
        assert "ようこそ" in text
        assert "品番" in text

    def test_magnet_copy_key_exists(self):
        svc = I18nService()
        assert "复制" in svc.t("magnet_copy", "zh_CN")
        assert "Copy" in svc.t("magnet_copy", "en_US")
        assert "コピー" in svc.t("magnet_copy", "ja_JP")

    def test_works_page_format_all_langs(self):
        svc = I18nService()
        for lang in SUPPORTED_LANGUAGES:
            text = svc.t("works_page", lang, 1, 5)
            assert "1" in text
            assert "5" in text

    def test_key_count(self):
        """Smoke test: total keys should not drop unexpectedly."""
        assert len(_TRANSLATIONS) >= 80  # reasonable minimum


def test_importability():
    """Module can be imported without errors."""
    from app.services.i18n_service import I18nService, SUPPORTED_LANGUAGES
    assert len(SUPPORTED_LANGUAGES) == 3
    assert I18nService is not None
