# kubernetes-storage-dashboard-grafana

A per-node storage breakdown for Kubernetes. Shows, for every node
and every real disk, what is using the bytes.

![Storage Usage panel](docs/images/dashboard-detail.png)

The dashboard answers a question that kubelet's `nodefs` and
node_exporter's `filesystem_used_bytes` do not: not how much is used,
but what is using it. Containerd images. Longhorn replicas. Per-pod
ephemeral writes. A stale buildkit cache.

## The three pieces

This repo ships three independent components. Each one is useful on
its own, and the install path for each is different.

1. A Prometheus exporter (the "storage exporter"), packaged as a
   container image and shipped as a DaemonSet via the Helm chart.
   Its only job is to publish detailed per-node, per-category storage
   metrics on `/metrics`. It does not render anything. You can
   consume the metrics from any Grafana dashboard, alerting rule, or
   `promtool query` invocation.

2. A Grafana panel plugin
   (`appmana-storage-breakdown-panel`), written in TypeScript +
   React, distributed as a `.zip` release asset. Installed into your
   Grafana by adding one entry to `grafana.plugins:` in your
   kube-prometheus-stack values. The plugin is a new panel type that
   knows how to draw the iPhone-Settings-style stacked storage bars
   from data with this exporter's schema.

3. A dashboard JSON (`Storage Usage`, uid `storage-usage`) that wires
   the plugin to the exporter's metrics with four PromQL targets.
   Shipped by the Helm chart as a `grafana_dashboard` labelled
   ConfigMap, which kube-prometheus-stack's Grafana sidecar
   auto-imports.

A typical install brings all three. A user who only wants the
metrics (to build their own dashboard, or to alert) installs only
the exporter. A user who has the metrics in some other way (their
own collector, a different exporter) installs only the plugin.

## What the exporter measures

Standard node-level storage metrics tell you a disk is 78% full. They
do not tell you whether 60% of that is your container image cache
(safe to `crictl rmi --prune`), or persistent local-path PVCs from a
deleted namespace (need manual cleanup), or pod ephemeral writes from
a runaway log (need an app fix).

This exporter classifies on-disk bytes into categories such as
`containerd-images`, `local-path-pvc`, `pod-ephemeral`, `longhorn`,
`journald`, `buildkit`, `home`, and `swap`. It uses the fastest
authoritative source for each category, then publishes three
gauges:

```
nsd_node_storage_bytes{node, mountpoint, category} <bytes>
nsd_node_filesystem_size_bytes{node, mountpoint} <bytes>
nsd_node_filesystem_used_bytes{node, mountpoint} <bytes>
```

The prefix `nsd_` is configurable (`exporter.metricPrefix` Helm value).

## How it measures

The exporter is hybrid by design. It does not run `du` on the large
trees, because a naive `du /var/lib/k0s/containerd` takes 5 to 30
minutes on a busy node and burns IO doing it. Each category uses the
fastest authoritative source available.

| Category | Source | Cost |
|---|---|---|
| `containerd-images` | kubelet `/stats/summary`, field `imageFs.usedBytes` | under 1 second |
| `pod-ephemeral` | kubelet `/stats/summary`, sum of `pods[*].ephemeral-storage.usedBytes` | under 1 second |
| `longhorn` | Longhorn's own `/metrics`, joined dashboard-side as `longhorn_replica_info * longhorn_volume_actual_size_bytes` | under 1 second |
| `swap` | `/proc/swaps` | instant |
| filesystem size and used | `statvfs()` on real block-device mountpoints (ext4, btrfs, xfs) | instant |
| Everything else (`apt-cache`, `journald`, `home`, and so on) | Bounded `du -sx --block-size=1` under `nice -n 19 ionice -c 3` with a 30 second timeout | under 5 seconds |
| Per-PVC local-path directories | Enum walk under `/opt/local-path-provisioner` (or your configured root), one `du` per PVC | under 5 seconds |

Three details that are not obvious.

### du with --block-size=1, not -b

Allocated bytes on disk, not apparent size. Apparent size
over-reports btrfs+zstd compressed files and Longhorn sparse replicas
by an order of magnitude.

### Avoid longhorn_disk_usage_bytes

That metric is `df`-based and reports the entire underlying
filesystem (OS, containerd, journald, Longhorn). The dashboard joins
Longhorn's per-replica metrics instead, which excludes the
surrounding filesystem.

### Synthetic mountpoint labels

Kubelet does not say where `imageFs` lives on the host, so the metric
carries `mountpoint="imageFs"`. The same applies to
`mountpoint="ephemeral"`. The panel plugin maps both back to `/` (or
the first available mountpoint) at render time, so each segment lands
on the right disk.

## Exporter internals

The exporter is built as a pluggable registry of categories. Each
category is one Python class. Most categories are a one-line subclass
of a base class that already knows how to do `du`, `statvfs`, kubelet
HTTP, or file parsing. To add a new category, drop a single `.py` file
into a ConfigMap. The exporter image does not need a rebuild.

```
exporter/
  categories/
    base.py                   ABC, DuPathCategory, EnumDirPathCategory, KubeletStatCategory
    filesystem.py             statvfs(), emits FilesystemSample (the dashboard's denominator)
    swap.py                   /proc/swaps
    containerd_images.py      kubelet /stats/summary, imageFs.usedBytes
    pod_ephemeral.py          kubelet /stats/summary, sum(pods.ephemeral-storage)
    apt_cache.py              du /var/cache/apt
    journald.py               du /var/log/journal
    home.py, snap.py, ...     one-line DuPathCategory subclasses
    local_path_provisioner.py EnumDirPathCategory for per-PVC dirs
  utils.py                    du_bytes, host_mountpoint, statvfs, fetch_kubelet_stats
  plugin_loader.py            Imports user .py files from plugins_dir
  config.py                   YAML loader, categories[] instantiation
  server.py                   Threading HTTP /metrics + collection loop
  defaults.yaml               Built-in default config
```

The exporter runs as a DaemonSet on every Linux node. It runs as root
with `hostPID: true` and a read-only bind mount of `/` at `/host`. At
startup it imports every `.py` file under
`/etc/storage-exporter/plugins.d/`, instantiates each category listed
in `config.categories[]`, and starts a collection loop. Every
`interval_seconds` it calls `cat.collect(ctx)` for each category and
publishes the result on `/metrics` at port 9101.

## Panel plugin internals

The panel plugin lives in `panel-plugin/`. It is a standard
`@grafana/create-plugin` scaffolded project. The runtime entry is
`src/module.ts`, which registers `StorageBreakdownPanel` as a
`PanelPlugin<PanelOptions>`. The component lives in
`src/components/StorageBreakdownPanel.tsx`, with `DiskRow.tsx` and
`Legend.tsx` handling the per-row markup.

`src/transform.ts` is the only place that knows about the metric
schema. It joins the four query results (`size`, `used`, `categories`,
`longhorn`) by `(node, mountpoint)`, remaps the synthetic
`imageFs`/`ephemeral` mountpoint labels back to a real mountpoint,
computes free and "other" residuals, and returns a `RowModel[]` for
React to render. Unit tests cover all of this.

Grafana renders the panel using the same machinery it uses for Bar
Chart or Time Series. The panel respects Grafana's time picker,
variables, drill-down, share links, and snapshots.

## Install

### Prerequisites

- Kubernetes 1.27 or later
- Prometheus and the ServiceMonitor CRD, for example via
  kube-prometheus-stack
- Grafana 10.4 or later, with the `grafana_dashboard` ConfigMap
  sidecar enabled (the default in kube-prometheus-stack)
- (Optional) [Longhorn](https://longhorn.io), which enables the
  `longhorn` segment

### Install the Grafana panel plugin

The dashboard uses a custom Grafana panel
(`appmana-storage-breakdown-panel`) that needs to be installed in your
Grafana instance. With kube-prometheus-stack, add the following to
your values and `helm upgrade`:

```yaml
grafana:
  plugins:
    - "appmana-storage-breakdown-panel@0.1.0@https://github.com/AppMana/kubernetes-storage-dashboard-grafana/releases/download/v0.1.0/appmana-storage-breakdown-panel-0.1.0.zip"
  grafana.ini:
    plugins:
      allow_loading_unsigned_plugins: appmana-storage-breakdown-panel
```

On the next Grafana pod roll the binary is fetched from the release
asset, extracted into `/var/lib/grafana/plugins/`, and the panel type
appears in Grafana's panel-type dropdown. The
`allow_loading_unsigned_plugins` line is required because v0.1.x
ships unsigned.

### Install the chart (exporter + dashboard ConfigMap)

```bash
helm install kubernetes-storage-dashboard-grafana \
  oci://ghcr.io/appmana/charts/kubernetes-storage-dashboard-grafana \
  --version 0.1.0 \
  --namespace monitoring --create-namespace
```

### Kustomize or raw manifests

```bash
kubectl apply -k https://github.com/appmana/kubernetes-storage-dashboard-grafana//deploy/kustomize?ref=v0.1.0
```

Or download `install.yaml` from the GitHub release page and run
`kubectl apply -f install.yaml`. The panel plugin is still installed
via the kube-prometheus-stack snippet above. The chart ships the
dashboard ConfigMap and the exporter DaemonSet, but does not install
the plugin into a Grafana it does not own.

### Verify

```bash
kubectl -n monitoring rollout status ds/kubernetes-storage-dashboard-grafana
kubectl -n monitoring port-forward ds/kubernetes-storage-dashboard-grafana 9101
curl -s localhost:9101/metrics | head -20
```

You should see lines like the following.

```
nsd_node_storage_bytes{node="...",mountpoint="/",category="home"} 1234567
nsd_node_storage_bytes{node="...",mountpoint="imageFs",category="containerd-images"} 9876543210
nsd_node_filesystem_size_bytes{node="...",mountpoint="/"} 8000000000
```

In Grafana, look for the "Storage Usage" dashboard (uid
`storage-usage`).

## Add a custom category without forking

To track one more thing, write six lines of Helm values. The change
ships as a Helm release. The exporter image is unchanged.

A plugin is a single Python file that subclasses one of three base
classes. Drop the source into `exporter.plugins` in your Helm values
and reference it from `exporter.categories`.

```yaml
# values-overlay.yaml
exporter:
  plugins:
    my_app.py: |
      from exporter.categories.base import DuPathCategory

      class MyAppCacheCategory(DuPathCategory):
          name = "my-app-cache"
          path = "/var/lib/my-app/cache"

  categories:
    # Keep all the defaults
    - { type: Filesystem }
    - { type: ContainerdImages }
    - { type: PodEphemeral }
    - { type: Swap }
    - { type: AptCache }
    - { type: Journald }
    - { type: Home }
    - { type: LocalPathProvisioner }
    # Add the new one
    - { type: MyAppCache }
```

Run `helm upgrade -f values-overlay.yaml`. Wait for the DaemonSet to
roll. The new `my-app-cache` series appears in Prometheus at the next
scrape.

### Which base class to subclass

- `DuPathCategory`: one fixed host path, walked with `du -sx`.
  Required attributes: `name`, `path`.
- `EnumDirPathCategory`: a directory of directories, where each
  subdirectory is its own time-series (for example local-path PVCs,
  SeaweedFS volumes). Classify by name with a regex and a rule list.
  Required attributes: `root`, `default_category`. Optional:
  `parse_regex`, `rules`.
- `KubeletStatCategory`: one number pulled from kubelet's
  `/stats/summary`. Multiple subclasses share one HTTP call per cycle.
  Required attributes: `name`, `mountpoint_label`. Override
  `extract(stats)`.
- `BaseCategory`: anything else. Custom file parsing, multiple
  paths, branching logic. Override `collect(ctx)`. Yield
  `StorageSample(category, mountpoint, bytes)`.

A more complex plugin that uses the full `BaseCategory` surface:

```yaml
exporter:
  plugins:
    multi_tenant_cache.py: |
      from exporter.categories.base import BaseCategory, StorageSample
      from exporter import utils

      class MultiTenantCacheCategory(BaseCategory):
          """Sums per-tenant cache dirs under /var/lib/my-app/tenants/*/cache."""
          name = "tenant-cache"

          def collect(self, ctx):
              for tenant in utils.list_host_dir("/var/lib/my-app/tenants"):
                  cache = f"/var/lib/my-app/tenants/{tenant}/cache"
                  if not utils.host_is_dir(cache):
                      continue
                  sz = utils.du_bytes(cache, ctx.du_timeout_seconds)
                  if sz is None:
                      continue
                  yield StorageSample(
                      category=self.name,
                      mountpoint=utils.host_mountpoint(cache),
                      bytes=sz,
                  )
```

Notes for plugin authors.

The host filesystem is bind-mounted at `/host` inside the pod. You do
not have to think about that prefix. Every helper in `exporter.utils`
(`du_bytes`, `host_mountpoint`, `list_host_dir`, `host_is_dir`,
`statvfs`) takes a host-side path and prepends the `/host` prefix for
you.

A category that yields nothing is fine. Use that to skip nodes where
the path does not exist, so the same plugin file ships cluster-wide.

The framework catches exceptions. A broken category yields no samples
that cycle, and the other categories continue to run.

### Inline categories without a .py file

For one-off `du` paths there is no need to write a plugin file. The
`DuPath` and `EnumDirPath` types accept their config inline.

```yaml
exporter:
  categories:
    - { type: DuPath, name: my-app-cache, path: /var/lib/my-app/cache }
    - type: EnumDirPath
      root: /mnt/seaweed
      parse_regex: '^(?P<volume>.+)$'
      default_category: seaweedfs-volume-data
```

### Disable a built-in

`categories:` is a list replacement, not a merge. To disable a default
category, omit it from your overlay's list. Re-list the categories you
want to keep.

### Reference: AppMana production config

[`examples/appmana.yaml`](examples/appmana.yaml) is the config used in
the production cluster this exporter was extracted from. It classifies
SeaweedFS volumes, vLLM JIT caches, ComfyUI custom-node caches,
HuggingFace model downloads, and a relocated local-path provisioner
store. It matches the dashboard screenshot at the top of this README.

## Packaging

Push a `v*.*.*` git tag to cut a release.
[`.github/workflows/release.yaml`](.github/workflows/release.yaml)
then does the following.

1. Builds and pushes a multi-arch container image (`linux/amd64` and
   `linux/arm64`) to
   `ghcr.io/appmana/kubernetes-storage-dashboard-grafana` with tags
   `:VERSION`, `:MAJOR.MINOR`, and `:latest`. Provenance and SBOM are
   attached.
2. Packages and pushes the Helm chart to
   `oci://ghcr.io/appmana/charts/kubernetes-storage-dashboard-grafana`.
   The chart's `version` and `appVersion` are rewritten to match the
   tag.
3. Renders a flat `install.yaml` from the chart at the released tag
   and attaches it (plus the chart tarball) to the GitHub release.

CI ([`.github/workflows/ci.yaml`](.github/workflows/ci.yaml)) runs on
every PR and push.

- Python: `ruff check`, `mypy --strict`, `pytest --cov`
- YAML: `yamllint` over all config, values, and kustomize
- Dashboard: render the template against both default and AppMana
  category lists, validate as JSON
- Helm: `helm lint`, `helm template`, `kubeconform -strict`
- Drift gate: re-render `install.yaml` and `diff -u` it against
  the committed copy, so a chart edit that the maintainer forgot to
  re-render fails CI instead of shipping a stale install.yaml
- Docker: full `docker buildx` build and `--help` smoke test
- Panel plugin: `yarn typecheck`, `yarn test:ci`, `yarn build`

The committed [`deploy/kustomize/install.yaml`](deploy/kustomize/install.yaml)
is the source of truth for the Kustomize install path. Regenerate it
with the following command.

```bash
helm template kubernetes-storage-dashboard-grafana \
  deploy/helm/kubernetes-storage-dashboard-grafana \
  --namespace monitoring > deploy/kustomize/install.yaml
```

## Security

The DaemonSet runs with the following settings.

- `runAsUser: 0`. Root is required to read `/proc/swaps`,
  `/proc/1/mounts`, and most `/var/lib/*` paths the `du` collector
  walks.
- `hostPID: true`. The pod sees the host's `/proc/1/mounts` instead
  of the container's.
- `hostPath: /` is mounted read-only at `/host` with
  `HostToContainer` propagation.
- `privileged: false`, default capability set, and the pod's own
  network namespace.

RBAC is the minimum needed for kubelet stats.

```yaml
rules:
  - apiGroups: [""]
    resources: ["nodes/proxy", "nodes/stats"]
    verbs: ["get"]
```

### Plugin trust

Plugins are arbitrary Python loaded into a root pod with hostPath
access. Treat the contents of `exporter.plugins` as trusted code.
Anyone who can edit your Helm values can run code on every node. This
is the same trust boundary as your DaemonSet image itself.

## License

Apache-2.0. See [LICENSE](LICENSE).
