---
id: pb-credential-access
title: "Playbook: Credential Access & Theft"
category: playbook
tags:
  - credential-access
  - lsass-dump
  - kerberoasting
  - dcsync
  - brute-force
  - T1003
  - T1003.001
  - T1003.006
  - T1110
  - T1558
  - T1556
---

# Playbook: Credential Access & Theft

**When to use.** LSASS memory-access/dump alerts, credential-dumping tool signatures (Mimikatz/comsvcs), Kerberoasting (many TGS requests for SPNs with RC4), DCSync (replication from a non-DC), brute-force/password-spray spikes, or registry SAM/SECURITY hive access. Maps to T1003 (OS Credential Dumping) incl. .001 LSASS / .006 DCSync, T1110 (Brute Force), T1558 (Steal/Forge Kerberos Tickets), T1556 (Modify Auth Process).

**Triage (priority order).**
1. Identify the technique + the accessing process/account and the target (LSASS, SAM hive, DC replication, KDC).
2. For dumping: capture the process tree and command line; was a dump file written? For spray/brute-force: source IP, targeted accounts, success-after-failure pattern.
3. Determine which credentials were exposed — local accounts, cached domain creds, service accounts (SPNs), or the whole directory (DCSync = treat as full-domain credential compromise).
4. Check for successful authentications following the theft (the payoff).

**Scope / blast-radius.** Every credential present in the dumped material is now compromised — enumerate them (local admins, logged-on domain users, service accounts). For DCSync/NTDS access, assume ALL domain credentials including krbtgt are stolen → golden-ticket risk. Trace the thief account's subsequent logons (pivot to pb-lateral-movement). For spray, list every account that authenticated successfully from the attacker source. Identify privileged accounts exposed first.

**Containment (CONFIRM before high-impact actions).** Reset exposed credentials, prioritizing privileged + service accounts. For confirmed DCSync/NTDS theft: reset krbtgt TWICE (operator-approved — disrupts the domain) and rotate all privileged creds. Disable/reset the thief account and revoke tickets/sessions. Isolate the host that ran the dumper. Block the dumper hash + brute-force source IP. Enable/verify Credential Guard + LSA protection going forward. Confirm service-account resets against dependent services to avoid outages.

**Evidence to collect.** Dumper process tree + hash, dump file artifact, 4624/4625/4672/4769/4662 (replication) events, list of exposed credentials, attacker source IPs, post-theft successful logons.

**Verdict criteria.**
- **True positive:** non-standard process opening LSASS with read/clone access, replication requested by a non-DC machine account, RC4 TGS bursts for service SPNs, or password-spray with successes from a foreign IP.
- **False positive / benign:** EDR/AV products and some backup/monitoring tools legitimately read LSASS — verify the process is an allow-listed security agent. Domain controllers replicate normally between themselves. A few failed logons after a password change are benign. Validate against known service accounts and management tooling before escalating.
