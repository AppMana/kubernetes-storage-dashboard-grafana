from collections.abc import Iterable

from exporter import utils
from exporter.categories.base import (
    BaseCategory,
    CollectContext,
    FilesystemSample,
    GaugeSample,
    Sample,
)


class FilesystemCategory(BaseCategory):
    """Per-mountpoint filesystem size + used totals via statvfs().

    This is the one built-in category that emits FilesystemSamples
    instead of StorageSamples. The dashboard uses them as the
    denominator for the per-disk stacked bars; every other category
    contributes a numerator segment.

    Filters to real block devices on supported filesystems; skips boot
    partitions, kubelet/containerd staging directories, and Longhorn
    iSCSI/engine mountpoints. The whole filter set is configurable.

    Also pulls `imagefs_capacity_bytes` from kubelet stats when
    available. Useful for noticing when imageFs lives on its own disk.
    """

    DEFAULT_INTERESTING_FS = ("ext4", "btrfs", "xfs")
    DEFAULT_REAL_DEV_PREFIXES = ("/dev/nvme", "/dev/sd", "/dev/mapper/", "/dev/md")
    DEFAULT_SKIP_DEV_PREFIXES = ("/dev/longhorn/",)
    DEFAULT_SKIP_MOUNTPOINT_PREFIXES = (
        "/boot",
        "/run/",
        "/var/lib/longhorn-iscsi/",
        "/var/lib/longhorn-engine/",
    )

    def __init__(
        self,
        interesting_fs: list[str] | None = None,
        real_dev_prefixes: list[str] | None = None,
        skip_dev_prefixes: list[str] | None = None,
        skip_mountpoint_prefixes: list[str] | None = None,
        imagefs_capacity_metric: bool = True,
    ) -> None:
        self.interesting_fs = tuple(interesting_fs or self.DEFAULT_INTERESTING_FS)
        self.real_dev_prefixes = tuple(real_dev_prefixes or self.DEFAULT_REAL_DEV_PREFIXES)
        self.skip_dev_prefixes = tuple(skip_dev_prefixes or self.DEFAULT_SKIP_DEV_PREFIXES)
        self.skip_mountpoint_prefixes = tuple(
            skip_mountpoint_prefixes or self.DEFAULT_SKIP_MOUNTPOINT_PREFIXES
        )
        self.imagefs_capacity_metric = imagefs_capacity_metric

    def _canonical_mounts(self) -> dict[str, str]:
        # Multiple mountpoints can share a device (e.g. btrfs subvols);
        # pick the shortest mountpoint per device as canonical.
        canonical: dict[str, str] = {}
        for dev, mp, fstype in utils.iter_mounts():
            if self.interesting_fs and fstype not in self.interesting_fs:
                continue
            if any(dev.startswith(p) for p in self.skip_dev_prefixes):
                continue
            if self.real_dev_prefixes and not any(dev.startswith(p) for p in self.real_dev_prefixes):
                continue
            if any(mp.startswith(p) for p in self.skip_mountpoint_prefixes):
                continue
            existing = canonical.get(dev)
            if existing is None or len(mp) < len(existing):
                canonical[dev] = mp
        return canonical

    def collect(self, ctx: CollectContext) -> Iterable[Sample]:
        for mp in self._canonical_mounts().values():
            result = utils.statvfs(mp)
            if result is None:
                continue
            size, used = result
            yield FilesystemSample(mp, size, used)

        if self.imagefs_capacity_metric:
            imagefs = ctx.kubelet_stats.get("node", {}).get("runtime", {}).get("imageFs", {})
            if "capacityBytes" in imagefs:
                yield GaugeSample(
                    name="imagefs_capacity_bytes",
                    value=int(imagefs["capacityBytes"]),
                )
