"""Functional helpers shared by every category.

A plugin author should be able to write a new category that imports only
two things: a base class from `exporter.categories.base`, and one or
more helpers from `exporter.utils`. Everything else (registration,
HTTP, threading, prometheus formatting) lives in the framework.
"""
from __future__ import annotations

import json
import os
import ssl
import subprocess
import urllib.request
from collections.abc import Iterator
from typing import Any

# Container-side path that the host root is bind-mounted at. Every
# helper that walks host paths prepends this; in tests you can monkey-
# patch this module attribute to point at a tmpdir fixture.
HOST = "/host"

SA_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
SA_CA_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"


def host_path(path: str) -> str:
    """Resolve `/foo` (a path on the host) to `/host/foo` (where it's
    accessible inside the exporter container)."""
    if path.startswith(HOST):
        return path
    if not path.startswith("/"):
        raise ValueError(f"host_path expects an absolute path, got {path!r}")
    return HOST + path


def du_bytes(path: str, timeout_seconds: int = 30) -> int | None:
    """Run `du -sx --block-size=1` under nice+ionice on the host-mounted path.

    `path` should be an absolute path on the host filesystem; this
    function will translate it to `/host/<path>` internally so plugin
    authors never have to think about the bind mount.

    Returns allocated bytes on disk (matches `df` on btrfs+zstd and on
    sparse files like Longhorn replicas). Returns None on timeout or
    error, in which case the caller skips emitting a sample.

    `nice -n 19 ionice -c 3` keeps the periodic walk out of the way of
    real workloads. Without it the burst trips CPUThrottlingHigh in
    the cgroup.
    """
    target = host_path(path)
    try:
        out = subprocess.run(
            ["nice", "-n", "19", "ionice", "-c", "3",
             "du", "-sx", "--block-size=1", target],
            capture_output=True, timeout=timeout_seconds, check=False,
        )
        if not out.stdout:
            return None
        return int(out.stdout.split()[0])
    except (subprocess.TimeoutExpired, OSError, ValueError) as e:
        print(f"du failed on {path}: {e}", flush=True)
        return None


def host_mountpoint(path: str) -> str:
    """Find the host mountpoint that `path` lives on.

    Walks up the inode tree from `path` to the filesystem boundary
    (where st_dev changes), then strips the /host prefix to give the
    canonical mountpoint as the node sees it.
    """
    target = host_path(path)
    try:
        d = os.stat(target).st_dev
    except OSError:
        return "/"
    cur = target
    while True:
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        try:
            if os.stat(parent).st_dev != d:
                break
        except OSError:
            break
        cur = parent
    rel = cur[len(HOST):] if cur.startswith(HOST) else cur
    return rel or "/"


def list_host_dir(path: str) -> list[str]:
    """`os.listdir` on a host path, sorted, returning empty list on error."""
    target = host_path(path)
    if not os.path.isdir(target):
        return []
    try:
        return sorted(os.listdir(target))
    except OSError as e:
        print(f"list failed on {path}: {e}", flush=True)
        return []


def host_is_dir(path: str) -> bool:
    return os.path.isdir(host_path(path))


def host_is_path(path: str) -> bool:
    return os.path.exists(host_path(path))


def statvfs(path: str) -> tuple[int, int] | None:
    """Return (size_bytes, used_bytes) for the host path, or None.

    Uses f_bavail (not f_bfree) so reserved-for-root blocks are
    excluded. Matches how node_exporter reports usage.
    """
    target = host_path(path) if path != "/" else (HOST or "/")
    try:
        st = os.statvfs(target)
    except OSError:
        return None
    size = st.f_blocks * st.f_frsize
    avail = st.f_bavail * st.f_frsize
    used = size - avail
    if size == 0:
        return None
    return size, used


def read_host_lines(*paths: str) -> list[str]:
    """Read the first path of `paths` that exists, return its lines."""
    for p in paths:
        try:
            with open(p) as f:
                return f.readlines()
        except OSError:
            continue
    return []


def fetch_kubelet_stats(node_name: str) -> dict[str, Any]:
    """One-shot fetch of kubelet's /stats/summary via apiserver proxy.

    Reads the in-pod ServiceAccount token + CA. Returns {} on any
    failure (missing token, network error, non-JSON response).
    """
    try:
        with open(SA_TOKEN_PATH) as f:
            token = f.read().strip()
    except OSError:
        return {}
    api_host = os.environ.get("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc")
    api_port = os.environ.get("KUBERNETES_SERVICE_PORT", "443")
    url = f"https://{api_host}:{api_port}/api/v1/nodes/{node_name}/proxy/stats/summary"
    ctx = ssl.create_default_context(cafile=SA_CA_PATH)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data: dict[str, Any] = json.loads(resp.read())
    except Exception as e:
        print(f"kubelet /stats/summary failed: {e}", flush=True)
        return {}
    return data


def iter_mounts() -> Iterator[tuple[str, str, str]]:
    """Yield (device, mountpoint, fstype) for every host mount, once.

    Reads /proc/1/mounts (with hostPID=true the container sees the
    host's PID 1, hence the host's mount table). Falls back to
    /host/proc/mounts.
    """
    lines = read_host_lines("/proc/1/mounts", "/host/proc/mounts")
    for line in lines:
        parts = line.split()
        if len(parts) >= 3:
            yield parts[0], parts[1], parts[2]
