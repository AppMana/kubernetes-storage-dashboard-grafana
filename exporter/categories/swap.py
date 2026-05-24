from collections.abc import Iterable

from exporter import utils
from exporter.categories.base import BaseCategory, CollectContext, Sample, StorageSample


class SwapCategory(BaseCategory):
    """Authoritative swap usage from /proc/swaps.

    Each line of /proc/swaps is a single swap area (file or partition)
    with size in 1 KiB units. File-backed swap is attributed to the
    filesystem the file lives on; partition-backed swap is attributed
    to "/" (lacks a natural mountpoint, would otherwise fall outside
    any disk's stacked bar).
    """

    def __init__(self, name: str | None = None) -> None:
        self.name = name or "swap"

    def collect(self, ctx: CollectContext) -> Iterable[Sample]:
        # Try the bind-mounted host /proc first so test fixtures (which
        # monkey-patch utils.HOST) take precedence; fall back to direct
        # /proc/swaps (which on a hostPID:true pod is already the host's).
        lines = utils.read_host_lines(utils.host_path("/proc/swaps"), "/proc/swaps")
        if not lines:
            return
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 3:
                continue
            sw_path, sw_type, size_kib = parts[0], parts[1], parts[2]
            try:
                sz = int(size_kib) * 1024
            except ValueError:
                continue
            mp = utils.host_mountpoint(sw_path) if sw_type == "file" else "/"
            yield StorageSample(self.name, mp, sz)
