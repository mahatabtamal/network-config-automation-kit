#!/usr/bin/env python3
"""audit_network.py - parse saved Cisco 'show' output and audit the network.

Reads:
    inventory/devices.yml           -> expected baseline per device
    show-output/<HOSTNAME>/*.txt    -> saved CLI output (Packet Tracer)

Writes:
    reports/network-audit.csv
    reports/network-audit.md

Usage:
    python scripts/audit_network.py
"""
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
INVENTORY = ROOT / "inventory" / "devices.yml"
SHOW_DIR = ROOT / "show-output"
REPORT_DIR = ROOT / "reports"

# --------------------------------------------------------------------------
# Parsers (one per saved 'show' command; regex-based, no vendor libraries)
# --------------------------------------------------------------------------

HOST_RE = re.compile(r"^(\S+?)#")
INTF_RE = re.compile(
    r"^(?P<name>\S+)\s+"
    r"(?P<ip>\S+)\s+"
    r"(?P<ok>YES|NO)\s+"
    r"(?P<method>\S+)\s+"
    r"(?P<status>administratively down|up|down)\s+"
    r"(?P<protocol>up|down)\s*$",
    re.IGNORECASE,
)
ROUTE_RE = re.compile(
    r"^(?P<code>[A-Z\*]{1,2})\s+(?P<prefix>\d+\.\d+\.\d+\.\d+/\d+)\s+"
    r"\[.+\]\svia\s(?P<via>\d+\.\d+\.\d+\.\d+)"
)
ROUTE_DIRECT_RE = re.compile(
    r"^(?P<code>[CD])\s+(?P<prefix>\d+\.\d+\.\d+\.\d+/\d+)\sis\sdirectly\sconnected,\s(?P<intf>\S+)"
)
OSPF_NEIGH_RE = re.compile(
    r"^(?P<id>\d+\.\d+\.\d+\.\d+)\s+\d+\s+(?P<state>FULL/\S+|INIT/\S+|EXCHANGE/\S+|2WAY/\S+)\s+"
    r"\d+:\d+:\d+\s+(?P<addr>\d+\.\d+\.\d+\.\d+)\s+(?P<intf>\S+)"
)
BGP_RE = re.compile(
    r"^(?P<ip>\d+\.\d+\.\d+\.\d+)\s+(?P<v>\d+)\s+(?P<as>\d+)\s+"
    r"(?P<msgrecv>\d+)\s+(?P<msgsent>\d+)\s+"
    r"(?P<tblver>\S+)\s+(?P<inq>\S+)\s+(?P<outq>\S+)\s+(?P<updown>\S+)\s+"
    r"(?P<state>\S+)\s*$"
)


def _read(device_dir, filename):
    path = device_dir / filename
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def detect_hostname(text):
    """Grab the hostname from the first CLI prompt, e.g. 'PE1#show ...'."""
    if not text:
        return None
    for line in text.splitlines():
        m = HOST_RE.match(line.strip())
        if m:
            return m.group(1)
    return None


def parse_interfaces(text):
    """show ip interface brief -> list of dicts."""
    result = []
    if not text:
        return result
    for line in text.splitlines():
        m = INTF_RE.match(line.strip())
        if m and not line.strip().startswith("Interface"):
            d = m.groupdict()
            d["up"] = d["status"].lower() == "up" and d["protocol"].lower() == "up"
            result.append(d)
    return result


def parse_routes(text):
    """show ip route -> list of dicts (via-routes and directly-connected)."""
    result = []
    if not text:
        return result
    for line in text.splitlines():
        m = ROUTE_RE.match(line.strip()) or ROUTE_DIRECT_RE.match(line.strip())
        if m:
            result.append(m.groupdict())
    return result


def parse_ospf_neighbors(text):
    """show ip ospf neighbor -> list of dicts."""
    result = []
    if not text:
        return result
    for line in text.splitlines():
        m = OSPF_NEIGH_RE.match(line.strip())
        if m:
            result.append(m.groupdict())
    return result


def parse_bgp_summary(text):
    """show ip bgp summary -> list of dicts; State/PfxRcd numeric == established."""
    result = []
    if not text:
        return result
    for line in text.splitlines():
        m = BGP_RE.match(line.strip())
        if m:
            d = m.groupdict()
            d["established"] = d["state"].isdigit()
            result.append(d)
    return result


# --------------------------------------------------------------------------
# Audit logic
# --------------------------------------------------------------------------

def audit_device(expected, device_dir):
    """Run the audit rules for one device. Returns a result dict."""
    findings, warnings = [], []
    hostname = expected["hostname"]
    has_output = device_dir.exists() and any(device_dir.glob("*.txt"))

    # Rule: device output available
    if not has_output:
        warnings.append(f"{hostname}: no saved show output found in show-output/{hostname}/")
        return {
            "hostname": hostname, "interfaces_up": 0, "interfaces_total": 0,
            "ospf_neighbors": 0, "bgp_peers": 0, "routes": 0,
            "status": "MISSING", "warnings": warnings, "findings": findings,
            "interfaces": [], "ospf": [], "bgp": [],
        }

    # Rule: expected hostname appears in saved output
    prompt_host = None
    for f in sorted(device_dir.glob("*.txt")):
        prompt_host = detect_hostname(f.read_text(encoding="utf-8"))
        if prompt_host:
            break
    if prompt_host != hostname:
        warnings.append(
            f"{hostname}: expected hostname '{hostname}' but found "
            f"'{prompt_host or 'unknown'}' in saved output"
        )
    else:
        findings.append(f"{hostname}: hostname matches inventory (OK)")

    # Interfaces
    interfaces = parse_interfaces(_read(device_dir, "show_ip_int_brief.txt"))
    up = sum(1 for i in interfaces if i["up"])
    exp_up = expected.get("interfaces_up", 0)
    if interfaces:
        for i in interfaces:
            if not i["up"]:
                warnings.append(
                    f"{hostname}: interface {i['name']} is {i['status']}/{i['protocol']} (not up/up)"
                )
        if up < exp_up:
            warnings.append(
                f"{hostname}: only {up} interface(s) up/up, expected {exp_up}"
            )
        else:
            findings.append(f"{hostname}: {up}/{len(interfaces)} interfaces up/up (OK)")
    else:
        warnings.append(f"{hostname}: show ip interface brief output missing or unparsable")

    # Loopback present
    if interfaces and not any(i["name"].lower().startswith("loopback") for i in interfaces):
        warnings.append(f"{hostname}: expected loopback interface not found")
    elif interfaces:
        lo = next(i for i in interfaces if i["name"].lower().startswith("loopback"))
        if lo["ip"] == expected.get("loopback"):
            findings.append(f"{hostname}: loopback0 = {lo['ip']} matches inventory (OK)")
        else:
            warnings.append(
                f"{hostname}: loopback0 = {lo['ip']}, expected {expected.get('loopback')}"
            )

    # OSPF neighbors
    ospf = parse_ospf_neighbors(_read(device_dir, "show_ip_ospf_neighbor.txt"))
    full = [n for n in ospf if n["state"].upper().startswith("FULL")]
    exp_ospf = expected.get("ospf_neighbors", 0)
    for n in ospf:
        if not n["state"].upper().startswith("FULL"):
            warnings.append(
                f"{hostname}: OSPF neighbor {n['id']} stuck in {n['state']}"
            )
    if len(full) < exp_ospf:
        warnings.append(
            f"{hostname}: {len(full)} OSPF neighbor(s) FULL, expected {exp_ospf}"
        )
    elif exp_ospf:
        findings.append(f"{hostname}: {len(full)} OSPF neighbor(s) FULL (OK)")

    # BGP peers
    bgp = parse_bgp_summary(_read(device_dir, "show_ip_bgp_summary.txt"))
    est = [b for b in bgp if b["established"]]
    exp_bgp = expected.get("bgp_peers", 0)
    for b in bgp:
        if not b["established"]:
            warnings.append(
                f"{hostname}: BGP peer {b['ip']} not established (state: {b['state']})"
            )
    if len(est) < exp_bgp:
        missing = exp_bgp - len(est)
        warnings.append(f"{hostname}: {missing} expected BGP peer(s) missing/not established")
    elif exp_bgp:
        findings.append(f"{hostname}: {len(est)} BGP peer(s) established (OK)")

    # Routes (informational)
    routes = parse_routes(_read(device_dir, "show_ip_route.txt"))
    if not routes:
        warnings.append(f"{hostname}: show ip route output missing or no routes found")

    status = "PASS" if not warnings else "WARNING"
    return {
        "hostname": hostname,
        "interfaces_up": up, "interfaces_total": len(interfaces),
        "ospf_neighbors": len(full), "bgp_peers": len(est), "routes": len(routes),
        "status": status, "warnings": warnings, "findings": findings,
        "interfaces": interfaces, "ospf": ospf, "bgp": bgp,
    }


# --------------------------------------------------------------------------
# Report writers
# --------------------------------------------------------------------------

def write_csv(results, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["device", "interfaces_up", "interfaces_total",
                    "ospf_neighbors", "bgp_peers", "routes", "status", "warnings"])
        for r in results:
            w.writerow([r["hostname"], r["interfaces_up"], r["interfaces_total"],
                        r["ospf_neighbors"], r["bgp_peers"], r["routes"],
                        r["status"], "; ".join(r["warnings"])])


def write_markdown(results, path):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Network Audit Report",
        "",
        f"_Generated: {now} by `scripts/audit_network.py`_",
        "",
        "## Summary",
        "",
        "| Device | Interfaces | OSPF Neighbors | BGP Peers | Routes | Status |",
        "|--------|------------|----------------|-----------|--------|--------|",
    ]
    for r in results:
        iface = (f"{r['interfaces_up']}/{r['interfaces_total']} UP"
                 if r["interfaces_total"] else "n/a")
        icon = {"PASS": "PASS", "WARNING": "WARNING", "MISSING": "MISSING"}[r["status"]]
        lines.append(f"| {r['hostname']} | {iface} | {r['ospf_neighbors']} "
                     f"| {r['bgp_peers']} | {r['routes']} | {icon} |")

    lines += ["", "## Per-device detail", ""]
    for r in results:
        lines += [f"### {r['hostname']} ({r['status']})", ""]
        if r["interfaces"]:
            lines += ["**Interfaces**", "",
                      "| Interface | IP | Status | Protocol |",
                      "|-----------|----|--------|----------|"]
            for i in r["interfaces"]:
                lines.append(f"| {i['name']} | {i['ip']} | {i['status']} | {i['protocol']} |")
            lines.append("")
        if r["ospf"]:
            lines += ["**OSPF neighbors**", "",
                      "| Neighbor ID | State | Address | Interface |",
                      "|-------------|-------|---------|-----------|"]
            for n in r["ospf"]:
                lines.append(f"| {n['id']} | {n['state']} | {n['addr']} | {n['intf']} |")
            lines.append("")
        if r["bgp"]:
            lines += ["**BGP peers**", "",
                      "| Peer | AS | State/PfxRcd | Established |",
                      "|------|----|--------------|-------------|"]
            for b in r["bgp"]:
                lines.append(f"| {b['ip']} | {b['as']} | {b['state']} "
                             f"| {'yes' if b['established'] else 'no'} |")
            lines.append("")
        if r["findings"]:
            lines += ["**Checks passed**", ""]
            lines += [f"- [x] {f}" for f in r["findings"]]
            lines.append("")
        if r["warnings"]:
            lines += ["**Warnings**", ""]
            lines += [f"- WARNING: {w}" for w in r["warnings"]]
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    with open(INVENTORY, encoding="utf-8") as fh:
        inventory = yaml.safe_load(fh)
    devices = inventory.get("devices", [])

    results = []
    for dev in devices:
        expected = {
            "hostname": dev["hostname"],
            "loopback": dev.get("loopback"),
            **dev.get("expected", {}),
        }
        device_dir = SHOW_DIR / dev["hostname"]
        results.append(audit_device(expected, device_dir))

    REPORT_DIR.mkdir(exist_ok=True)
    write_csv(results, REPORT_DIR / "network-audit.csv")
    write_markdown(results, REPORT_DIR / "network-audit.md")

    # Console summary
    print(f"{'Device':<8} {'Interfaces':<12} {'OSPF Neighbors':<16} "
          f"{'BGP Peers':<11} Status")
    print("-" * 64)
    for r in results:
        iface = (f"{r['interfaces_up']}/{r['interfaces_total']} UP"
                 if r["interfaces_total"] else "n/a")
        print(f"{r['hostname']:<8} {iface:<12} {r['ospf_neighbors']:<16} "
              f"{r['bgp_peers']:<11} {r['status']}")
    for r in results:
        for w in r["warnings"]:
            print(f"WARNING: {w}")
    print(f"\nReports written: reports/network-audit.csv, reports/network-audit.md")

    return 1 if any(r["status"] != "PASS" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
