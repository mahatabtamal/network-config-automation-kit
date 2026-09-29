# Network Configuration Automation & Audit Toolkit

A lightweight Python toolkit for generating standardized Cisco IOS
configurations and producing network documentation and configuration-audit
reports. It demonstrates basic network automation techniques applicable to
ISP and telecom network operations.

## Objectives

- Automate repetitive configuration generation.
- Separate configuration data (YAML) from configuration templates (Jinja2).
- Generate Cisco IOS configurations ready to paste into a Packet Tracer lab.
- Parse saved Cisco `show` command output with regular expressions.
- Generate network documentation automatically (Markdown) and machine-readable
  audit data (CSV).
- Identify basic configuration/operational issues.

## Architecture

```text
                 devices.yml
                     |
                     v
              +--------------+
              | Python       |
              | + Jinja2     |
              +------+-------+
                     |
                     v
              Cisco IOS config
                     |
                     v
             Packet Tracer lab
```

Audit workflow:

```text
Packet Tracer
     |
     v
Saved show output
     |
     v
Python parser
     |
     v
Audit / documentation
     |
     +------> CSV
     |
     +------> Markdown
```

## Technologies

Python 3, YAML (PyYAML), Jinja2, regular expressions, CSV, Markdown,
Cisco IOS CLI. No external network emulator or network-management server
is required.

## Project Structure

```text
.
├── README.md
├── inventory/
│   └── devices.yml              # single source of truth for all devices
├── templates/
│   └── router_config.j2         # Cisco IOS config template
├── scripts/
│   ├── generate_config.py       # YAML + Jinja2 -> generated/*.cfg
│   ├── audit_network.py         # saved show output -> reports/*
│   └── diff_config.py           # generated/*.cfg vs saved show run -> drift report
├── show-output/
│   ├── PE1/                     # saved 'show' output per device
│   │   ├── show_ip_int_brief.txt
│   │   ├── show_ip_route.txt
│   │   ├── show_ip_ospf_neighbor.txt
│   │   ├── show_ip_bgp_summary.txt
│   │   └── show_run.txt         # saved 'show running-config' (for diff mode)
│   ├── PE2/
│   └── PE3/
├── generated/                   # rendered configs (created by script)
└── reports/
    ├── network-audit.csv
    ├── network-audit.md
    └── config-diff.md
```

## Setup

```bash
pip install pyyaml jinja2
```

## 1. Configuration Generation

Device-specific information lives in `inventory/devices.yml`:

```yaml
- hostname: PE1
  router_id: 10.255.0.1
  loopback: 10.255.0.1
  ospf_process: 1
  interfaces:
    - name: GigabitEthernet0/0
      ip: 10.0.12.1
      mask: 255.255.255.252
      ...
```

`templates/router_config.j2` converts these variables into a full Cisco IOS
configuration (hostname, interfaces, OSPF, iBGP, vty/console lines). The same
template is reused for every device.

## 2. Configuration Generator

```bash
python scripts/generate_config.py            # all devices
python scripts/generate_config.py PE1 PE2    # selected devices only
```

```text
Generated configuration:
  generated/PE1.cfg
  generated/PE2.cfg
  generated/PE3.cfg
```

Review the rendered configs, then paste them into the Packet Tracer topology
(CLI config mode).

## 3. Network Audit

Save output from the lab devices into `show-output/<HOSTNAME>/`:

```text
show ip interface brief   ->  show_ip_int_brief.txt
show ip route             ->  show_ip_route.txt
show ip ospf neighbor     ->  show_ip_ospf_neighbor.txt
show ip bgp summary       ->  show_ip_bgp_summary.txt
show running-config       ->  show_run.txt   (used by diff mode, see section 6)
```

Then run:

```bash
python scripts/audit_network.py
```

The script extracts hostname, interface status, IP addresses, OSPF neighbors,
BGP peers and routing information, then compares everything against the
expectations declared in `inventory/devices.yml` (`expected:` block).

## 4. Audit Report

```text
Device   Interfaces   OSPF Neighbors   BGP Peers   Status
----------------------------------------------------------------
PE1      3/3 UP       2                2           PASS
PE2      2/3 UP       1                1           WARNING
PE3      n/a          0                0           MISSING
```

- `reports/network-audit.md` - human-readable documentation with per-device
  interface/OSPF/BGP tables, passed checks, and warnings.
- `reports/network-audit.csv` - flat data for spreadsheets or other tools.

The script exits with code 1 if any device is not PASS, so it can be used in
CI or cron jobs.

## 5. Basic Audit Rules

```text
[OK]  Expected hostname matches inventory
[OK]  Expected number of interfaces operational (up/up)
[OK]  Expected loopback configured with the right IP
[OK]  OSPF neighbors established (FULL state)
[OK]  BGP peers established (numeric State/PfxRcd)
[OK]  Routing table present
[OK]  Device output available
```

Example warning:

```text
WARNING: PE2: 1 expected BGP peer(s) missing/not established
```

The goal is not to build a complete configuration-management system, but to
demonstrate how routine network checks can be automated.

## 6. Configuration Drift Detection (Diff Mode)

`scripts/diff_config.py` compares the config produced by the template
(`generated/<HOST>.cfg`) against the config actually running on the device
(`show-output/<HOST>/show_run.txt`, a saved `show running-config`).

Both sides are normalized before comparison: CLI prompts, comment lines,
indentation, and capture noise (`Building configuration...`, `end`) are
removed, so only meaningful configuration statements are compared.

```bash
python scripts/generate_config.py    # first render the expected configs
python scripts/diff_config.py        # then compare against saved show run
python scripts/diff_config.py PE2    # single device
```

```text
Device   Common   Missing   Extra   Status
------------------------------------------------
PE1      35       0         0       PASS
PE2      33       2         2       DRIFT
PE3      -        -         -       MISSING
DRIFT: PE2: missing on device: neighbor 10.255.0.3 remote-as 65001
DRIFT: PE2: extra on device: banner motd ^C Maintenance window Sunday 02:00 UTC ^C
```

Two kinds of drift are reported.

- **Missing on device** - a line from the generated config was never applied
  (e.g. a forgotten iBGP neighbor).
- **Extra on device** - a line in the running config the template does not
  produce (manual changes, leftovers from previous configs).

Results are written to `reports/config-diff.md`. As with the audit script, the
exit code is 1 if any device shows drift or is missing files, so diff mode can
also run from CI or cron.

## Extending

- Add a device: append an entry to `inventory/devices.yml` and re-run the
  generator.
- Add a check: extend `audit_device()` in `scripts/audit_network.py`.
