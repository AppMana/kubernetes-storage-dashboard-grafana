"""Entry point. `python -m exporter` loads config and starts the server."""
from __future__ import annotations

import argparse
import os
import sys

from exporter.config import load
from exporter.server import serve


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="storage-exporter")
    p.add_argument("--config", help="Path to user config YAML (default: $CONFIG_FILE or /etc/storage-exporter/config.yaml)")
    args = p.parse_args(argv)

    cfg = load(args.config)
    node = os.environ.get("NODE_NAME", "unknown")
    serve(cfg, node)
    return 0  # unreachable; serve() loops forever


if __name__ == "__main__":
    sys.exit(main())
