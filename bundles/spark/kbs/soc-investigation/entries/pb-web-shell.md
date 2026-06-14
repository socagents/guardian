---
id: pb-web-shell
title: "Playbook: Web Shell on Internet-Facing Server"
category: playbook
tags:
  - persistence
  - web-shell
  - server-software-component
  - exploitation
  - T1505.003
  - T1190
  - T1059
  - T1071.001
---

# Playbook: Web Shell on Internet-Facing Server

**When to use.** A new/modified script in a web-root, a web server process spawning a shell or system binary (e.g., `w3wp.exe`/`httpd`→`cmd`/`bash`), WAF alerts on command-injection patterns, or AV/EDR detection of a known web-shell signature. Maps to T1505.003 (Web Shell), T1190 (Exploit Public-Facing Application), T1059 (Command/Scripting Interpreter).

**Triage (priority order).**
1. Locate the suspect file: path under web-root, creation/modification time, owner, and content (look for `eval`, `system`, `passthru`, base64 blobs, password gates).
2. Identify the writing process and the request that created it — correlate file ctime with web-access logs to find the exploit request and source IP.
3. Pull all subsequent requests TO the web-shell URL (same source IP, POST bodies, user-agent) to reconstruct attacker commands.
4. Check for child processes spawned by the web server and any outbound connections.

**Scope / blast-radius.** Determine what the attacker did post-access: commands run, files read/written, credentials harvested from config files, and lateral movement off the server. Search every web-facing host running the same vulnerable software/version for additional shells (grep web-roots for the same signature). Identify whether the server holds or can reach sensitive data/credentials (DB connection strings, service accounts) — those are now suspect.

**Containment (confirm before destructive actions).** Isolate the server from the network (preserve it — don't wipe yet). Block the attacker source IP at the edge/WAF. Capture the web-shell file before removal, then remove it. Patch/virtual-patch the exploited vulnerability. Rotate any credentials stored on or reachable from the host. Confirm with the operator before taking a production web service offline; consider failover. Plan rebuild from a known-good image — web-shell hosts are often re-compromised.

**Evidence to collect.** Web-shell file + hash, web-access logs showing the exploit request and command requests, source IPs/user-agents, process-spawn telemetry, list of vulnerable hosts, any exfiltrated/accessed file list.

**Verdict criteria.**
- **True positive:** an unexpected web-root file containing command-execution primitives + access-log evidence of POST interaction from an external IP + web-server-spawned shell processes.
- **False positive / benign:** legitimate admin/CMS plugins, deployment scripts, or developer debug endpoints — verify against change-management and the application's expected file manifest. A signature match on a quarantined sample in a backup directory is not a live shell.
