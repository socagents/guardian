---
id: pb-cryptomining
title: "Playbook: Unauthorized Cryptomining (Cryptojacking)"
category: playbook
tags:
  - impact
  - cryptomining
  - cryptojacking
  - resource-hijacking
  - mining-pool
  - T1496
  - T1059
  - T1543
  - T1053
  - T1610
---

# Playbook: Unauthorized Cryptomining (Cryptojacking)

**When to use.** Sustained high CPU/GPU on a host or container, connections to known mining-pool domains/ports (e.g., stratum), XMRig/miner-binary signatures, anomalous cloud-compute spend spikes, or unexplained new compute instances. Maps to T1496 (Resource Hijacking), T1059 (Command/Scripting), T1543 (Create/Modify System Process), T1053 (Scheduled Task/Cron), T1610 (Deploy Container).

**Triage (priority order).**
1. Confirm the mining process: binary name/hash, command line (look for pool URL, wallet address, worker name), CPU/GPU usage, and parent process.
2. Identify the mining-pool destination and the wallet address (the wallet is a strong campaign pivot/IOC).
3. Establish persistence: cron/scheduled task, service, run-key, or container/Kubernetes deployment.
4. Determine entry vector — exposed service/exploit, web-shell, compromised credential, exposed cloud API/IAM key, or malicious container image.

**Scope / blast-radius.** Pivot on the wallet address, pool domain, and miner hash across the fleet/cloud account — miners are deployed at scale by automated campaigns. Enumerate every host/container/instance running the miner. In cloud, check for IAM-key abuse spawning new instances (cost-driven blast radius) and whether the key can spin up more. Although cryptomining is the *visible* payload, treat the underlying access as a full compromise — the same foothold can be repurposed. Identify the initial-access path and any additional implants.

**Containment (confirm before destructive actions).** Block the mining-pool domains/IPs and stratum ports at the firewall. Kill + quarantine the miner process and remove its persistence (cron/service/run-key). Block the miner hash fleet-wide. For cloud: revoke the abused IAM key/credential, terminate attacker-spawned instances, and tighten the exposed API/security group. Remediate the entry vector (patch/close the exposed service). Confirm before terminating cloud instances that may hold legitimate workloads. Because the foothold may host more than mining, rebuild compromised hosts from clean images.

**Evidence to collect.** Miner binary + hash, command line with pool URL + wallet, pool destination IOCs, persistence artifacts, resource-usage timeline, entry-vector logs, cloud audit trail (instance creation, IAM-key usage), list of affected hosts/instances.

**Verdict criteria.**
- **True positive:** unauthorized miner binary + connection to a mining pool + wallet/worker in the command line + persistence, plus an identifiable unauthorized entry vector. Cloud cost spikes from attacker-spawned instances confirm impact.
- **False positive / benign:** sanctioned blockchain/mining workloads (verify with the owner), or legitimate compute-heavy jobs (rendering, ML training, builds) misread as mining — confirm there is no pool connection or wallet before escalating. High CPU alone is not cryptojacking; the pool + wallet signature is the differentiator.
