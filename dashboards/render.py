#!/usr/bin/env python3
"""Render the dashboard template into a concrete dashboard JSON.

The template has three placeholders:

    __METRIC_PREFIX__        Prefix used on exporter metric names
                             (e.g. "nsd_node_storage_bytes").

    __DATASOURCE_UID__       Grafana datasource UID for Prometheus.
                             Defaults to "prometheus" in most
                             kube-prometheus installs.

    __CATEGORIES_OBJ_JSON__  JSON array of {id, color, label} objects,
                             substituted verbatim into the panel's
                             options.categories. Loaded from the
                             --categories file, which is a JSON array
                             of [id, color, label] tuples.

Usage:
    python dashboards/render.py \\
        --template dashboards/storage-usage.tmpl.json \\
        --categories dashboards/default-categories.json \\
        --prefix nsd \\
        --datasource-uid prometheus \\
        --out dashboards/storage-usage.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def render(template: str, prefix: str, datasource_uid: str, categories_obj: str) -> str:
    return (
        template
        .replace("__METRIC_PREFIX__", prefix)
        .replace("__DATASOURCE_UID__", datasource_uid)
        .replace("__CATEGORIES_OBJ_JSON__", categories_obj)
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--template", type=Path, required=True)
    p.add_argument("--categories", type=Path, required=True,
                   help="JSON file with array of [id, color, label] tuples")
    p.add_argument("--prefix", default="nsd")
    p.add_argument("--datasource-uid", default="prometheus")
    p.add_argument("--out", type=Path)
    args = p.parse_args(argv)

    template = args.template.read_text()
    tuples = json.loads(args.categories.read_text())
    cats = [{"id": id_, "color": color, "label": label} for id_, color, label in tuples]
    cats_inline = json.dumps(cats, separators=(",", ":"))

    rendered = render(template, args.prefix, args.datasource_uid, cats_inline)
    json.loads(rendered)  # validates the result parses as JSON

    if args.out:
        args.out.write_text(rendered)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
