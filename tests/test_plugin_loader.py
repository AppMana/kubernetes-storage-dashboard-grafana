from __future__ import annotations

import textwrap
from pathlib import Path

from exporter import plugin_loader
from exporter.categories.base import BaseCategory


def test_loads_py_files_and_subclass_registers(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / "my_plugin.py").write_text(
        textwrap.dedent("""
        from exporter.categories.base import DuPathCategory

        class MyAppCacheCategory(DuPathCategory):
            name = "my-app-cache"
            path = "/var/lib/my-app/cache"
        """).lstrip()
    )

    loaded = plugin_loader.load_plugins(str(plugins))
    try:
        assert len(loaded) == 1
        cls = BaseCategory.resolve("MyAppCache")
        assert cls.__name__ == "MyAppCacheCategory"
        instance = cls()
        assert instance.name == "my-app-cache"
        assert instance.path == "/var/lib/my-app/cache"
    finally:
        BaseCategory._registry.pop("MyAppCache", None)
        BaseCategory._registry.pop("MyAppCacheCategory", None)


def test_missing_dir_returns_empty(tmp_path: Path) -> None:
    assert plugin_loader.load_plugins(str(tmp_path / "nonexistent")) == []


def test_broken_plugin_does_not_break_startup(tmp_path: Path, capsys) -> None:
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / "good.py").write_text(
        "from exporter.categories.base import DuPathCategory\n"
        "class GoodOneCategory(DuPathCategory):\n"
        "    name = 'good-one'\n"
        "    path = '/tmp/good'\n"
    )
    (plugins / "broken.py").write_text("this is not python at all !!!\n")
    (plugins / "_skipped.py").write_text("raise RuntimeError('should be skipped')\n")

    try:
        loaded = plugin_loader.load_plugins(str(plugins))
        captured = capsys.readouterr()
        assert any("GoodOne" in n or "good" in n for n in loaded)
        assert "broken.py failed to load" in captured.out
        # _skipped.py starts with underscore, so plugin_loader ignores it.
        assert "_skipped.py" not in captured.out
        assert BaseCategory.resolve("GoodOne").__name__ == "GoodOneCategory"
    finally:
        BaseCategory._registry.pop("GoodOne", None)
        BaseCategory._registry.pop("GoodOneCategory", None)
