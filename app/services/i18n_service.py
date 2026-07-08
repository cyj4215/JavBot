from __future__ import annotations

from typing import Dict, Optional

_LANG_ZH = "zh_CN"
_LANG_EN = "en_US"
_LANG_JA = "ja_JP"

SUPPORTED_LANGUAGES = [_LANG_ZH, _LANG_EN, _LANG_JA]
LANGUAGE_NAMES = {
    _LANG_ZH: "中文",
    _LANG_EN: "English",
    _LANG_JA: "日本語",
}

_TRANSLATIONS: Dict[str, Dict[str, str]] = {

    # ── Bot info ──
    "bot_welcome": {
        _LANG_ZH: "🎉 欢迎使用！\n\n快速上手：\n🔍 发送女优名字 → 查看个人资料\n🧲 发送番号 (SSIS-123) → 搜索磁力\n⭐ 收藏女优 → 随时查看最新作品\n\n以下是主要功能入口：",
        _LANG_EN: "🎉 Welcome!\n\nQuick start:\n🔍 Send an actress name → View profile\n🧲 Send an AV ID (SSIS-123) → Search magnets\n⭐ Save favorites → Track latest works\n\nMain menu:",
        _LANG_JA: "🎉 ようこそ！\n\nクイックスタート：\n🔍 女優名を送信 → プロフィール表示\n🧲 品番を送信 (SSIS-123) → マグネット検索\n⭐ お気に入り登録 → 最新作品をチェック\n\nメインメニュー：",
    },
    "bot_started": {
        _LANG_ZH: "🚀 机器人已成功启动！",
        _LANG_EN: "🚀 Bot successfully started!",
        _LANG_JA: "🚀 ボットが正常に起動しました！",
    },
    "bot_data_source": {
        _LANG_ZH: "🔧 数据来源：JavBus / JavDb / Wikipedia",
        _LANG_EN: "🔧 Data source: JavBus / JavDb / Wikipedia",
        _LANG_JA: "🔧 データソース: JavBus / JavDb / Wikipedia",
    },
    "bot_query_time": {
        _LANG_ZH: "⏰ 查询时间：{}",
        _LANG_EN: "⏰ Query time: {}",
        _LANG_JA: "⏰ 検索時刻：{}",
    },

    # ── Menu buttons ──
    "menu_search_actress": {
        _LANG_ZH: "🔍 搜索女优",
        _LANG_EN: "🔍 Search Actress",
        _LANG_JA: "🔍 女優を検索",
    },
    "menu_magnet": {
        _LANG_ZH: "💾 磁力搜索",
        _LANG_EN: "💾 Magnet Search",
        _LANG_JA: "💾 マグネット検索",
    },
    "menu_rank": {
        _LANG_ZH: "🏆 热门女优榜",
        _LANG_EN: "🏆 Top Actresses",
        _LANG_JA: "🏆 人気女優ランキング",
    },
    "menu_favorites": {
        _LANG_ZH: "⭐ 我的收藏",
        _LANG_EN: "⭐ My Favorites",
        _LANG_JA: "⭐ お気に入り",
    },
    "menu_help": {
        _LANG_ZH: "ℹ️ 帮助信息",
        _LANG_EN: "ℹ️ Help",
        _LANG_JA: "ℹ️ ヘルプ",
    },
    "menu_return": {
        _LANG_ZH: "🔄 返回主菜单",
        _LANG_EN: "🔄 Back to Menu",
        _LANG_JA: "🔄 メインメニューに戻る",
    },
    "profile_back_fav": {
        _LANG_ZH: "返回收藏列表",
        _LANG_EN: "Back to Favorites",
        _LANG_JA: "お気に入りに戻る",
    },

    # ── Auth ──
    "no_permission": {
        _LANG_ZH: "无权限使用此机器人。",
        _LANG_EN: "You do not have permission to use this bot.",
        _LANG_JA: "このボットを使用する権限がありません。",
    },
    "no_permission_alert": {
        _LANG_ZH: "无权限使用",
        _LANG_EN: "No permission",
        _LANG_JA: "権限がありません",
    },

    # ── Search ──
    "search_actress": {
        _LANG_ZH: "🔍 请发送女优名字进行查询，例如：\n三上悠亚\n明日花キララ\nYua Mikami",
        _LANG_EN: "🔍 Send an actress name to search, e.g.:\nYua Mikami\nSora Aoi\nMaria Ozawa",
        _LANG_JA: "🔍 女優名を入力して検索してください。例：\n三上悠亜\n明日花キララ\nYua Mikami",
    },
    "search_loading": {
        _LANG_ZH: "查询中，请稍等...",
        _LANG_EN: "Searching, please wait...",
        _LANG_JA: "検索中、お待ちください...",
    },
    "search_failed": {
        _LANG_ZH: "查询失败，请稍后再试。",
        _LANG_EN: "Search failed, please try again later.",
        _LANG_JA: "検索に失敗しました。後でもう一度お試しください。",
    },
    "search_cancelled": {
        _LANG_ZH: "已取消查询",
        _LANG_EN: "Search cancelled",
        _LANG_JA: "検索をキャンセルしました",
    },
    "search_usage": {
        _LANG_ZH: "用法：/s 名字\n例如：/s 三上悠亚",
        _LANG_EN: "Usage: /s name\nExample: /s Yua Mikami",
        _LANG_JA: "使い方: /s 名前\n例: /s 三上悠亜",
    },
    "search_no_result": {
        _LANG_ZH: "❌ 未找到：<code>{}</code>",
        _LANG_EN: "❌ Not found: <code>{}</code>",
        _LANG_JA: "❌ 見つかりません: <code>{}</code>",
    },
    "search_suggestions": {
        _LANG_ZH: "💡 你可能想查：",
        _LANG_EN: "💡 Did you mean:",
        _LANG_JA: "💡 もしかして：",
    },
    "search_try_full_name": {
        _LANG_ZH: "💡 请尝试中文全名、日文名或英文名。",
        _LANG_EN: "💡 Try full name in Chinese, Japanese, or English.",
        _LANG_JA: "💡 中国語、日本語、または英語のフルネームをお試しください。",
    },
    "search_click_button": {
        _LANG_ZH: "点击下方按钮快速查询：",
        _LANG_EN: "Click a button to search:",
        _LANG_JA: "ボタンをクリックして検索：",
    },
    "search_magnet_for": {
        _LANG_ZH: "🧲 搜索 {} 磁力",
        _LANG_EN: "🧲 Search {} magnets",
        _LANG_JA: "🧲 {} をマグネット検索",
    },

    # ── Profile ──
    "profile_title": {
        _LANG_ZH: "👩 女优信息",
        _LANG_EN: "👩 Actress Info",
        _LANG_JA: "👩 女優情報",
    },
    "profile_name": {
        _LANG_ZH: "🎯 姓名：",
        _LANG_EN: "🎯 Name: ",
        _LANG_JA: "🎯 名前：",
    },
    "profile_id": {
        _LANG_ZH: "🆔 演员ID：",
        _LANG_EN: "🆔 Actress ID: ",
        _LANG_JA: "🆔 女優ID：",
    },
    "profile_match": {
        _LANG_ZH: "🔍 匹配关键词：",
        _LANG_EN: "🔍 Matched: ",
        _LANG_JA: "🔍 一致したキーワード：",
    },
    "profile_wiki": {
        _LANG_ZH: "📚 Wiki：",
        _LANG_EN: "📚 Wiki: ",
        _LANG_JA: "📚 Wiki：",
    },
    "profile_bio": {
        _LANG_ZH: "📋 个人简介",
        _LANG_EN: "📋 Biography",
        _LANG_JA: "📋 プロフィール",
    },
    "profile_birth": {
        _LANG_ZH: "• 🎂 出生日期：{}",
        _LANG_EN: "• 🎂 Birth: {}",
        _LANG_JA: "• 🎂 生年月日：{}",
    },
    "profile_height": {
        _LANG_ZH: "• 📏 身高：{}",
        _LANG_EN: "• 📏 Height: {}",
        _LANG_JA: "• 📏 身長：{}",
    },
    "profile_measurements": {
        _LANG_ZH: "• 👙 三围：{}",
        _LANG_EN: "• 👙 Measurements: {}",
        _LANG_JA: "• 👙 スリーサイズ：{}",
    },
    "profile_cup": {
        _LANG_ZH: "• 🚺 罩杯：{}",
        _LANG_EN: "• 🚺 Cup: {}",
        _LANG_JA: "• 🚺 カップ：{}",
    },
    "profile_social": {
        _LANG_ZH: "• 🌐 社媒：",
        _LANG_EN: "• 🌐 Social: ",
        _LANG_JA: "• 🌐 SNS：",
    },
        "profile_favorite": {
        _LANG_ZH: "☆ 收藏",
        _LANG_EN: "☆ Favorite",
        _LANG_JA: "☆ お気に入り",
    },
    "profile_favorited": {
        _LANG_ZH: "⭐ 已收藏",
        _LANG_EN: "⭐ Favorited",
        _LANG_JA: "⭐ お気に入り済み",
    },
    "profile_latest_works": {
        _LANG_ZH: "📰 最新作品",
        _LANG_EN: "📰 Latest Works",
        _LANG_JA: "📰 最新作品",
    },
        "works_empty": {
        _LANG_ZH: "暂未获取到作品信息。",
        _LANG_EN: "No works found.",
        _LANG_JA: "作品情報が見つかりません。",
    },
    "works_page": {
        _LANG_ZH: "第 {}/{} 页",
        _LANG_EN: "Page {}/{}",
        _LANG_JA: "{}/{} ページ",
    },

    # ── Magnet ──
    "magnet_result": {
        _LANG_ZH: "💾 磁力搜索",
        _LANG_EN: "💾 Magnet Search",
        _LANG_JA: "💾 マグネット検索",
    },
    "magnet_usage": {
        _LANG_ZH: "用法：/search 关键词\n例如：/search SSIS-123",
        _LANG_EN: "Usage: /search keyword\nExample: /search SSIS-123",
        _LANG_JA: "使い方: /search キーワード\n例: /search SSIS-123",
    },
    "magnet_no_result": {
        _LANG_ZH: "❌ 未找到结果。\n💡 试试：换关键词、用完整番号、或使用日文名。",
        _LANG_EN: "❌ No results found.\n💡 Try a different keyword, full AV ID, or Japanese name.",
        _LANG_JA: "❌ 結果が見つかりません。\n💡 別のキーワード、完全な品番、または日本語名をお試しください。",
    },
    "magnet_size": {
        _LANG_ZH: "📦 大小：",
        _LANG_EN: "📦 Size: ",
        _LANG_JA: "📦 サイズ：",
    },
    "magnet_link": {
        _LANG_ZH: "🧲 磁力：",
        _LANG_EN: "🧲 Magnet: ",
        _LANG_JA: "🧲 マグネット：",
    },
    "magnet_continue": {
        _LANG_ZH: "💾 磁力搜索（续）",
        _LANG_EN: "💾 Magnet Search (cont.)",
        _LANG_JA: "💾 マグネット検索（続き）",
    },
    "magnet_data_source": {
        _LANG_ZH: "🔧 数据来源：sukebei.nyaa.si",
        _LANG_EN: "🔧 Data source: sukebei.nyaa.si",
        _LANG_JA: "🔧 データソース：sukebei.nyaa.si",
    },
    "magnet_copy": {
        _LANG_ZH: "复制",
        _LANG_EN: "Copy",
        _LANG_JA: "コピー",
    },

    # ── Rank ──
    "rank_title": {
        _LANG_ZH: "🏆 热门女优排行榜",
        _LANG_EN: "🏆 Top Actresses Ranking",
        _LANG_JA: "🏆 人気女優ランキング",
    },
    "rank_source": {
        _LANG_ZH: "📊 来源：JavDb 排行榜（第{}页）",
        _LANG_EN: "📊 Source: JavDb Rankings (Page {})",
        _LANG_JA: "📊 ソース：JavDb ランキング（{}ページ）",
    },
    "rank_empty": {
        _LANG_ZH: "❌ 暂时无法获取榜单，请稍后再试。",
        _LANG_EN: "❌ Unable to fetch rankings. Try again later.",
        _LANG_JA: "❌ ランキングを取得できませんでした。後でもう一度お試しください。",
    },
    # ── Favorites ──
    "fav_empty": {
        _LANG_ZH: "你还没有收藏任何女优。\n\n使用 /fav 女优名字 来收藏女优\n例如：/fav 三上悠亚",
        _LANG_EN: "You haven't favorited any actresses yet.\n\nUse /fav name to add favorites\nExample: /fav Yua Mikami",
        _LANG_JA: "まだお気に入りの女優がいません。\n\n/fav 名前 でお気に入りに追加\n例：/fav 三上悠亜",
    },
    "fav_add_usage": {
        _LANG_ZH: "用法：/fav 女优名字\n例如：/fav 三上悠亚\n支持一次性添加多个女优，用逗号或分号分隔\n例如：/fav 三上悠亚, 苍井空; 波多野结衣",
        _LANG_EN: "Usage: /fav name\nExample: /fav Yua Mikami\nSeparate multiple names with commas or semicolons\nExample: /fav Yua Mikami, Sora Aoi",
        _LANG_JA: "使い方: /fav 名前\n例：/fav 三上悠亜\nカンマまたはセミコロンで区切って複数追加可能\n例：/fav 三上悠亜, 蒼井そら",
    },
    "fav_unfav_usage": {
        _LANG_ZH: "用法：/unfav 女优名字\n例如：/unfav 三上悠亚\n支持一次性取消多个收藏，用逗号或分号分隔\n例如：/unfav 三上悠亚, 苍井空; 波多野结衣",
        _LANG_EN: "Usage: /unfav name\nExample: /unfav Yua Mikami\nSeparate multiple names with commas or semicolons",
        _LANG_JA: "使い方: /unfav 名前\n例：/unfav 三上悠亜\nカンマまたはセミコロンで区切って複数削除可能",
    },
    "fav_querying": {
        _LANG_ZH: "正在查询 {} 位女优...",
        _LANG_EN: "Searching {} actresses...",
        _LANG_JA: "{} 人の女優を検索中...",
    },
    "fav_unfav_querying": {
        _LANG_ZH: "正在取消收藏 {} 位女优...",
        _LANG_EN: "Removing {} favorites...",
        _LANG_JA: "{} 人のお気に入りを削除中...",
    },
    "fav_added": {
        _LANG_ZH: "✅ 已收藏: {}",
        _LANG_EN: "✅ Favorited: {}",
        _LANG_JA: "✅ お気に入りに追加: {}",
    },
    "fav_add_failed": {
        _LANG_ZH: "❌ 收藏失败: {}",
        _LANG_EN: "❌ Failed to favorite: {}",
        _LANG_JA: "❌ お気に入りに追加できません: {}",
    },
    "fav_removed": {
        _LANG_ZH: "✅ 已取消收藏: {}",
        _LANG_EN: "✅ Removed: {}",
        _LANG_JA: "✅ お気に入りを削除: {}",
    },
    "fav_remove_failed": {
        _LANG_ZH: "❌ 取消收藏失败: {}",
        _LANG_EN: "❌ Failed to remove: {}",
        _LANG_JA: "❌ 削除できません: {}",
    },
    "fav_not_found": {
        _LANG_ZH: "❌ 未找到收藏: {}",
        _LANG_EN: "❌ Favorite not found: {}",
        _LANG_JA: "❌ お気に入りが見つかりません: {}",
    },
    "fav_no_valid": {
        _LANG_ZH: "未找到有效的女优名字",
        _LANG_EN: "No valid actress names found",
        _LANG_JA: "有効な女優名が見つかりません",
    },
    "fav_list_title": {
        _LANG_ZH: "📚 我的收藏",
        _LANG_EN: "📚 My Favorites",
        _LANG_JA: "📚 お気に入り",
    },
    "fav_exported": {
        _LANG_ZH: "📥 已导出 {} 条收藏记录",
        _LANG_EN: "📥 Exported {} favorite records",
        _LANG_JA: "📥 {} 件のお気に入りをエクスポート",
    },
    "fav_export_empty": {
        _LANG_ZH: "暂无收藏可导出。使用 /fav 名字 开始收藏。",
        _LANG_EN: "No favorites to export. Use /fav to start adding.",
        _LANG_JA: "エクスポートできるお気に入りがありません。/fav で追加してください。",
    },
    "fav_myfav_hint": {
        _LANG_ZH: "\n\n使用 /myfav 查看所有收藏\n使用 /favlatest 查看收藏女优的最新作品",
        _LANG_EN: "\n\nUse /myfav to view all favorites\nUse /favlatest to see latest works",
        _LANG_JA: "\n\n/myfav ですべてのお気に入りを表示\n/favlatest で最新作品を表示",
    },
    "fav_expired": {
        _LANG_ZH: "该链接已过期，请重新搜索",
        _LANG_EN: "This link has expired. Please search again.",
        _LANG_JA: "このリンクは期限切れです。もう一度検索してください。",
    },
    "fav_found": {
        _LANG_ZH: "未找到女优: {}",
        _LANG_EN: "Actress not found: {}",
        _LANG_JA: "女優が見つかりません: {}",
    },

    # ── Favorites page ──
    "fav_page_prev": {
        _LANG_ZH: "◀️ 上一页",
        _LANG_EN: "◀️ Previous Page",
        _LANG_JA: "◀️ 前のページ",
    },
    "fav_page_next": {
        _LANG_ZH: "下一页 ▶️",
        _LANG_EN: "Next Page ▶️",
        _LANG_JA: "次のページ ▶️",
    },
    # ── Sort labels ──
    "sort_date": {
        _LANG_ZH: "收藏时间",
        _LANG_EN: "Date",
        _LANG_JA: "保存日",
    },
    "sort_name": {
        _LANG_ZH: "名称",
        _LANG_EN: "Name",
        _LANG_JA: "名前",
    },
    "sort_recent": {
        _LANG_ZH: "最近查询",
        _LANG_EN: "Recent",
        _LANG_JA: "最近検索",
    },
    "sort_changed": {
        _LANG_ZH: "排序切换: {}",
        _LANG_EN: "Sort changed: {}",
        _LANG_JA: "並び替え: {}",
    },
    "sort_label": {
        _LANG_ZH: "排序: {}",
        _LANG_EN: "Sort: {}",
        _LANG_JA: "並び替え: {}",
    },
    "fav_total": {
        _LANG_ZH: "共 {} 位",
        _LANG_EN: "{} total",
        _LANG_JA: "合計 {}",
    },
    "fav_page_info": {
        _LANG_ZH: "第 {}/{} 页",
        _LANG_EN: "Page {}/{}",
        _LANG_JA: "{}/{} ページ",
    },

    # ── Work display ──
    "work_date_unknown": {
        _LANG_ZH: "未知",
        _LANG_EN: "Unknown",
        _LANG_JA: "不明",
    },

    # ── History ──
    "history_title": {
        _LANG_ZH: "📜 最近搜索",
        _LANG_EN: "📜 Recent Searches",
        _LANG_JA: "📜 最近の検索",
    },
    "history_empty": {
        _LANG_ZH: "暂无搜索历史。\n\n使用 /s 名字 查询女优信息，搜索记录会自动保存。",
        _LANG_EN: "No search history yet.\n\nUse /s to search for actresses. Your history will be saved automatically.",
        _LANG_JA: "検索履歴がありません。\n\n/s 名前 で女優を検索すると履歴が自動保存されます。",
    },
    # ── Push ──
    # ── Language ──
    "lang_current": {
        _LANG_ZH: "🌐 当前语言：{}",
        _LANG_EN: "🌐 Current language: {}",
        _LANG_JA: "🌐 現在の言語：{}",
    },
    "lang_set": {
        _LANG_ZH: "✅ 已切换至 {}",
        _LANG_EN: "✅ Switched to {}",
        _LANG_JA: "✅ {} に切り替えました",
    },
    "lang_usage": {
        _LANG_ZH: "用法：/language 代码\n支持的语言：zh_CN (中文), en_US (English), ja_JP (日本語)",
        _LANG_EN: "Usage: /language code\nSupported: zh_CN (中文), en_US (English), ja_JP (日本語)",
        _LANG_JA: "使い方: /language コード\n対応言語：zh_CN (中文), en_US (English), ja_JP (日本語)",
    },
    "stats_title": {
        _LANG_ZH: "使用统计",
        _LANG_EN: "Usage Statistics",
        _LANG_JA: "使用統計",
    },
    "lang_invalid": {
        _LANG_ZH: "不支持的语言代码。支持：{}",
        _LANG_EN: "Unsupported language code. Supported: {}",
        _LANG_JA: "サポートされていない言語コードです。対応言語：{}",
    },
    # ── Errors ──
    "error_generic": {
        _LANG_ZH: "操作失败，请稍后再试。",
        _LANG_EN: "Operation failed, please try again later.",
        _LANG_JA: "操作に失敗しました。後でもう一度お試しください。",
    },
    }


class I18nService:
    """Translation service using dict-based lookup."""

    DEFAULT_LANG = _LANG_ZH

    def __init__(self, default_lang: str = _LANG_ZH):
        self._default_lang = default_lang if default_lang in SUPPORTED_LANGUAGES else _LANG_ZH

    def t(self, key: str, lang: Optional[str] = None, *args) -> str:
        """Translate a key to the given language, with optional positional format args.

        Fallback chain: requested lang → default lang → key itself.
        """
        lang = lang if lang in SUPPORTED_LANGUAGES else self._default_lang

        entry = _TRANSLATIONS.get(key)
        if not entry:
            return key

        text = entry.get(lang) or entry.get(self._default_lang) or key

        if args:
            try:
                text = text.format(*args)
            except (KeyError, IndexError):
                pass

        return text

    def supported_languages(self) -> Dict[str, str]:
        return dict(LANGUAGE_NAMES)

    def is_supported(self, lang: str) -> bool:
        return lang in SUPPORTED_LANGUAGES
