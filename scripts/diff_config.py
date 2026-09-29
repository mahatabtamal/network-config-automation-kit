#!/usr/bin/env python3
"""diff_config.py - compare generated configs against saved 'show running-config'.

Detects configuration drift:
    * MISSING  : a line from the generated config was never applied to the device
    * EXTRA    : a line in the running config that the template does not produce
                 (manual changes, leftovers from previous configs)

Reads:
    inventory/devices.yml                    -> device list
    generated/<HOSTNAME>.cfg                 -> run scripts/generate_config.py first
    show-output/<HOSTNAME>/show_run.txt      -> saved 'show running-config'

Writes:
    reports/config-diff.md

Usage:
    python scripts/diff_config.py            # all devices
    python scripts/diff_config.py PE1 PE2    # selected devices

Exit code is 1 if any device shows drift or is missing files.
"""
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
INVENTORY = ROOT / "inventory" / "devices.yml"
GENERATED_DIR = ROOT / "generated"
SHOW_DIR = ROOT / "show-output"
REPORT_DIR = ROOT / "reports"

# Lines commonly present in a saved 'show run' capture that carry no
# configuration meaning; they are ignored during comparison.
NOISE_PREFIXES = (
    "building configuration",
    "current configuration",
)
NOISE_EXACT = {"end"}


def normalize(text, hostname=None):
    """Reduce raw config text to a set of meaningful configuration lines.

    * drops CLI prompt lines (e.g. 'PE1#show running-config')
    * drops comments (lines starting with '!') and blank lines
    * strips indentation (running-config indents sub-commands)
    * drops capture noise ('Building configuration...', 'end')
    """
    lines = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("!"):
            continue
        if line.lower() in NOISE_EXACT:
            continue
        if line.lower().startswith(NOISE_PREFIXES):
            continue
        if hostname and line.startswith(f"{hostname}#"):
            continue
        lines.add(line)
    return lines


def load_hostnames(selected=None):
    with open(INVENTORY, encoding="utf-8") as fh:
        inventory = yaml.safe_load(fh)
    hostnames = [d["hostname"] for d in inventory.get("devices", [])]
    if selected:
        unknown = set(selected) - set(hostnames)
        if unknown:
            sys.exit(f"error: unknown device(s) in inventory: {', '.join(sorted(unknown))}")
        hostnames = [h for h in hostnames if h in selected]
    return hostnames


def diff_device(hostname):
    """Compare one device. Returns a result dict."""
    gen_path = GENERATED_DIR / f"{hostname}.cfg"
    run_path = SHOW_DIR / hostname / "show_run.txt"

    result = {"hostname": hostname, "status": "PASS",
              "missing": [], "extra": [], "common": 0, "error": None}

    if not gen_path.exists():
        result["status"] = "MISSING"
        result["error"] = (f"generated config not found: {gen_path.relative_to(ROOT)} "
                           f"(run scripts/generate_config.py first)")
        return result
    if not run_path.exists():
        result["status"] = "MISSING"
        result["error"] = (f"saved show run not found: {run_path.relative_to(ROOT)} "
                           f"(save 'show running-config' from the device)")
        return result

    generated = normalize(gen_path.read_text(encoding="utf-8"))
    running = normalize(run_path.read_text(encoding="utf-8"), hostname)

    result["missing"] = sorted(generated - running)   # in template, not on device
    result["extra"] = sorted(running - generated)     # on device, not in template
    result["common"] = len(generated & running)
    if result["missing"] or result["extra"]:
        result["status"] = "DRIFT"
    return result


def write_markdown(results, path):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Configuration Drift Report",
        "",
        f"_Generated: {now} by `scripts/diff_config.py`_",
        "",
        "Compares `generated/<HOST>.cfg` (template output) against",
        "`show-output/<HOST>/show_run.txt` (saved running config).",
        "",
        "## Summary",
        "",
        "| Device | Common lines | Missing on device | Extra on device | Status |",
        "|--------|--------------|-------------------|-----------------|--------|",
    ]
    for r in results:
        if r["error"]:
            lines.append(f"| {r['hostname']} | - | - | - | {r['status']} |")
        else:
            lines.append(f"| {r['hostname']} | {r['common']} | {len(r['missing'])} "
                         f"| {len(r['extra'])} | {r['status']} |")

    lines += ["", "## Per-device detail", ""]
    for r in results:
        lines += [f"### {r['hostname']} ({r['status']})", ""]
        if r["error"]:
            lines += [f"- {r['error']}", ""]
            continue
        if r["status"] == "PASS":
            lines += ["- [x] Running config matches the generated configuration.", ""]
        if r["missing"]:
            lines += ["**Missing on device** (in generated config, not applied):", ""]
            lines += [f"- `{m}`" for m in r["missing"]]
            lines.append("")
        if r["extra"]:
            lines += ["**Extra on device** (not produced by the template):", ""]
            lines += [f"- `{e}`" for e in r["extra"]]
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv):
    hostnames = load_hostnames(argv[1:] or None)
    results = [diff_device(h) for h in hostnames]

    REPORT_DIR.mkdir(exist_ok=True)
    write_markdown(results, REPORT_DIR / "config-diff.md")

    # Console summary
    print(f"{'Device':<8} {'Common':<8} {'Missing':<9} {'Extra':<7} Status")
    print("-" * 48)
    for r in results:
        if r["error"]:
            print(f"{r['hostname']:<8} {'-':<8} {'-':<9} {'-':<7} {r['status']}")
        else:
            print(f"{r['hostname']:<8} {r['common']:<8} {len(r['missing']):<9} "
                  f"{len(r['extra']):<7} {r['status']}")
    for r in results:
        if r["error"]:
            print(f"ERROR: {r['hostname']}: {r['error']}")
        for m in r["missing"]:
            print(f"DRIFT: {r['hostname']}: missing on device: {m}")
        for e in r["extra"]:
            print(f"DRIFT: {r['hostname']}: extra on device: {e}")
    print("\nReport written: reports/config-diff.md")

    return 1 if any(r["status"] != "PASS" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
