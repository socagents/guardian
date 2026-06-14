---
id: pb-phishing
title: "Playbook: Phishing / Suspicious Email Investigation"
category: playbook
tags:
  - initial-access
  - phishing
  - credential-harvest
  - email
  - T1566
  - T1566.001
  - T1566.002
  - T1204
---

# Playbook: Phishing / Suspicious Email Investigation

**When to use.** A user-reported suspicious email, a secure-email-gateway (SEG) detonation verdict, a URL/attachment sandbox hit, or an EDR alert tracing execution back to an email-delivered file. Maps to T1566 (Phishing), T1566.001 (attachment), T1566.002 (link), T1204 (User Execution).

**Triage (priority order).**
1. Pull the full email: sender (envelope-from vs header-from), reply-to, subject, SPF/DKIM/DMARC result, originating IP/ASN, and any URL/attachment.
2. Did the user *interact*? Click, credential entry, or attachment open. Query proxy/DNS logs for the URL and EDR for child processes of the mail client / Office apps.
3. Detonate the URL/attachment in a sandbox if not already done; extract IOCs (final-landing domain, dropped hashes, C2).
4. Reputation-check sender domain age, URL category, and file hashes against threat intel.

**Scope / blast-radius.** Search the mail platform for all recipients of the same campaign (sender, subject, URL pattern, attachment hash) — phishing is rarely singular. For each recipient, check who clicked (proxy logs), who submitted credentials (look for the landing page in web logs), and whether any session/MFA token was issued afterward. Pivot on the credential-harvest domain across all users.

**Containment (confirm before destructive actions).** Quarantine/purge the message tenant-wide (e.g., soft-delete + block sender). Block the URL/domain/IP at proxy and DNS sinkhole. Block the attachment hash at EDR. For confirmed credential entry: force password reset + revoke active sessions/refresh tokens + re-enroll MFA. Isolate the host if the attachment executed payload. Confirm purge scope with the operator before bulk-deleting mail.

**Evidence to collect.** Original .eml with full headers, sandbox report, proxy/DNS hits per user, list of recipients + clickers + credential-submitters, IOC set (domains, IPs, hashes), and the screenshot of the phishing landing page.

**Verdict criteria.**
- **True positive:** failed/forged DMARC + newly registered look-alike domain + credential-harvest landing page or malicious payload + at least one user interaction. Confirmed cred entry or payload execution escalates to incident.
- **False positive / benign:** legitimate bulk-mail or marketing sender, valid SPF/DKIM/DMARC, known-good domain, no payload and no credential form. Internal phishing-simulation campaigns (check the known training sender/tag) are benign — close with a note.
When interaction occurred but verdict is unclear, treat as suspected-compromise and pivot to pb-credential-access.
