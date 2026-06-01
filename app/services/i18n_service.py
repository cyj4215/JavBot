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
    "profile_top_works": {
        _LANG_ZH: "🏆 高分作品",
        _LANG_EN: "🏆 Top Works",
        _LANG_JA: "🏆 高評価作品",
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
    "profile_view_works": {
        _LANG_ZH: "📼 全部作品",
        _LANG_EN: "📼 All Works",
        _LANG_JA: "📼 全作品",
    },
    "works_actions": {
        _LANG_ZH: "点击下方按钮搜索对应作品的磁力链接：",
        _LANG_EN: "Click below to search magnets for each work:",
        _LANG_JA: "各作品のマグネットリンクを検索：",
    },
    "works_title": {
        _LANG_ZH: "🎬 {} 的作品",
        _LANG_EN: "🎬 {}'s Works",
        _LANG_JA: "🎬 {} の作品",
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
    "magnet_loading": {
        _LANG_ZH: "正在查询，请稍等...",
        _LANG_EN: "Searching magnets, please wait...",
        _LANG_JA: "マグネット検索中、お待ちください...",
    },
    "magnet_searching": {
        _LANG_ZH: "正在搜索磁力，请稍等...",
        _LANG_EN: "Searching for magnet links...",
        _LANG_JA: "マグネットリンクを検索中...",
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
    "magnet_failed": {
        _LANG_ZH: "搜索失败，请稍后再试。",
        _LANG_EN: "Search failed, please try again later.",
        _LANG_JA: "検索に失敗しました。後でもう一度お試しください。",
    },
    "magnet_detail": {
        _LANG_ZH: "🎬 作品详情",
        _LANG_EN: "🎬 Work Details",
        _LANG_JA: "🎬 作品詳細",
    },
    "magnet_id": {
        _LANG_ZH: "番号：",
        _LANG_EN: "ID: ",
        _LANG_JA: "品番：",
    },
    "magnet_title": {
        _LANG_ZH: "标题：",
        _LANG_EN: "Title: ",
        _LANG_JA: "タイトル：",
    },
    "magnet_date": {
        _LANG_ZH: "日期：",
        _LANG_EN: "Date: ",
        _LANG_JA: "日付：",
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
    "rank_loading": {
        _LANG_ZH: "正在获取热门女优排行榜...",
        _LANG_EN: "Fetching top actresses ranking...",
        _LANG_JA: "人気女優ランキングを取得中...",
    },
    "rank_empty": {
        _LANG_ZH: "❌ 暂时无法获取榜单，请稍后再试。",
        _LANG_EN: "❌ Unable to fetch rankings. Try again later.",
        _LANG_JA: "❌ ランキングを取得できませんでした。後でもう一度お試しください。",
    },
    "rank_failed": {
        _LANG_ZH: "获取榜单失败，请稍后再试。\n点击下方按钮重试：",
        _LANG_EN: "Failed to fetch rankings. Try again later.\nClick the button below to retry:",
        _LANG_JA: "ランキングの取得に失敗しました。後でもう一度お試しください。\n下のボタンをクリックして再試行：",
    },
    "rank_still_loading": {
        _LANG_ZH: "⏳ 排行榜数据正在后台加载中，请稍后再试。\n点击下方按钮重试：",
        _LANG_EN: "⏳ Rankings are loading in the background. Try again later.\nClick the button below to retry:",
        _LANG_JA: "⏳ ランキングデータをバックグラウンドで読み込み中です。後でもう一度お試しください。\n下のボタンをクリックして再試行：",
    },
    "rank_cached": {
        _LANG_ZH: "⚠️ 最新数据获取失败，显示缓存数据",
        _LANG_EN: "⚠️ Failed to fetch latest data, showing cached data",
        _LANG_JA: "⚠️ 最新データの取得に失敗しました。キャッシュデータを表示しています",
    },
    "rank_retry": {
        _LANG_ZH: "🔄 重试",
        _LANG_EN: "🔄 Retry",
        _LANG_JA: "🔄 再試行",
    },
    "rank_retrying": {
        _LANG_ZH: "正在重试...",
        _LANG_EN: "Retrying...",
        _LANG_JA: "再試行中...",
    },
    "rank_next": {
        _LANG_ZH: "下一页 ▶️",
        _LANG_EN: "Next ▶️",
        _LANG_JA: "次へ ▶️",
    },
    "rank_prev": {
        _LANG_ZH: "◀️ 上一页",
        _LANG_EN: "◀️ Previous",
        _LANG_JA: "◀️ 前へ",
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
    "fav_list_count": {
        _LANG_ZH: "共收藏 {} 位女优",
        _LANG_EN: "{} actresses favorited",
        _LANG_JA: "{} 人の女優をお気に入り登録",
    },
    "fav_list_page": {
        _LANG_ZH: "第 {}/{} 页",
        _LANG_EN: "Page {}/{}",
        _LANG_JA: "{}/{} ページ",
    },
    "fav_list_hint": {
        _LANG_ZH: "点击名字可快速查询最新作品：",
        _LANG_EN: "Click a name to see latest works:",
        _LANG_JA: "名前をクリックして最新作品を表示：",
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
    "fav_latest_loading": {
        _LANG_ZH: "正在查询 {} 位收藏女优的最新作品...",
        _LANG_EN: "Fetching latest works for {} favorites...",
        _LANG_JA: "{} 人のお気に入り女優の最新作品を取得中...",
    },
    "fav_latest_title": {
        _LANG_ZH: "🎬 收藏女优最新作品",
        _LANG_EN: "🎬 Latest Favorites Works",
        _LANG_JA: "🎬 お気に入り女優の最新作品",
    },
    "fav_latest_empty": {
        _LANG_ZH: "暂无最新作品信息。",
        _LANG_EN: "No latest works available.",
        _LANG_JA: "最新作品情報はありません。",
    },
    "fav_latest_more": {
        _LANG_ZH: "...还有 {} 部作品",
        _LANG_EN: "...and {} more works",
        _LANG_JA: "...あと {} 作品",
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
    "fav_view_all_latest": {
        _LANG_ZH: "📰 查看所有收藏的最新作品",
        _LANG_EN: "📰 View all favorites latest works",
        _LANG_JA: "📰 お気に入り全員の最新作品を見る",
    },
    "fav_saved_at": {
        _LANG_ZH: "(收藏于: {})",
        _LANG_EN: "(saved: {})",
        _LANG_JA: "(保存日: {})",
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
    "history_count": {
        _LANG_ZH: "共 {} 条记录",
        _LANG_EN: "{} records",
        _LANG_JA: "{} 件の記録",
    },
    "history_empty": {
        _LANG_ZH: "暂无搜索历史。\n\n使用 /s 名字 查询女优信息，搜索记录会自动保存。",
        _LANG_EN: "No search history yet.\n\nUse /s to search for actresses. Your history will be saved automatically.",
        _LANG_JA: "検索履歴がありません。\n\n/s 名前 で女優を検索すると履歴が自動保存されます。",
    },
    "history_re_search": {
        _LANG_ZH: "点击按钮重新查询",
        _LANG_EN: "Click a button to search again",
        _LANG_JA: "ボタンをクリックして再検索",
    },

    # ── Push ──
    "push_status": {
        _LANG_ZH: "📰 新作品推送状态：{}",
        _LANG_EN: "📰 New works push status: {}",
        _LANG_JA: "📰 新作プッシュ通知状態：{}",
    },
    "push_enabled_text": {
        _LANG_ZH: "✅ 已开启",
        _LANG_EN: "✅ Enabled",
        _LANG_JA: "✅ 有効",
    },
    "push_disabled_text": {
        _LANG_ZH: "❌ 已关闭",
        _LANG_EN: "❌ Disabled",
        _LANG_JA: "❌ 無効",
    },
    "push_usage": {
        _LANG_ZH: "使用 /push on 开启推送\n使用 /push off 关闭推送",
        _LANG_EN: "Use /push on to enable\nUse /push off to disable",
        _LANG_JA: "/push on で有効にする\n/push off で無効にする",
    },
    "push_enabled_msg": {
        _LANG_ZH: "✅ 已开启新作品推送\n\n当你关注的女优有新作品时，我会及时通知你！",
        _LANG_EN: "✅ Push notifications enabled!\n\nI'll notify you when your favorited actresses have new works!",
        _LANG_JA: "✅ 新作プッシュ通知を有効にしました！\n\nお気に入りの女優に新作があればお知らせします！",
    },
    "push_disabled_msg": {
        _LANG_ZH: "❌ 已关闭新作品推送",
        _LANG_EN: "❌ Push notifications disabled",
        _LANG_JA: "❌ 新作プッシュ通知を無効にしました",
    },
    "push_toggle_usage": {
        _LANG_ZH: "用法：/push [on|off]",
        _LANG_EN: "Usage: /push [on|off]",
        _LANG_JA: "使い方: /push [on|off]",
    },
    "push_notification_title": {
        _LANG_ZH: "🎉 关注女优更新啦！",
        _LANG_EN: "🎉 New work from your favorite!",
        _LANG_JA: "🎉 お気に入り女優の新作です！",
    },

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
    "lang_prompt": {
        _LANG_ZH: "请选择语言 / Choose language / 言語を選択：",
        _LANG_EN: "Please select a language / 请选择语言 / 言語を選択：",
        _LANG_JA: "言語を選択 / Please select a language / 请选择语言：",
    },

    # ── Errors ──
    "error_generic": {
        _LANG_ZH: "操作失败，请稍后再试。",
        _LANG_EN: "Operation failed, please try again later.",
        _LANG_JA: "操作に失敗しました。後でもう一度お試しください。",
    },
    "error_expired": {
        _LANG_ZH: "链接已过期，请重新操作",
        _LANG_EN: "Link has expired. Please try again.",
        _LANG_JA: "リンクの期限が切れています。もう一度操作してください。",
    },
    "error_not_found": {
        _LANG_ZH: "未找到女优: {}",
        _LANG_EN: "Actress not found: {}",
        _LANG_JA: "女優が見つかりません: {}",
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
