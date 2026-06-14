---
id: pb-ransomware
title: "Playbook: Ransomware Detection & Response"
category: playbook
tags:
  - impact
  - ransomware
  - encryption
  - shadow-copy-deletion
  - T1486
  - T1490
  - T1489
  - T1059
  - T1562
---

# Playbook: Ransomware Detection & Response

**When to use.** Mass file-modification/rename alerts, ransom-note file creation, EDR detection of known ransomware, shadow-copy/backup deletion commands, or `vssadmin delete shadows` / `wbadmin delete` execution. Maps to T1486 (Data Encrypted for Impact), T1490 (Inhibit System Recovery), T1489 (Service Stop), T1562 (Impair Defenses).

**Triage (priority order). SPEED MATTERS — minimize dwell while encryption is active.**
1. Identify patient-zero host and the encrypting process tree (parent process, command line, signed/unsigned).
2. Determine encryption status: actively running vs. completed. Pull the ransom note + file extension for family attribution.
3. Check for recovery-inhibition: shadow-copy deletion, backup-service stops, boot-config tampering.
4. Identify the entry vector (look back for RDP brute force, phishing payload, exploited service, or compromised credential).

**Scope / blast-radius.** Find every host the encrypting account/binary touched: query EDR for the same binary hash and ransom-note filename fleet-wide. Map lateral spread — SMB writes, PsExec/WMI/scheduled-task creation, domain-admin usage. Check file servers and backup repositories specifically; encrypted backups change the recovery strategy entirely. Identify the compromised account(s) and every host where it authenticated.

**Containment (CONFIRM before destructive actions).** Network-isolate affected hosts immediately (EDR isolation, not power-off — preserve memory/keys). Disable the compromised account + reset its credentials. Block C2/exfil IOCs. Pause/segment backup network to protect clean backups. Kill the encrypting process fleet-wide if family is confirmed. Power-off is a last resort and operator-approved only (loses volatile evidence). Do not pay; coordinate with leadership/legal.

**Evidence to collect.** Memory image of patient-zero (keys may be recoverable), ransom note + sample encrypted files, encrypting binary hash, process tree, entry-vector logs, lateral-movement artifacts, list of affected hosts + accounts, backup integrity status.

**Verdict criteria.**
- **True positive:** ransom note present + bulk file-extension changes + recovery-inhibition commands + known family hash/TTP. Always treat as a major incident.
- **False positive / benign:** legitimate bulk-encryption tooling (authorized backup encryption, full-disk encryption rollout), a noisy file-sync client renaming files, or a red-team exercise (verify with the engagement window). Confirm any "mass file change" against change-management before standing down. Often co-occurs with pb-data-exfiltration (double-extortion) — check egress.
