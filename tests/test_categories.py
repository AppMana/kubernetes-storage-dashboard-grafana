from __future__ import annotations

from pathlib import Path

import pytest

from exporter import utils
from exporter.categories.base import (
    BaseCategory,
    CollectContext,
    DuPathCategory,
    EnumDirPath,
    StorageSample,
)


def test_subclass_auto_registers() -> None:
    class FooCategory(DuPathCategory):
        name = "foo"
        path = "/tmp/foo"

    try:
        cls = BaseCategory.resolve("Foo")
        assert cls is FooCategory
        cls2 = BaseCategory.resolve("FooCategory")  # full name also works
        assert cls2 is FooCategory
    finally:
        # Don't leak into other tests.
        BaseCategory._registry.pop("Foo", None)
        BaseCategory._registry.pop("FooCategory", None)


def test_abstract_subclass_not_registered() -> None:
    class IntermediateBaseCategory(DuPathCategory):
        _abstract = True

    names = BaseCategory.registered_names()
    assert "IntermediateBase" not in names


def test_dupath_skips_missing_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(utils, "HOST", "/nonexistent-host-root")

    class MissingCategory(DuPathCategory):
        name = "missing"
        path = "/this/path/will/not/be/found"
    try:
        cat = MissingCategory()
        ctx = CollectContext(node_name="t")
        assert list(cat.collect(ctx)) == []
    finally:
        BaseCategory._registry.pop("Missing", None)
        BaseCategory._registry.pop("MissingCategory", None)


def test_dupath_emits_storage_sample(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Build a fake /host fixture and run du against it.
    host = tmp_path / "host"
    sub = host / "var" / "lib" / "foo"
    sub.mkdir(parents=True)
    (sub / "data").write_bytes(b"x" * 1024)
    monkeypatch.setattr(utils, "HOST", str(host))

    class FooCategory(DuPathCategory):
        name = "foo"
        path = "/var/lib/foo"
    try:
        cat = FooCategory()
        ctx = CollectContext(node_name="t", du_timeout_seconds=5)
        samples = list(cat.collect(ctx))
        assert len(samples) == 1
        s = samples[0]
        assert isinstance(s, StorageSample)
        assert s.category == "foo"
        assert s.bytes > 0
    finally:
        BaseCategory._registry.pop("Foo", None)
        BaseCategory._registry.pop("FooCategory", None)


def test_enum_dir_classification() -> None:
    ed = EnumDirPath(
        root="/var/lib/foo",
        parse_regex=r"^[^_]+_(?P<namespace>[^_]+)_(?P<claim>.+)$",
        default_category="catchall",
        rules=[
            {"if": {"namespace": "special"}, "category": "special-cat"},
            {"if": {"claim_prefix": "cache-"}, "category": "cache-cat"},
            {"if": {"claim_contains": "temp"}, "category": "temp-cat"},
        ],
    )
    assert ed.classify("pvc-abc_special_anything") == "special-cat"
    assert ed.classify("pvc-abc_other_cache-foo") == "cache-cat"
    assert ed.classify("pvc-abc_other_xyz-temp-xyz") == "temp-cat"
    assert ed.classify("pvc-abc_other_normalclaim") == "catchall"
    assert ed.classify("malformed") == "catchall"


def test_kubelet_stat_shared_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    # Verify ContainerdImages + PodEphemeral share one fetch_kubelet_stats call.
    calls = {"count": 0}
    fake_stats = {
        "node": {"runtime": {"imageFs": {"usedBytes": 10, "capacityBytes": 100}}},
        "pods": [{"ephemeral-storage": {"usedBytes": 5}}],
    }

    def fake_fetch(node_name: str) -> dict:
        calls["count"] += 1
        return fake_stats
    monkeypatch.setattr(utils, "fetch_kubelet_stats", fake_fetch)

    from exporter.categories.containerd_images import ContainerdImagesCategory
    from exporter.categories.pod_ephemeral import PodEphemeralCategory
    ctx = CollectContext(node_name="t")
    s1 = list(ContainerdImagesCategory().collect(ctx))
    s2 = list(PodEphemeralCategory().collect(ctx))
    assert calls["count"] == 1, "kubelet stats should be fetched exactly once per cycle"
    assert s1 == [StorageSample("containerd-images", "imageFs", 10)]
    assert s2 == [StorageSample("pod-ephemeral", "ephemeral", 5)]


def test_kubelet_stat_skipped_on_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(utils, "fetch_kubelet_stats", lambda n: {})
    from exporter.categories.containerd_images import ContainerdImagesCategory
    ctx = CollectContext(node_name="t")
    assert list(ContainerdImagesCategory().collect(ctx)) == []


def test_swap_parses_proc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Fake /host/proc/swaps so swap collector reads from our fixture.
    proc = tmp_path / "host" / "proc"
    proc.mkdir(parents=True)
    (proc / "swaps").write_text(
        "Filename                                Type            Size            Used            Priority\n"
        "/swapfile                               file            33554432        0               -2\n"
    )
    monkeypatch.setattr(utils, "HOST", str(tmp_path / "host"))

    from exporter.categories.swap import SwapCategory
    samples = list(SwapCategory().collect(CollectContext(node_name="t")))
    assert len(samples) == 1
    assert samples[0].category == "swap"
    assert samples[0].bytes == 33554432 * 1024
