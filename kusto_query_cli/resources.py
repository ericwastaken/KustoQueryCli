"""Locate repository/container resources independently of the caller's directory."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESOURCE_ROOT = Path(__file__).resolve().parent / "assets"
VERSION_FILE = RESOURCE_ROOT / "mcp-wrapper-version"
PROTOCOL_VERSION_FILE = RESOURCE_ROOT / "mcp-protocol-version"
MANIFEST_FILE = RESOURCE_ROOT / "mcp-manifest.json"


def load_version():
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def load_protocol_version():
    return PROTOCOL_VERSION_FILE.read_text(encoding="utf-8").strip()
