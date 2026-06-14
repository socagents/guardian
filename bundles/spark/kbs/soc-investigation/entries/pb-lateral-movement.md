---
id: pb-lateral-movement
title: "Playbook: Lateral Movement Investigation"
category: playbook
tags:
  - lateral-movement
  - remote-services
  - smb
  - rdp
  - pass-the-hash
  - T1021
  - T1021.001
  - T1021.002
  - T1570
  - T1550
---

# Playbook: Lateral Movement Investigation

**When to use.** Anomalous remote-logon chains (one host authenticating to many), PsExec/WMI/WinRM/PowerShell-remoting service creation, RDP from an unusual source, admin-share writes, or pass-the-hash/ticket alerts. Maps to T1021 (Remote Services) and subtechniques .001 RDP / .002 SMB-admin-shares, T1570 (Lateral Tool Transfer), T1550 (Use Alternate Auth Material).

**Triage (priority order).**
1. Identify the source host + account driving the movement. Pull its recent auth history and process tree.
2. Reconstruct the logon chain: which destinations, logon types (3 network / 10 RemoteInteractive), and timestamps. Build the host-to-host graph.
3. Determine the auth method — interactive password, NTLM hash, Kerberos ticket (look for overpass-the-hash / forged tickets), or stolen service account.
4. Check what executed on each destination (service install 7045, scheduled task, WMI process create).

**Scope / blast-radius.** Treat the source account as compromised and enumerate EVERY host it authenticated to in the window. Pivot on any new accounts/credentials harvested at each hop. Identify whether domain-admin or a privileged service account was used — if so, blast radius is potentially the whole domain (assume DC compromise; consider pb-credential-access for DCSync). Map tool-transfer artifacts (admin-share file writes) to find dropped implants.

**Containment (confirm before destructive actions).** Disable/reset the compromised account(s) and revoke Kerberos tickets (reset twice for krbtgt only with operator approval — it disrupts the domain). Isolate the source host and any confirmed-implanted destinations. Block the lateral tooling (PsExec variants) via EDR. Disable unnecessary admin shares / remote-service paths on affected segments. Confirm account disablement won't break a production service before pulling it.

**Evidence to collect.** Host-to-host logon graph, 4624/4648/4672/4769/7045 events, source process tree, transferred tool hashes, account-usage timeline, ticket/hash artifacts.

**Verdict criteria.**
- **True positive:** one account/host fanning out to multiple destinations in a short window, off-hours, with service-creation or tool-transfer on the destinations, especially using NTLM hashes or anomalous source. 
- **False positive / benign:** vulnerability scanners, patch-management/SCCM, backup agents, and admin jump-box activity all fan out legitimately — verify against the asset inventory of known management hosts and service accounts. A single expected RDP from an admin workstation is benign.
