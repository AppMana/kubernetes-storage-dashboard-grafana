"""Base classes for category collectors.

Plugin authors should pick the most specific base class that fits, in
order of preference:

  DuPathCategory          Walks one fixed host path with `du`.
  EnumDirPathCategory     Walks each subdirectory of one root with `du`,
                          classifying by name via regex + rule list.
  KubeletStatCategory     Pulls one number from kubelet /stats/summary.
  BaseCategory            Anything else (custom file parsing, multiple
                          paths with custom logic, etc.).

A subclass becomes available to config by being defined. The class is
auto-registered under its class name with the trailing "Category"
stripped, so `AptCacheCategory` registers as `AptCache`.

To author a new plugin, drop a .py file into the configured
`plugins_dir` (defaults to /etc/storage-exporter/plugins.d). At
startup the exporter imports each plugin file, then instantiates every
category listed in `config.categories[]` by class name. Example
plugin:

    from exporter.categories.base import DuPathCategory

    class FooCacheCategory(DuPathCategory):
        name = "foo-cache"
        path = "/var/lib/foo"

Reference from config:

    categories:
      - type: FooCache       # the trailing "Category" is optional
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from exporter import utils

# ---------------------------------------------------------------------------
# Sample types: every category emits one of these.
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class StorageSample:
    """Per-category bytes used. Emitted as `{prefix}_node_storage_bytes`."""
    category: str
    mountpoint: str
    bytes: int


@dataclass(frozen=True, slots=True)
class FilesystemSample:
    """Per-mountpoint filesystem totals. Emitted as
    `{prefix}_node_filesystem_size_bytes` + `_used_bytes`."""
    mountpoint: str
    size: int
    used: int


@dataclass(frozen=True, slots=True)
class GaugeSample:
    """Generic single-value gauge. Emitted as `{prefix}_node_{name}{labels}`.

    Used by the Filesystem category for `imagefs_capacity_bytes`.
    Prefer StorageSample in plugin code.
    """
    name: str
    value: int
    labels: dict[str, str] = field(default_factory=dict)


Sample = StorageSample | FilesystemSample | GaugeSample


# ---------------------------------------------------------------------------
# Per-cycle collection context. Categories that share work (such as
# all the kubelet-stats categories wanting the same HTTP fetch)
# coordinate through this object.
# ---------------------------------------------------------------------------

class CollectContext:
    """Built once per collection cycle; passed to every collect() call."""

    def __init__(self, node_name: str, du_timeout_seconds: int = 30) -> None:
        self.node_name = node_name
        self.du_timeout_seconds = du_timeout_seconds
        self._kubelet_stats: dict[str, Any] | None = None

    @property
    def kubelet_stats(self) -> dict[str, Any]:
        if self._kubelet_stats is None:
            self._kubelet_stats = utils.fetch_kubelet_stats(self.node_name)
        return self._kubelet_stats


# ---------------------------------------------------------------------------
# BaseCategory: ABC + class registry.
# ---------------------------------------------------------------------------

class BaseCategory(ABC):
    """Abstract base for every category collector.

    Subclass and implement `collect()`. Subclasses are auto-registered
    under their class name (with trailing `Category` stripped) so they
    can be referenced from YAML config by name.
    """

    # Mark a subclass abstract to skip registration (useful for
    # intermediate base classes like DuPathCategory itself).
    _abstract: ClassVar[bool] = True

    _registry: ClassVar[dict[str, type[BaseCategory]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # `_abstract` doesn't inherit; every subclass opts in
        # explicitly. Intermediate bases set it; leaf classes don't.
        if cls.__dict__.get("_abstract", False):
            return
        name = cls.__name__
        short = name[:-len("Category")] if name.endswith("Category") else name
        BaseCategory._registry[short] = cls
        # Also allow the full class name (with "Category" suffix) for
        # users who want to be unambiguous.
        BaseCategory._registry[name] = cls

    @classmethod
    def resolve(cls, type_name: str) -> type[BaseCategory]:
        try:
            return cls._registry[type_name]
        except KeyError as e:
            available = sorted({k for k in cls._registry if not k.endswith("Category")})
            raise KeyError(
                f"No category registered as {type_name!r}. "
                f"Available: {', '.join(available)}"
            ) from e

    @classmethod
    def registered_names(cls) -> list[str]:
        """Short names of every registered concrete category."""
        return sorted({k for k in cls._registry if not k.endswith("Category")})

    @abstractmethod
    def collect(self, ctx: CollectContext) -> Iterable[Sample]:
        """Yield zero or more Samples for this collection cycle.

        Implementations should handle their own errors and yield
        nothing on failure (so other categories aren't disturbed).
        """


# ---------------------------------------------------------------------------
# Common-shape base classes. Most plugins want one of these.
# ---------------------------------------------------------------------------

class DuPathCategory(BaseCategory):
    """Walks a single fixed host path with `du`.

    Subclass and set `name` (the category label, e.g. `apt-cache`) and
    `path` (the absolute host path to walk, e.g. `/var/cache/apt`).

    The path is interpreted as a host path; `du` runs against
    `/host/<path>` inside the container. A path that doesn't exist on
    a given node yields no sample, so the same config works
    cluster-wide.
    """

    _abstract = True
    # Class-level defaults; subclasses override at class scope, or
    # inline-instances supply them via constructor kwargs. Declared as
    # plain (non-ClassVar) attributes so per-instance assignment works.
    name = ""
    path = ""

    def __init__(self, name: str | None = None, path: str | None = None) -> None:
        cls = type(self)
        self.name = name if name is not None else cls.name
        self.path = path if path is not None else cls.path
        if not self.name or not self.path:
            raise ValueError(f"{type(self).__name__} requires both `name` and `path`")

    def collect(self, ctx: CollectContext) -> Iterable[Sample]:
        if not utils.host_is_path(self.path):
            return
        sz = utils.du_bytes(self.path, ctx.du_timeout_seconds)
        if sz is None:
            return
        yield StorageSample(self.name, utils.host_mountpoint(self.path), sz)


class DuPath(DuPathCategory):
    """Inline DuPath instances created entirely from config (no subclass)."""
    pass


class EnumRule:
    """One PVC classification rule. See EnumDirPathCategory."""

    def __init__(self, match: dict[str, str], category: str) -> None:
        self.match = match
        self.category = category

    def matches(self, groups: dict[str, str]) -> bool:
        for key, val in self.match.items():
            if key.endswith("_prefix"):
                base = key[: -len("_prefix")]
                if not groups.get(base, "").startswith(val):
                    return False
            elif key.endswith("_contains"):
                base = key[: -len("_contains")]
                if val not in groups.get(base, ""):
                    return False
            elif key.endswith("_regex"):
                base = key[: -len("_regex")]
                if re.search(val, groups.get(base, "")) is None:
                    return False
            else:
                if groups.get(key) != val:
                    return False
        return True


class EnumDirPathCategory(BaseCategory):
    """Walks each subdir of `root` with `du`, classifying by name.

    `parse_regex` extracts named groups from each directory name; each
    `rules[i]` is checked in order against the groups and the first
    match wins. If no rule matches, `default_category` is used.

    Designed for the local-path-provisioner layout (subdir per PVC,
    naming pattern `pvc-<uuid>_<namespace>_<claim>/...`), but works
    for any "directory of directories" such as SeaweedFS volume data.
    """

    _abstract = True
    root = ""
    parse_regex = r"(?P<claim>.+)"
    default_category = ""

    def __init__(
        self,
        root: str | None = None,
        parse_regex: str | None = None,
        default_category: str | None = None,
        rules: list[dict[str, Any]] | None = None,
    ) -> None:
        cls = type(self)
        self.root = root if root is not None else cls.root
        self.parse_regex = parse_regex if parse_regex is not None else cls.parse_regex
        self.default_category = (
            default_category if default_category is not None else cls.default_category
        )
        if not self.root or not self.default_category:
            raise ValueError(
                f"{type(self).__name__} requires `root` and `default_category`"
            )
        self._regex = re.compile(self.parse_regex)
        self._rules = [
            EnumRule(match=dict(r.get("if", {})), category=r["category"])
            for r in (rules or [])
        ]

    def classify(self, dir_name: str) -> str:
        m = self._regex.match(dir_name)
        groups = m.groupdict() if m else {}
        for rule in self._rules:
            if rule.matches(groups):
                return rule.category
        return self.default_category

    def collect(self, ctx: CollectContext) -> Iterable[Sample]:
        for entry in utils.list_host_dir(self.root):
            full = f"{self.root.rstrip('/')}/{entry}"
            if not utils.host_is_dir(full):
                continue
            sz = utils.du_bytes(full, ctx.du_timeout_seconds)
            if sz is None:
                continue
            yield StorageSample(self.classify(entry), utils.host_mountpoint(full), sz)


class EnumDirPath(EnumDirPathCategory):
    """Inline EnumDirPath created entirely from config (no subclass)."""
    pass


class KubeletStatCategory(BaseCategory):
    """One number pulled from kubelet /stats/summary.

    Subclass and set `name` (category label), `mountpoint_label` (since
    kubelet doesn't tell us the actual mountpoint), and override
    `extract()` to pull the number from the JSON response. The kubelet
    HTTP call is shared via `ctx.kubelet_stats` so multiple
    KubeletStatCategory subclasses cost one round-trip per cycle.
    """

    _abstract = True
    name = ""
    mountpoint_label = ""

    @abstractmethod
    def extract(self, stats: dict[str, Any]) -> int | None:
        """Return the value to emit, or None to skip this cycle."""

    def collect(self, ctx: CollectContext) -> Iterable[Sample]:
        if not self.name or not self.mountpoint_label:
            raise ValueError(f"{type(self).__name__} requires name + mountpoint_label")
        stats = ctx.kubelet_stats
        if not stats:
            return
        value = self.extract(stats)
        if value is None:
            return
        yield StorageSample(self.name, self.mountpoint_label, value)
