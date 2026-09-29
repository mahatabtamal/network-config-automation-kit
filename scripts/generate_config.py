#!/usr/bin/env python3
"""generate_config.py - render Cisco IOS configs from YAML inventory.

Usage:
    python scripts/generate_config.py            # all devices
    python scripts/generate_config.py PE1 PE2    # selected devices

Reads:   inventory/devices.yml + templates/router_config.j2
Writes:  generated/<HOSTNAME>.cfg
"""
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parent.parent
INVENTORY = ROOT / "inventory" / "devices.yml"
TEMPLATES = ROOT / "templates"
OUT_DIR = ROOT / "generated"


def load_inventory(path=INVENTORY):
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    defaults = data.get("defaults", {})
    devices = []
    for dev in data.get("devices", []):
        merged = {**defaults, **dev}
        devices.append(merged)
    return devices


def render_devices(devices, selected=None):
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        undefined=StrictUndefined,          # fail loudly on missing variables
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    template = env.get_template("router_config.j2")

    OUT_DIR.mkdir(exist_ok=True)
    written = []
    for dev in devices:
        if selected and dev["hostname"] not in selected:
            continue
        cfg = template.render(**dev)
        out = OUT_DIR / f"{dev['hostname']}.cfg"
        out.write_text(cfg, encoding="utf-8")
        written.append(out)
    return written


def main(argv):
    selected = set(argv[1:]) or None
    devices = load_inventory()
    if selected:
        known = {d["hostname"] for d in devices}
        unknown = selected - known
        if unknown:
            sys.exit(f"error: unknown device(s) in inventory: {', '.join(sorted(unknown))}")

    written = render_devices(devices, selected)
    if not written:
        sys.exit("error: no devices matched.")

    print("Generated configuration:")
    for path in written:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv)
