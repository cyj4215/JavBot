import os
from dataclasses import dataclass
from typing import Optional


def _env_bool(key: str, default: str = "1") -> bool:
    return os.getenv(key, default).strip() not in ("0", "false", "False")


def _env_int(key: str, default: str) -> int:
    raw = os.getenv(key, default)
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"环境变量 {key} 的值 '{raw}' 不是合法整数") from None


@dataclass
class BotConfig:
    token: str
    proxy_addr: str
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    latest_limit: int
    top_limit: int
    send_latest_covers: bool
    latest_cover_limit: int
    magnet_limit: int
    magnet_timeout: int
    profile_cache_ttl: int
    uncensored: bool
    allowed_user_ids: set[int]
    push_check_interval: int
    push_enabled_global: bool
    admin_user_id: Optional[int]
    log_level: str
    i18n_default_language: str
    rank_limit_default: int
    rank_page_default: int
    rank_cache_ttl: int
    rank_feature_avatars: bool
    rank_avatar_limit: int

    @classmethod
    def from_env(cls) -> "BotConfig":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

        admin_user_id_raw = os.getenv("ADMIN_USER_ID", "").strip()
        admin_user_id = int(admin_user_id_raw) if admin_user_id_raw.isdigit() else None

        return cls(
            token=token,
            proxy_addr=os.getenv("HTTP_PROXY", "").strip(),
            mysql_host=os.getenv("MYSQL_HOST", "127.0.0.1").strip(),
            mysql_port=_env_int("MYSQL_PORT", "3306"),
            mysql_user=os.getenv("MYSQL_USER", "javbot").strip(),
            mysql_password=os.getenv("MYSQL_PASSWORD", "javbot").strip(),
            mysql_database=os.getenv("MYSQL_DATABASE", "javbot").strip(),
            latest_limit=_env_int("LATEST_LIMIT", "5"),
            top_limit=_env_int("TOP_LIMIT", "5"),
            send_latest_covers=_env_bool("SEND_LATEST_COVERS"),
            latest_cover_limit=_env_int("LATEST_COVER_LIMIT", "3"),
            magnet_limit=_env_int("MAGNET_LIMIT", "5"),
            magnet_timeout=_env_int("MAGNET_TIMEOUT", "20"),
            profile_cache_ttl=_env_int("PROFILE_CACHE_TTL", "1800"),
            uncensored=_env_bool("UNCENSORED", "0"),
            allowed_user_ids={
                int(v.strip())
                for v in os.getenv("ALLOWED_USER_IDS", "").split(",")
                if v.strip().isdigit()
            },
            push_check_interval=_env_int("PUSH_CHECK_INTERVAL", "3600"),
            push_enabled_global=_env_bool("PUSH_ENABLED"),
            admin_user_id=admin_user_id,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            i18n_default_language=os.getenv("I18N_DEFAULT_LANGUAGE", "zh_CN").strip(),
            rank_limit_default=_env_int("RANK_LIMIT_DEFAULT", "20"),
            rank_page_default=_env_int("RANK_PAGE_DEFAULT", "1"),
            rank_cache_ttl=_env_int("RANK_CACHE_TTL", "900"),
            rank_feature_avatars=_env_bool("RANK_FEATURE_AVATARS", "0"),
            rank_avatar_limit=_env_int("RANK_AVATAR_LIMIT", "3"),
        )
