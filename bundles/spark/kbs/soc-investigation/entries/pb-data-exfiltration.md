---
id: pb-data-exfiltration
title: "Playbook: Data Exfiltration Investigation"
category: playbook
tags:
  - exfiltration
  - data-theft
  - dlp
  - large-egress
  - cloud-storage
  - T1041
  - T1567
  - T1048
  - T1030
  - T1020
---

# Playbook: Data Exfiltration Investigation

**When to use.** DLP alerts on sensitive-data movement, anomalous large outbound transfers, uploads to personal cloud storage / unsanctioned SaaS, unusual database bulk-export, or egress to a rare external destination. Maps to T1041 (Exfil over C2), T1567 (Exfil to Web Service), T1048 (Exfil over Alternative Protocol), T1030 (Data Transfer Size Limits), T1020 (Automated Exfiltration).

**Triage (priority order).**
1. Identify the source host/account, the destination (domain/IP/cloud service), protocol, and the byte volume + duration.
2. Determine WHAT data moved: file names/types, DLP classification, database/table, repo. Sensitivity drives severity.
3. Establish baseline: is this destination/volume normal for this user/host? Compare to historical egress.
4. Identify the moving process and whether it's interactive (user-driven) or automated (scripted/scheduled — staging + chunking suggests adversary tooling).

**Scope / blast-radius.** Quantify the full dataset: total bytes, number of records/files, and the time window of transfer. Check for staging (large archive creation, `.rar`/`.7z`/`.zip` in temp/staging dirs) preceding egress. Pivot on the destination across all hosts/users — exfil channels are reused. Determine if the data is regulated (PII/PHI/PCI/IP) to trigger breach-notification obligations. Trace back to the compromised account/host and how access was obtained.

**Containment (confirm before destructive actions).** Block the destination domain/IP at proxy/firewall and revoke any cloud-storage app authorization. Disable the source account + revoke sessions. Isolate the host if adversary-driven. Apply DLP block policy for the data class. For SaaS, revoke OAuth grants/API tokens used. Confirm before blocking a destination that might be a sanctioned business service used by others.

**Evidence to collect.** Netflow/proxy logs with byte counts + timestamps, DLP event with classified content, destination IOCs, staging-archive hashes, list of files/records exfiltrated, source account + access path, cloud audit logs (download/upload events).

**Verdict criteria.**
- **True positive:** sensitive/classified data + anomalous destination (personal cloud, rare ASN, attacker infra) + abnormal volume/timing + staging artifacts or a compromised account. Adversary-driven exfil escalates to a breach incident.
- **False positive / benign:** sanctioned backup/sync (verify the service is approved), legitimate large business transfer with a known recipient, or a user moving their own work files to approved storage. Validate against approved-app inventory and the user's role before escalating. Frequently paired with pb-c2-beaconing or pb-ransomware (double-extortion).
