#!/usr/bin/env python3
"""Render a dashboard template into a concrete dashboard JSON.

The template has four placeholders, two of which are mutually
exclusive depending on which template you're rendering:

    __METRIC_PREFIX__        Prefix used on exporter metric names
                             (e.g. "nsd_node_storage_bytes").

    __DATASOURCE_UID__       Grafana datasource UID for Prometheus.
                             Defaults to "prometheus" in most
                             kube-prometheus installs.

    __CATEGORIES_OBJ_JSON__  JSON array of {id, color, label} objects,
                             substituted verbatim. Used by the native
                             plugin template (storage-usage.tmpl.json).

    __CATEGORIES_JSON__      JSON array of [id, color, label] tuples,
                             escaped for embedding inside a JSON
                             string value. Used by the legacy
                             Text/HTML template.

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


def render(
    template: str,
    prefix: str,
    datasource_uid: str,
    categories_tuple_inline: str,
    categories_obj_inline: str,
) -> str:
    return (
        template
        .replace("__METRIC_PREFIX__", prefix)
        .replace("__DATASOURCE_UID__", datasource_uid)
        .replace("__CATEGORIES_OBJ_JSON__", categories_obj_inline)
        .replace("__CATEGORIES_JSON__", categories_tuple_inline)
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
    categories = json.loads(args.categories.read_text())

    # Two forms:
    # 1. Tuple-form, escaped for embedding inside a JSON string value
    #    (used by the legacy template's `content` field).
    cats_tuple_inline = json.dumps(categories, separators=(",", ":")).replace('"', '\\"')
    # 2. Object-form, substituted verbatim into the panel options
    #    (used by the native plugin template).
    cats_obj = [
        {"id": id_, "color": color, "label": label}
        for id_, color, label in categories
    ]
    cats_obj_inline = json.dumps(cats_obj, separators=(",", ":"))

    rendered = render(
        template, args.prefix, args.datasource_uid,
        cats_tuple_inline, cats_obj_inline,
    )
    # Validate the result parses as a Grafana dashboard JSON.
    json.loads(rendered)

    if args.out:
        args.out.write_text(rendered)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
