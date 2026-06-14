---
id: pb-c2-beaconing
title: "Playbook: Command-and-Control Beaconing"
category: playbook
tags:
  - command-and-control
  - c2
  - beaconing
  - implant
  - dns-tunneling
  - T1071
  - T1071.001
  - T1071.004
  - T1573
  - T1090
  - T1568
---

# Playbook: Command-and-Control Beaconing

**When to use.** Periodic outbound connections to a rare/newly-registered domain or IP, regular-interval traffic with low jitter, beaconing IOC match (Cobalt Strike/Sliver/etc.), DNS-tunneling patterns (high-volume TXT/long subdomains), or traffic to known-bad infra. Maps to T1071 (Application Layer Protocol) incl. .001 web / .004 DNS, T1573 (Encrypted Channel), T1090 (Proxy), T1568 (Dynamic Resolution / DGA).

**Triage (priority order).**
1. Characterize the beacon: destination(s), interval + jitter, protocol (HTTP/S, DNS, TLS), JA3/SNI, user-agent, and packet sizes.
2. Identify the originating process on the host (which binary is calling out — signed? injected? living-off-the-land?).
3. Reputation/age-check the destination; check for domain-fronting, fast-flux, or DGA naming.
4. Determine duration — how long has the host been beaconing? Find first-seen.

**Scope / blast-radius.** Pivot on the C2 destination(s) and JA3/SNI fingerprint across ALL hosts — beacons share infra. Enumerate every host contacting the same domain/IP family. Identify the implant binary by hash and search fleet-wide. Determine the entry vector (first-seen process ancestry → phishing payload, web-shell, or lateral movement) and whether the implant moved laterally or established additional persistence. Check whether the beacon coincides with data staging/exfil.

**Containment (confirm before destructive actions).** Sinkhole/block the C2 domains, IPs, and DGA patterns at DNS + firewall + proxy. Isolate beaconing hosts via EDR (preserve memory for implant extraction). Kill + quarantine the implant process and remove its persistence. Block the implant hash fleet-wide. Reset credentials used on the host. Confirm before blocking a domain that could be a shared CDN/front used legitimately — scope to the specific indicator where possible.

**Evidence to collect.** PCAP/netflow showing the beacon interval, destination IOCs + JA3/SNI, implant binary + hash + memory image, originating process tree, persistence artifacts, first-seen timestamp, list of all beaconing hosts.

**Verdict criteria.**
- **True positive:** regular-interval low-jitter callbacks to rare/newly-registered/known-bad infra + an unsigned or injected calling process + encrypted/obfuscated payload or DNS tunneling. 
- **False positive / benign:** software update checks, telemetry/analytics SDKs, CDN keep-alives, and monitoring agents all beacon regularly — verify the destination is a known vendor and the process is a signed, expected application. NTP, certificate-OCSP, and push-notification services are benign periodic traffic. Correlate with pb-lateral-movement and pb-data-exfiltration once confirmed.
