---
id: pb-insider-threat
title: "Playbook: Insider Threat / Malicious or Negligent Insider"
category: playbook
tags:
  - insider-threat
  - data-theft
  - privilege-abuse
  - policy-violation
  - hr-coordination
  - T1078
  - T1530
  - T1052
  - T1567
  - T1213
---

# Playbook: Insider Threat / Malicious or Negligent Insider

**When to use.** A legitimately-authorized user behaves abnormally: bulk-downloading data outside their role, accessing systems unrelated to their job, mass-copying to USB/personal cloud, activity spikes around resignation/termination, off-hours privileged actions, or an HR/legal referral. Maps to T1078 (Valid Accounts), T1530 (Data from Cloud Storage), T1052 (Exfil over Physical Medium), T1567 (Exfil to Web Service), T1213 (Data from Information Repositories).

**Triage (priority order). HANDLE WITH DISCRETION — loop in HR/Legal early; preserve, don't tip off.**
1. Establish the baseline for this user's role: normal systems, data volumes, hours, locations. Identify the specific deviation.
2. Pull access logs across repositories (file shares, SaaS, code repos, CRM/HR systems) for the suspect window.
3. Check egress channels: USB/removable-media events, personal cloud uploads, personal-email forwarding, print logs.
4. Correlate with HR context (resignation date, performance issues, access changes) — WITHOUT alerting the subject.

**Scope / blast-radius.** Quantify what was accessed and what left: which repositories, how many files/records, classification, and via which channels (download, USB, cloud, email, print). Map the full timeline from first anomalous access to present. Check for credential sharing or use of others' accounts. Determine if the data is regulated or IP/trade-secret. Identify any sabotage (deletions, backdoor accounts, logic bombs) in addition to theft.

**Containment (confirm with HR/Legal before acting — this is process-sensitive).** Do NOT unilaterally disable the account; coordinate timing with HR/Legal to preserve evidence and employment process. When approved: revoke access, disable account, block personal-cloud/USB channels, and revoke remote access. Preserve mailbox, endpoint, and logs under legal hold. For imminent departure, pre-stage access removal for the termination moment. Avoid actions that destroy evidence or alert the subject prematurely.

**Evidence to collect (chain-of-custody matters — likely HR/legal proceeding).** Access logs across all repositories, DLP/USB/cloud/print events, file lists with classification, timeline, the user's role/entitlements, mailbox/endpoint forensic image under legal hold, HR context. Document handling for admissibility.

**Verdict criteria.**
- **True positive:** access clearly outside role + bulk/abnormal volume + exfil to a personal channel + timing tied to departure or grievance, especially with attempts to conceal (deleting logs, clearing history).
- **False positive / benign:** a legitimate role/project change, an approved bulk export with business justification, or a manager's sanctioned access. Validate against current entitlements, ticketed approvals, and the user's actual responsibilities before escalating. Negligent (not malicious) policy violations route to security-awareness/HR, not incident response.
