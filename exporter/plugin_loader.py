"""Load user-supplied category plugin .py files at startup.

A plugin file is a Python module that subclasses one of the classes
in `exporter.categories.base`. Importing the file is enough, because
subclasses auto-register via `__init_subclass__`. After registration
the category is referenceable from YAML config by its class name.

Plugin dir defaults to /etc/storage-exporter/plugins.d (set
`plugins_dir:` in the config YAML to override). The directory is
scanned shallowly; subdirectories are ignored. Files that fail to
import log a warning and the startup continues, so one broken plugin
will not bring the whole exporter down.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import traceback
from pathlib import Path

DEFAULT_PLUGINS_DIR = "/etc/storage-exporter/plugins.d"


def load_plugins(plugins_dir: str | None = None) -> list[str]:
    """Import every *.py file under plugins_dir. Returns module names loaded."""
    if plugins_dir is None:
        plugins_dir = os.environ.get("PLUGINS_DIR", DEFAULT_PLUGINS_DIR)
    p = Path(plugins_dir)
    if not p.is_dir():
        return []
    loaded: list[str] = []
    for path in sorted(p.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module_name = f"ksdg_plugin_{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                print(f"plugin {path.name}: could not build import spec", flush=True)
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            loaded.append(module_name)
            print(f"plugin loaded: {path.name}", flush=True)
        except Exception:
            print(f"plugin {path.name} failed to load:", flush=True)
            traceback.print_exc()
    return loaded
