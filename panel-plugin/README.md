# appmana-storage-breakdown-panel

A native Grafana panel that renders the iPhone-Settings-style stacked
horizontal storage bar produced by the
[kubernetes-storage-dashboard-grafana](https://github.com/AppMana/kubernetes-storage-dashboard-grafana)
exporter. One row per (node, mountpoint); one color-coded segment per
storage category (containerd images, longhorn, buildkit, pod
ephemeral, journald, etc.); free and "other" residuals computed at
render time.

The panel takes four query inputs by `refId`:

| refId | PromQL |
|---|---|
| `size` | `nsd_node_filesystem_size_bytes` |
| `used` | `nsd_node_filesystem_used_bytes` |
| `categories` | `nsd_node_storage_bytes` |
| `longhorn` (optional) | `sum by (node, disk_path) (longhorn_replica_info * on(volume) group_left() longhorn_volume_actual_size_bytes)` |

`nsd_` is the default metric prefix. Override it via the panel's
`metricPrefix` option to match a custom exporter prefix.

## Install

This plugin is distributed as a release asset on the parent repo.
For kube-prometheus-stack, add the following to your values:

```yaml
grafana:
  plugins:
    - "appmana-storage-breakdown-panel@0.1.0@https://github.com/AppMana/kubernetes-storage-dashboard-grafana/releases/download/v0.1.0/appmana-storage-breakdown-panel-0.1.0.zip"
  grafana.ini:
    plugins:
      allow_loading_unsigned_plugins: appmana-storage-breakdown-panel
```

On the next Grafana pod roll the plugin is fetched and installed; the
panel appears as **Storage Breakdown** in the panel-type dropdown.

The `allow_loading_unsigned_plugins` line is required because the
plugin is shipped unsigned. Signed releases are tracked in the parent
repo issues.

## Develop

```bash
yarn install
yarn dev      # webpack watch
yarn test     # jest
yarn build    # production bundle in dist/
```
