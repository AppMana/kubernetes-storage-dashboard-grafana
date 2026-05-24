"""Configuration loader.

Loads the built-in defaults.yaml, deep-merges a user config file on
top, then resolves the `categories:[]` list into instantiated
BaseCategory objects (after importing any plugin files so their
subclasses are registered).
"""
from __future__ import annotations

import importlib.resources
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

import exporter.categories  # noqa: F401  (registers built-in categories)
from exporter.categories.base import BaseCategory
from exporter.plugin_loader import DEFAULT_PLUGINS_DIR, load_plugins

DEFAULTS_RESOURCE = "defaults.yaml"
USER_CONFIG_PATH_ENV = "CONFIG_FILE"
DEFAULT_USER_CONFIG_PATH = "/etc/storage-exporter/config.yaml"


def _load_defaults() -> dict[str, Any]:
    text = importlib.resources.files("exporter").joinpath(DEFAULTS_RESOURCE).read_text()
    loaded = yaml.safe_load(text)
    assert isinstance(loaded, dict)
    return loaded


def _load_user(path: str | None) -> dict[str, Any]:
    if path is None:
        path = os.environ.get(USER_CONFIG_PATH_ENV, DEFAULT_USER_CONFIG_PATH)
    p = Path(path)
    if not p.is_file():
        return {}
    return yaml.safe_load(p.read_text()) or {}


def _merge(defaults: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    # Deep-merge dicts; lists are REPLACED, not concatenated. So a user
    # config that re-lists `categories:` fully replaces the default set
    # (the convention everyone expects from values overlays).
    out = dict(defaults)
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _apply_env(cfg: dict[str, Any]) -> dict[str, Any]:
    overrides = {
        "metric_prefix":      os.environ.get("METRIC_PREFIX"),
        "interval_seconds":   os.environ.get("INTERVAL_SECONDS"),
        "du_timeout_seconds": os.environ.get("DU_TIMEOUT_SECONDS"),
        "listen_port":        os.environ.get("LISTEN_PORT"),
        "plugins_dir":        os.environ.get("PLUGINS_DIR"),
    }
    for k, v in overrides.items():
        if v is None:
            continue
        if k in ("interval_seconds", "du_timeout_seconds", "listen_port"):
            cfg[k] = int(v)
        else:
            cfg[k] = v
    return cfg


@dataclass(frozen=True)
class Config:
    metric_prefix: str
    interval_seconds: int
    du_timeout_seconds: int
    listen_port: int
    categories: list[BaseCategory]
    plugins_dir: str
    raw: dict[str, Any]


def load(path: str | None = None) -> Config:
    """Load config + plugins + instantiate every enabled category."""
    raw = _apply_env(_merge(_load_defaults(), _load_user(path)))

    plugins_dir = raw.get("plugins_dir", DEFAULT_PLUGINS_DIR)
    load_plugins(plugins_dir)

    categories: list[BaseCategory] = []
    for entry in raw.get("categories") or []:
        # Each entry is either a string ("Home": instantiate Home with no
        # args) or a dict ({type: Home, ...kwargs}).
        if isinstance(entry, str):
            type_name = entry
            kwargs: dict[str, Any] = {}
        elif isinstance(entry, dict):
            entry = dict(entry)  # don't mutate caller's dict
            type_name = entry.pop("type", None)
            if type_name is None:
                raise ValueError(f"category entry missing `type`: {entry}")
            kwargs = entry
        else:
            raise TypeError(f"invalid category entry: {entry!r}")

        cls = BaseCategory.resolve(type_name)
        try:
            categories.append(cls(**kwargs))
        except TypeError as e:
            raise ValueError(
                f"failed to instantiate {type_name} with {kwargs}: {e}"
            ) from e

    return Config(
        metric_prefix=raw["metric_prefix"],
        interval_seconds=int(raw["interval_seconds"]),
        du_timeout_seconds=int(raw["du_timeout_seconds"]),
        listen_port=int(raw["listen_port"]),
        categories=categories,
        plugins_dir=plugins_dir,
        raw=raw,
    )
