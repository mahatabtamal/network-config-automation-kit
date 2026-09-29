# Network Audit Report

_Generated: 2026-09-29 18:57 by `scripts/audit_network.py`_

## Summary

| Device | Interfaces | OSPF Neighbors | BGP Peers | Routes | Status |
|--------|------------|----------------|-----------|--------|--------|
| PE1 | 3/3 UP | 2 | 2 | 7 | PASS |
| PE2 | 2/3 UP | 1 | 1 | 6 | WARNING |
| PE3 | n/a | 0 | 0 | 0 | MISSING |

## Per-device detail

### PE1 (PASS)

**Interfaces**

| Interface | IP | Status | Protocol |
|-----------|----|--------|----------|
| GigabitEthernet0/0 | 10.0.12.1 | up | up |
| GigabitEthernet0/1 | 10.0.13.1 | up | up |
| Loopback0 | 10.255.0.1 | up | up |

**OSPF neighbors**

| Neighbor ID | State | Address | Interface |
|-------------|-------|---------|-----------|
| 10.255.0.2 | FULL/DR | 10.0.13.2 | GigabitEthernet0/1 |
| 10.255.0.3 | FULL/BDR | 10.0.12.2 | GigabitEthernet0/0 |

**BGP peers**

| Peer | AS | State/PfxRcd | Established |
|------|----|--------------|-------------|
| 10.255.0.2 | 65001 | 4 | yes |
| 10.255.0.3 | 65001 | 3 | yes |

**Checks passed**

- [x] PE1: hostname matches inventory (OK)
- [x] PE1: 3/3 interfaces up/up (OK)
- [x] PE1: loopback0 = 10.255.0.1 matches inventory (OK)
- [x] PE1: 2 OSPF neighbor(s) FULL (OK)
- [x] PE1: 2 BGP peer(s) established (OK)

### PE2 (WARNING)

**Interfaces**

| Interface | IP | Status | Protocol |
|-----------|----|--------|----------|
| GigabitEthernet0/0 | 10.0.13.2 | up | up |
| GigabitEthernet0/1 | 10.0.23.1 | administratively down | down |
| Loopback0 | 10.255.0.2 | up | up |

**OSPF neighbors**

| Neighbor ID | State | Address | Interface |
|-------------|-------|---------|-----------|
| 10.255.0.1 | FULL/BDR | 10.0.13.1 | GigabitEthernet0/0 |
| 10.255.0.3 | INIT/- | 10.0.34.2 | GigabitEthernet0/1 |

**BGP peers**

| Peer | AS | State/PfxRcd | Established |
|------|----|--------------|-------------|
| 10.255.0.1 | 65001 | 4 | yes |
| 10.255.0.3 | 65001 | Active | no |

**Checks passed**

- [x] PE2: hostname matches inventory (OK)
- [x] PE2: loopback0 = 10.255.0.2 matches inventory (OK)

**Warnings**

- WARNING: PE2: interface GigabitEthernet0/1 is administratively down/down (not up/up)
- WARNING: PE2: only 2 interface(s) up/up, expected 3
- WARNING: PE2: OSPF neighbor 10.255.0.3 stuck in INIT/-
- WARNING: PE2: 1 OSPF neighbor(s) FULL, expected 2
- WARNING: PE2: BGP peer 10.255.0.3 not established (state: Active)
- WARNING: PE2: 1 expected BGP peer(s) missing/not established

### PE3 (MISSING)

**Warnings**

- WARNING: PE3: no saved show output found in show-output/PE3/
