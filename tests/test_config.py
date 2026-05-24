from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from exporter import config
from exporter.categories.apt_cache import AptCacheCategory
from exporter.categories.base import BaseCategory, DuPath
from exporter.categories.home import HomeCategory


def test_load_defaults_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONFIG_FILE", raising=False)
    cfg = config.load(str(tmp_path / "does-not-exist.yaml"))
    assert cfg.metric_prefix == "nsd"
    assert cfg.interval_seconds == 300
    types = {type(c).__name__ for c in cfg.categories}
    # Spot-check that a few built-ins are wired up.
    assert "AptCacheCategory" in types
    assert "HomeCategory" in types
    assert "ContainerdImagesCategory" in types
    assert "FilesystemCategory" in types
    assert "LocalPathProvisionerCategory" in types


def test_user_overrides_categories_list_wholesale(tmp_path: Path) -> None:
    p = tmp_path / "user.yaml"
    p.write_text(
        textwrap.dedent("""
        metric_prefix: foo
        categories:
          - { type: Home }
          - { type: AptCache }
        """).lstrip()
    )
    cfg = config.load(str(p))
    assert cfg.metric_prefix == "foo"
    assert len(cfg.categories) == 2
    assert isinstance(cfg.categories[0], HomeCategory)
    assert isinstance(cfg.categories[1], AptCacheCategory)


def test_env_overrides_take_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METRIC_PREFIX", "envwins")
    monkeypatch.setenv("INTERVAL_SECONDS", "42")
    cfg = config.load(str(tmp_path / "does-not-exist.yaml"))
    assert cfg.metric_prefix == "envwins"
    assert cfg.interval_seconds == 42


def test_inline_dupath_from_config(tmp_path: Path) -> None:
    p = tmp_path / "user.yaml"
    p.write_text(
        textwrap.dedent("""
        categories:
          - type: DuPath
            name: my-app
            path: /var/lib/my-app
        """).lstrip()
    )
    cfg = config.load(str(p))
    assert len(cfg.categories) == 1
    cat = cfg.categories[0]
    assert isinstance(cat, DuPath)
    assert cat.name == "my-app"
    assert cat.path == "/var/lib/my-app"


def test_class_name_full_form_also_works(tmp_path: Path) -> None:
    p = tmp_path / "user.yaml"
    p.write_text(
        textwrap.dedent("""
        categories:
          - HomeCategory      # full class name
          - Home              # short form
        """).lstrip()
    )
    cfg = config.load(str(p))
    assert len(cfg.categories) == 2
    assert isinstance(cfg.categories[0], HomeCategory)
    assert isinstance(cfg.categories[1], HomeCategory)


def test_unknown_category_type_raises(tmp_path: Path) -> None:
    p = tmp_path / "user.yaml"
    p.write_text("categories: [ DoesNotExist ]\n")
    with pytest.raises(KeyError, match="DoesNotExist"):
        config.load(str(p))


def test_dupath_missing_kwargs_raises(tmp_path: Path) -> None:
    p = tmp_path / "user.yaml"
    p.write_text("categories: [ { type: DuPath, name: x } ]\n")  # missing path
    with pytest.raises(ValueError, match="requires both"):
        config.load(str(p))


def test_registry_lists_all_builtins() -> None:
    names = BaseCategory.registered_names()
    for expected in [
        "AptCache", "Buildkit", "ContainerdImages", "CrashDumps",
        "Dockerd", "Filesystem", "Fscache", "Home", "Journald",
        "LocalPathProvisioner", "PodEphemeral", "Snap", "Swap",
        "DuPath", "EnumDirPath",
    ]:
        assert expected in names, f"missing built-in: {expected} (have {names})"
