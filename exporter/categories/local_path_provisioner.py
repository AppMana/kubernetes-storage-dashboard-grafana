from exporter.categories.base import EnumDirPathCategory


class LocalPathProvisionerCategory(EnumDirPathCategory):
    """Per-PVC usage under the local-path-provisioner root.

    Default root is `/opt/local-path-provisioner` (the upstream
    default); set `root` in config to override (e.g.
    `/mnt/kubernetes` if your local-path-provisioner was relocated).

    Each subdirectory is named `pvc-<uuid>_<namespace>_<claim>/` and
    becomes a separate time-series classified by `rules` against the
    parsed (namespace, claim) groups. Defaults to `local-path-pvc`
    with one built-in rule promoting anything containing "cache" in
    the claim name to `local-path-cache`.
    """
    root = "/opt/local-path-provisioner"
    parse_regex = r"^[^_]+_(?P<namespace>[^_]+)_(?P<claim>.+)$"
    default_category = "local-path-pvc"
