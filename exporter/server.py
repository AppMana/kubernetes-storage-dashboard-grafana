"""Threading HTTP /metrics server + background collection loop."""
from __future__ import annotations

import http.server
import threading
import time
from typing import Any

from exporter.categories.base import (
    BaseCategory,
    CollectContext,
    FilesystemSample,
    GaugeSample,
    StorageSample,
)
from exporter.config import Config


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.storage: list[StorageSample] = []
        self.fs: list[FilesystemSample] = []
        self.gauges: list[GaugeSample] = []


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _build_handler(state: _State, cfg: Config, node: str) -> type[http.server.BaseHTTPRequestHandler]:
    prefix = cfg.metric_prefix
    storage_metric = f"{prefix}_node_storage_bytes"
    fs_size_metric = f"{prefix}_node_filesystem_size_bytes"
    fs_used_metric = f"{prefix}_node_filesystem_used_bytes"
    gauge_prefix = f"{prefix}_node_"

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_: Any, **__: Any) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
            if self.path != "/metrics":
                self.send_response(404)
                self.end_headers()
                return
            with state.lock:
                storage_snap = list(state.storage)
                fs_snap = list(state.fs)
                gauges_snap = list(state.gauges)
            try:
                self.send_response(200)
                self.send_header(
                    "Content-Type", "text/plain; version=0.0.4; charset=utf-8"
                )
                self.end_headers()
                lines: list[str] = []

                lines.append(f"# HELP {storage_metric} Per-category bytes used on each node.\n")
                lines.append(f"# TYPE {storage_metric} gauge\n")
                for s in storage_snap:
                    lines.append(
                        f'{storage_metric}{{node="{_esc(node)}",mountpoint="{_esc(s.mountpoint)}",category="{_esc(s.category)}"}} {s.bytes}\n'
                    )

                lines.append(f"# HELP {fs_size_metric} Filesystem capacity in bytes.\n")
                lines.append(f"# TYPE {fs_size_metric} gauge\n")
                lines.append(f"# HELP {fs_used_metric} Filesystem bytes in use.\n")
                lines.append(f"# TYPE {fs_used_metric} gauge\n")
                for f in fs_snap:
                    lines.append(
                        f'{fs_size_metric}{{node="{_esc(node)}",mountpoint="{_esc(f.mountpoint)}"}} {f.size}\n'
                    )
                    lines.append(
                        f'{fs_used_metric}{{node="{_esc(node)}",mountpoint="{_esc(f.mountpoint)}"}} {f.used}\n'
                    )

                # Group gauges by metric name so HELP/TYPE appears once.
                by_name: dict[str, list[GaugeSample]] = {}
                for g in gauges_snap:
                    by_name.setdefault(g.name, []).append(g)
                for name, samples in by_name.items():
                    metric_name = gauge_prefix + name
                    lines.append(f"# TYPE {metric_name} gauge\n")
                    for g in samples:
                        labels = {"node": node, **g.labels}
                        lstr = ",".join(f'{k}="{_esc(v)}"' for k, v in labels.items())
                        lines.append(f"{metric_name}{{{lstr}}} {g.value}\n")

                self.wfile.write("".join(lines).encode())
            except (BrokenPipeError, ConnectionResetError):
                pass

    return Handler


def _collect_one(cat: BaseCategory, ctx: CollectContext) -> list[StorageSample | FilesystemSample | GaugeSample]:
    try:
        return list(cat.collect(ctx))
    except Exception as e:
        print(f"category {type(cat).__name__} failed: {e}", flush=True)
        return []


def _updater(state: _State, cfg: Config, node: str) -> None:
    interval = cfg.interval_seconds
    time.sleep(2)
    while True:
        t0 = time.time()
        ctx = CollectContext(node_name=node, du_timeout_seconds=cfg.du_timeout_seconds)
        storage: list[StorageSample] = []
        fs: list[FilesystemSample] = []
        gauges: list[GaugeSample] = []
        per_cat_counts: dict[str, int] = {}
        for cat in cfg.categories:
            samples = _collect_one(cat, ctx)
            per_cat_counts[type(cat).__name__] = len(samples)
            for s in samples:
                if isinstance(s, StorageSample):
                    storage.append(s)
                elif isinstance(s, FilesystemSample):
                    fs.append(s)
                elif isinstance(s, GaugeSample):
                    gauges.append(s)
        with state.lock:
            state.storage[:] = storage
            state.fs[:] = fs
            state.gauges[:] = gauges
        elapsed = time.time() - t0
        summary = " ".join(f"{k}={v}" for k, v in per_cat_counts.items())
        print(f"collected {summary} in {elapsed:.1f}s", flush=True)
        time.sleep(max(interval - int(elapsed), 30))


def serve(cfg: Config, node: str) -> None:
    state = _State()
    threading.Thread(target=_updater, args=(state, cfg, node), daemon=True).start()
    handler = _build_handler(state, cfg, node)
    port = cfg.listen_port
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", port), handler)
    print(
        f"listening on :{port} (node={node}, interval={cfg.interval_seconds}s, "
        f"prefix={cfg.metric_prefix}, categories={len(cfg.categories)})",
        flush=True,
    )
    srv.serve_forever()
