from __future__ import annotations

from pathlib import Path

from exporter import config, server
from exporter.categories.base import (
    BaseCategory,
    CollectContext,
    DuPathCategory,
    FilesystemSample,
    GaugeSample,
    StorageSample,
)


def test_metrics_output_uses_configured_prefix(tmp_path: Path) -> None:
    p = tmp_path / "user.yaml"
    p.write_text("metric_prefix: myprefix\ncategories: []\n")
    cfg = config.load(str(p))

    state = server._State()
    state.storage = [
        StorageSample("home", "/", 1024),
        StorageSample("containerd-images", "imageFs", 200),
    ]
    state.fs = [FilesystemSample("/", 100, 50)]
    state.gauges = [GaugeSample("imagefs_capacity_bytes", 1000)]

    Handler = server._build_handler(state, cfg, node="test-node")

    written: list[bytes] = []
    class FakeWFile:
        def write(self, b: bytes) -> None:
            written.append(b)

    class FakeHandler(Handler):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            self.path = "/metrics"
            self.wfile = FakeWFile()
            self.status: int | None = None
            self.headers_sent: list[tuple[str, str]] = []
        def send_response(self, code: int) -> None: self.status = code
        def send_header(self, k: str, v: str) -> None: self.headers_sent.append((k, v))
        def end_headers(self) -> None: pass

    h = FakeHandler()
    h.do_GET()
    body = b"".join(written).decode()
    assert h.status == 200
    assert 'myprefix_node_storage_bytes{node="test-node",mountpoint="/",category="home"} 1024' in body
    assert 'myprefix_node_storage_bytes{node="test-node",mountpoint="imageFs",category="containerd-images"} 200' in body
    assert 'myprefix_node_filesystem_size_bytes{node="test-node",mountpoint="/"} 100' in body
    assert 'myprefix_node_filesystem_used_bytes{node="test-node",mountpoint="/"} 50' in body
    assert 'myprefix_node_imagefs_capacity_bytes{node="test-node"} 1000' in body


def test_404_for_other_paths(tmp_path: Path) -> None:
    p = tmp_path / "user.yaml"
    p.write_text("categories: []\n")
    cfg = config.load(str(p))
    state = server._State()
    Handler = server._build_handler(state, cfg, node="x")

    class FakeHandler(Handler):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            self.path = "/healthz"
            self.status: int | None = None
        def send_response(self, code: int) -> None: self.status = code
        def end_headers(self) -> None: pass

    h = FakeHandler()
    h.do_GET()
    assert h.status == 404


def test_failing_category_does_not_break_others() -> None:
    class GoodACategory(DuPathCategory):
        name = "good-a"
        path = "/tmp/never-walked"
        def collect(self, ctx: CollectContext):
            yield StorageSample("good-a", "/", 1)

    class BrokenCategory(DuPathCategory):
        name = "broken"
        path = "/tmp/x"
        def collect(self, ctx: CollectContext):
            raise RuntimeError("boom")

    class GoodBCategory(DuPathCategory):
        name = "good-b"
        path = "/tmp/x"
        def collect(self, ctx: CollectContext):
            yield StorageSample("good-b", "/", 2)

    try:
        ctx = CollectContext(node_name="t")
        # Server collects via _collect_one which catches exceptions.
        assert server._collect_one(GoodACategory(), ctx) == [StorageSample("good-a", "/", 1)]
        assert server._collect_one(BrokenCategory(), ctx) == []
        assert server._collect_one(GoodBCategory(), ctx) == [StorageSample("good-b", "/", 2)]
    finally:
        for n in ("GoodA", "GoodACategory", "Broken", "BrokenCategory", "GoodB", "GoodBCategory"):
            BaseCategory._registry.pop(n, None)
