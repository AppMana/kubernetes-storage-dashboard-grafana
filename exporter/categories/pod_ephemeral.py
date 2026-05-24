from typing import Any

from exporter.categories.base import KubeletStatCategory


class PodEphemeralCategory(KubeletStatCategory):
    """Total pod ephemeral-storage usage (writable layer + emptyDir + logs).

    Sum of `pods[*].ephemeral-storage.usedBytes` from kubelet's
    `/stats/summary`. Ephemeral spans multiple mountpoints across pods,
    so the metric carries the synthetic mountpoint label `ephemeral`.
    """
    name = "pod-ephemeral"
    mountpoint_label = "ephemeral"

    def extract(self, stats: dict[str, Any]) -> int | None:
        total = 0
        any_seen = False
        for pod in stats.get("pods", []) or []:
            es = pod.get("ephemeral-storage", {})
            if "usedBytes" in es:
                total += int(es["usedBytes"])
                any_seen = True
        return total if any_seen else None
