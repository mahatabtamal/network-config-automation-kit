# Configuration Drift Report

_Generated: 2026-09-29 19:05 by `scripts/diff_config.py`_

Compares `generated/<HOST>.cfg` (template output) against
`show-output/<HOST>/show_run.txt` (saved running config).

## Summary

| Device | Common lines | Missing on device | Extra on device | Status |
|--------|--------------|-------------------|-----------------|--------|
| PE1 | 35 | 0 | 0 | PASS |
| PE2 | 33 | 2 | 2 | DRIFT |
| PE3 | - | - | - | MISSING |

## Per-device detail

### PE1 (PASS)

- [x] Running config matches the generated configuration.

### PE2 (DRIFT)

**Missing on device** (in generated config, not applied):

- `neighbor 10.255.0.3 description iBGP peer PE3`
- `neighbor 10.255.0.3 remote-as 65001`

**Extra on device** (not produced by the template):

- `banner motd ^C Maintenance window Sunday 02:00 UTC ^C`
- `shutdown`

### PE3 (MISSING)

- saved show run not found: show-output/PE3/show_run.txt (save 'show running-config' from the device)
