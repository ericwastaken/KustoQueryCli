"""Persistent proxy configuration used by action-based clients."""
import json
import os

PROXY_CONFIG_FILE = os.path.expanduser("~/.azure/mcp_proxy_config.json")


def _to_bool(value, default: bool = False) -> bool:
    """Best-effort boolean coercion for loose client inputs."""
    try:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            if value == 1:
                return True
            if value == 0:
                return False
            return default
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"true", "1", "yes", "on", "t", "y"}:
                return True
            if v in {"false", "0", "no", "off", "f", "n"}:
                return False
            return default
    except Exception:
        pass
    return default


def _normalize_proxy_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return str(value).strip() or None


def _disabled_proxy_config() -> dict:
    return {
        "proxy_enabled": False,
        "socks5_proxy": None,
        "socks5_dns": False,
    }


def _normalize_proxy_config(raw: dict | None) -> dict:
    if not isinstance(raw, dict):
        return _disabled_proxy_config()
    proxy = _normalize_proxy_value(raw.get("socks5_proxy"))
    dns = _to_bool(raw.get("socks5_dns"), False)
    if not proxy:
        return _disabled_proxy_config()
    return {
        "proxy_enabled": True,
        "socks5_proxy": proxy,
        "socks5_dns": dns,
    }


def _load_proxy_config() -> dict:
    try:
        with open(PROXY_CONFIG_FILE, "r", encoding="utf-8") as f:
            return _normalize_proxy_config(json.load(f))
    except Exception:
        return _disabled_proxy_config()


def _save_proxy_config(config: dict) -> dict:
    normalized = _normalize_proxy_config(config)
    os.makedirs(os.path.dirname(PROXY_CONFIG_FILE), exist_ok=True)
    with open(PROXY_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "socks5_proxy": normalized["socks5_proxy"],
                "socks5_dns": normalized["socks5_dns"],
            },
            f,
            separators=(",", ":"),
        )
    return normalized


def _clear_proxy_config() -> dict:
    try:
        os.remove(PROXY_CONFIG_FILE)
    except FileNotFoundError:
        pass
    return _disabled_proxy_config()
