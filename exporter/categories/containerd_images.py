from typing import Any

from exporter.categories.base import KubeletStatCategory


class ContainerdImagesCategory(KubeletStatCategory):
    """Image + layer cache usage from kubelet's CRI accounting.

    Pulled from `/stats/summary` field `node.runtime.imageFs.usedBytes`.
    Sub-second per node, no fs walk required. Avoids the 5-30 minute
    cost of `du /var/lib/k0s/containerd` on busy nodes.

    Kubelet doesn't report where imageFs is actually mounted, so the
    metric carries the synthetic mountpoint label `imageFs`. The
    dashboard renderer maps this back to `/` (or the first available
    mountpoint) at draw time.
    """
    name = "containerd-images"
    mountpoint_label = "imageFs"

    def extract(self, stats: dict[str, Any]) -> int | None:
        imagefs = stats.get("node", {}).get("runtime", {}).get("imageFs", {})
        if "usedBytes" not in imagefs:
            return None
        return int(imagefs["usedBytes"])
