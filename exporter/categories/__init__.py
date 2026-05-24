"""Built-in category plugins.

Each .py file in this directory defines one category (or one family of
categories) by subclassing a base class from `exporter.categories.base`.
Subclasses auto-register via __init_subclass__, so importing the module
is enough to make the category available to config.

Users add new categories by dropping additional .py files into
plugins_dir (defaults to /etc/storage-exporter/plugins.d); see
exporter.plugin_loader.
"""
from __future__ import annotations

# Import every built-in category module so __init_subclass__ runs and the
# class becomes resolvable from config by name. Order doesn't matter.
from exporter.categories import (  # noqa: F401
    apt_cache,
    buildkit,
    containerd_images,
    crash_dumps,
    dockerd,
    filesystem,
    fscache,
    home,
    journald,
    local_path_provisioner,
    pod_ephemeral,
    snap,
    swap,
)
