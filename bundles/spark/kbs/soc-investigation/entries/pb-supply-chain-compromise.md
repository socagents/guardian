---
id: pb-supply-chain-compromise
title: "Playbook: Supply-Chain / Trusted-Software Compromise"
category: playbook
tags:
  - initial-access
  - supply-chain
  - software-update
  - signed-binary
  - ci-cd
  - T1195
  - T1195.001
  - T1195.002
  - T1199
  - T1554
---

# Playbook: Supply-Chain / Trusted-Software Compromise

**When to use.** A trusted/signed application or update begins exhibiting malicious behavior, a vendor advisory of a compromised release, a poisoned dependency/package alert, anomalous activity from a managed software-distribution or CI/CD system, or IOCs matching a known supply-chain campaign. Maps to T1195 (Supply Chain Compromise) incl. .001 dev-tools / .002 software-supply, T1199 (Trusted Relationship), T1554 (Compromise Host Software Binary).

**Triage (priority order).**
1. Identify the affected component: vendor, product, exact version/build, hash, and signing cert. Confirm against the vendor's known-bad version list.
2. Determine the behavior — what does the trojanized component do (beacon, drop payload, harvest creds)? Pull its process tree and network activity.
3. Establish the distribution path: how did it land (auto-update, package manager, MSP/RMM tool, CI artifact)?
4. Check whether the malicious functionality has activated (many supply-chain implants dwell/check-in before second-stage).

**Scope / blast-radius.** This is inherently fleet-wide — inventory EVERY host/build with the affected version/hash across the estate (the trusted component is everywhere it's deployed). Identify which instances actually executed the malicious second stage vs. merely have it installed. For compromised CI/CD or dev tooling, scope to every artifact built/signed in the compromised window. For a trusted-relationship (MSP/vendor) compromise, scope to all access that partner holds. Check downstream — did you redistribute the artifact?

**Containment (confirm before destructive actions).** Block the malicious version's hash + its C2 IOCs fleet-wide. Halt the update channel / pin to a known-good version. Quarantine actively-beaconing hosts. Rotate any secrets the compromised component could access (CI signing keys, API tokens, service creds). For MSP/vendor compromise, suspend that trust relationship's access pending review. Confirm before mass-blocking a business-critical signed application; stage rollback to the last-good version. Rebuild from clean sources where second-stage executed.

**Evidence to collect.** Affected version/hash/cert, vendor advisory reference, distribution mechanism, list of all hosts with the version + subset that executed second stage, C2 IOCs, CI/CD audit logs, secrets potentially exposed.

**Verdict criteria.**
- **True positive:** a legitimately-signed/trusted component matching a vendor-confirmed compromised build (hash match) exhibiting unexpected network/host behavior, present across many hosts via the normal trusted channel.
- **False positive / benign:** a normal new vendor release flagged by heuristic anomaly detection, or a legitimate behavior change documented in vendor release notes. Verify the hash against the vendor's published good hashes before declaring compromise. A single mismatched hash from a mirror may be a benign repackage — confirm with the vendor.
