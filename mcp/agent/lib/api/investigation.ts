/**
 * Investigation API client — Issues + Cases (v0.1.3).
 *
 * Thin typed wrappers over the /api/agent/issues|cases proxy routes (which
 * forward to the embedded MCP's /api/v1/issues|cases). Shared by the
 * Investigation UI pages so types + fetch shapes stay in one place.
 */

export type IssueStatus = "open" | "investigating" | "resolved" | "closed";
export type IssueSeverity = "low" | "medium" | "high" | "critical";

/** v0.2.45 — the closed enum of structured verdicts (mirrors ISSUE_VERDICTS). */
export type IssueVerdict =
  | "TRUE_POSITIVE"
  | "FALSE_POSITIVE"
  | "BENIGN"
  | "NEEDS_ESCALATION"
  | "INCONCLUSIVE";

/** v0.2.45 — an ATT&CK technique observed in an issue (mirrors TechniqueMapping). */
export interface TechniqueMapping {
  id: string;
  issue_id: string;
  technique_id: string;
  tactic: string | null;
  manifestation: string | null;
  evidence_ref: string | null;
  confidence: number | null;
  created_at: string;
}

export interface Issue {
  id: string;
  title: string;
  status: IssueStatus;
  severity: IssueSeverity;
  kind: string;
  origin: "agent" | "operator";
  source_ref: string | null;
  case_id: string | null;
  summary: string | null;
  scope: string | null;
  recommendations: string | null;
  conclusions: string | null;
  next_steps: string | null;
  /** v0.2.45 — structured verdict enum (null until the agent calls issue_set_verdict). */
  verdict: IssueVerdict | null;
  /** v0.2.45 — 0..1 confidence the agent attaches to the verdict. */
  verdict_confidence: number | null;
  /** v0.2.45 — JSON-encoded blast-radius object, e.g. {"hosts":[…],"accounts":[…]}. */
  blast_radius: string | null;
  created_at: string;
  updated_at: string;
}

export interface IssueEvent {
  id: string;
  issue_id: string;
  ts: string;
  type: string;
  content: string;
}

export interface CaseRow {
  id: string;
  title: string;
  description: string | null;
  status: string;
  /** v0.2.47 (stage C) — campaign rollup, synthesized by case_rollup from member
   *  issues. infrastructure + techniques are JSON strings; null until rolled up. */
  campaign_summary: string | null;
  threat_actor: string | null;
  infrastructure: string | null;
  techniques: string | null;
  severity_rollup: string | null;
  created_at: string;
  updated_at: string;
  issue_count?: number;
}

/** v0.2.47 (stage C) — a typed cross-case edge, with the other case resolved. */
export interface CaseRelationshipEdge {
  relationship_type: string;
  note: string | null;
  direction: "outgoing" | "incoming";
  other_case: { id: string; title: string | null; status: string | null } | null;
}

/** v0.2.47 (stage C) — a KB playbook an investigation was routed through. */
export interface PlaybookMatch {
  id: string;
  issue_id: string;
  playbook_doc_id: string;
  score: number | null;
  matched_criteria: string | null;
  created_at: string;
}

export interface IssueDetail extends Issue {
  events: IssueEvent[];
  case: CaseRow | null;
  /** v0.1.8 — self-contained SVG attack chain (null until the agent draws one).
   *  Rendered sandboxed as an <img> data-URI on the Attack-chain tab. */
  attack_chain_svg: string | null;
  /** v0.2.1 — self-contained SVG STIX relations canvas (null until drawn).
   *  Rendered sandboxed as an <img> data-URI on the Relations tab. */
  relations_canvas_svg: string | null;
  /** v0.2.45 — agent-generated investigation report (markdown), null until
   *  generate_investigation_report runs. Detail-only (dropped from list payload). */
  report: string | null;
  /** v0.2.45 — ATT&CK techniques mapped to this issue (empty until mapped). */
  techniques: TechniqueMapping[];
  /** v0.2.47 — KB playbooks this investigation was routed through. */
  playbook_matches: PlaybookMatch[];
}

/** v0.2.1 — a STIX-style relationship edge (source indicator → target entity). */
export interface Relationship {
  id: string;
  source_id: string;
  source_type: string;
  target_value: string;
  target_type: string;
  relationship_type: string; // STIX verb: resolves-to, indicates, attributed-to, uses, …
  description: string | null;
  source: string; // "guardian" | "xsoar"
  first_seen: string;
  last_seen: string;
}

export interface CaseDetail extends CaseRow {
  issues: Issue[];
  /** v0.2.47 (stage C) — typed cross-case edges touching this case. */
  related: CaseRelationshipEdge[];
  /** v0.2.2 — campaign-level diagram SVGs synthesized across the case's
   *  issues (null until the agent draws them). Rendered sandboxed on the
   *  case detail's Attack-chain / Relations tabs. */
  attack_chain_svg: string | null;
  relations_canvas_svg: string | null;
}

async function jsonOrThrow(resp: Response) {
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`HTTP ${resp.status}: ${text.slice(0, 200)}`);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

// ── Issues ──────────────────────────────────────────────────────────

export async function listIssues(params?: {
  status?: string;
  case_id?: string;
}): Promise<{ issues: Issue[]; count: number }> {
  const q = new URLSearchParams();
  if (params?.status) q.set("status", params.status);
  if (params?.case_id) q.set("case_id", params.case_id);
  const qs = q.toString() ? `?${q}` : "";
  return jsonOrThrow(await fetch(`/api/agent/issues${qs}`, { cache: "no-store" }));
}

export async function getIssue(id: string): Promise<IssueDetail> {
  return jsonOrThrow(await fetch(`/api/agent/issues/${id}`, { cache: "no-store" }));
}

export async function createIssue(body: {
  title: string;
  kind?: string;
  severity?: string;
  source_ref?: string;
  scope?: string;
  summary?: string;
}): Promise<Issue> {
  return jsonOrThrow(
    await fetch("/api/agent/issues", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export async function updateIssue(
  id: string,
  body: Partial<Pick<Issue, "title" | "status" | "severity" | "kind" | "summary" | "scope" | "recommendations" | "conclusions" | "next_steps">>,
): Promise<Issue> {
  return jsonOrThrow(
    await fetch(`/api/agent/issues/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export async function deleteIssue(id: string): Promise<void> {
  await jsonOrThrow(await fetch(`/api/agent/issues/${id}`, { method: "DELETE" }));
}

export async function addIssueEvent(
  id: string,
  body: { type: string; content: string },
): Promise<IssueEvent> {
  return jsonOrThrow(
    await fetch(`/api/agent/issues/${id}/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

// ── Cases ───────────────────────────────────────────────────────────

export async function listCases(): Promise<{ cases: CaseRow[]; count: number }> {
  return jsonOrThrow(await fetch("/api/agent/cases", { cache: "no-store" }));
}

export async function getCase(id: string): Promise<CaseDetail> {
  return jsonOrThrow(await fetch(`/api/agent/cases/${id}`, { cache: "no-store" }));
}

export async function createCase(body: {
  title: string;
  description?: string;
}): Promise<CaseRow> {
  return jsonOrThrow(
    await fetch("/api/agent/cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export async function addIssueToCase(caseId: string, issueId: string): Promise<Issue> {
  return jsonOrThrow(
    await fetch(`/api/agent/cases/${caseId}/issues`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ issue_id: issueId }),
    }),
  );
}

// ── UI helpers ──────────────────────────────────────────────────────

export const SEVERITY_TOKENS: Record<string, string> = {
  critical: "text-error border-error/40 bg-error/10",
  high: "text-tertiary border-tertiary/40 bg-tertiary/10",
  medium: "text-primary border-primary/40 bg-primary/10",
  low: "text-on-surface-variant border-outline-variant bg-surface-container-high",
};

export const STATUS_TOKENS: Record<string, string> = {
  open: "text-primary border-primary/40 bg-primary/10",
  investigating: "text-tertiary border-tertiary/40 bg-tertiary/10",
  resolved: "text-on-surface-variant border-outline-variant bg-surface-container-high",
  closed: "text-on-surface-variant border-outline-variant bg-surface-container-high",
};

export const KIND_LABELS: Record<string, string> = {
  phishing: "Phishing",
  lateral_movement: "Lateral movement",
  access_violation: "Access violation",
  malware: "Malware",
  other: "Other",
};

export function kindLabel(k: string): string {
  return KIND_LABELS[k] ?? k;
}

// ── Indicators (IoCs) — v0.2.0 ──────────────────────────────────────

export interface Indicator {
  id: string;
  value: string;
  type: string;
  dbot_score: number | null;
  enrichment: string | null; // JSON string
  source: string; // "guardian" | "xsoar"
  first_seen: string;
  last_seen: string;
  created_at: string;
  updated_at: string;
  issue_count?: number;
}

export interface IndicatorIssueRef {
  id: string;
  title: string;
  kind: string;
  status: string;
  source_ref: string | null;
}

export interface IndicatorDetail extends Indicator {
  issues: IndicatorIssueRef[];
  /** v0.2.1 — STIX edges from this indicator to other entities. The REST
   *  endpoint always populates this (possibly empty), so it is non-optional. */
  relationships: Relationship[];
}

export async function listIndicators(params?: {
  type?: string;
  issue_id?: string;
}): Promise<{ indicators: Indicator[]; count: number }> {
  const q = new URLSearchParams();
  if (params?.type) q.set("type", params.type);
  if (params?.issue_id) q.set("issue_id", params.issue_id);
  const qs = q.toString() ? `?${q}` : "";
  return jsonOrThrow(await fetch(`/api/agent/indicators${qs}`, { cache: "no-store" }));
}

export async function getIndicator(id: string): Promise<IndicatorDetail> {
  return jsonOrThrow(await fetch(`/api/agent/indicators/${id}`, { cache: "no-store" }));
}

export const INDICATOR_TYPE_ICON: Record<string, string> = {
  ip: "lan",
  domain: "language",
  url: "link",
  file_hash: "fingerprint",
  email: "mail",
  cve: "gpp_maybe",
  host: "computer",
  account: "person",
};

export const INDICATOR_TYPE_LABELS: Record<string, string> = {
  ip: "IP",
  domain: "Domain",
  url: "URL",
  file_hash: "File hash",
  email: "Email",
  cve: "CVE",
  host: "Host",
  account: "Account",
};

export function indicatorTypeLabel(t: string): string {
  return INDICATOR_TYPE_LABELS[t] ?? t;
}

// ── Relationships (STIX edges) — v0.2.1 ─────────────────────────────

/** STIX SDO type → Material Symbol icon (for the target node of an edge). */
export const RELATION_TARGET_ICON: Record<string, string> = {
  indicator: "tag",
  "attack-pattern": "swords", // MITRE ATT&CK technique
  malware: "coronavirus",
  tool: "build",
  campaign: "campaign",
  "intrusion-set": "groups",
  "threat-actor": "skull",
  vulnerability: "gpp_maybe",
  identity: "badge",
};

export const RELATION_TARGET_LABELS: Record<string, string> = {
  indicator: "Indicator",
  "attack-pattern": "Technique",
  malware: "Malware",
  tool: "Tool",
  campaign: "Campaign",
  "intrusion-set": "Intrusion set",
  "threat-actor": "Threat actor",
  vulnerability: "Vulnerability",
  identity: "Identity",
};

export function relationTargetIcon(t: string): string {
  return RELATION_TARGET_ICON[t] ?? "hub";
}

export function relationTargetLabel(t: string): string {
  return RELATION_TARGET_LABELS[t] ?? t;
}

/** STIX verb → tone. Attribution verbs read stronger than plain associations. */
export function relationVerbTone(verb: string): string {
  if (verb === "attributed-to" || verb === "indicates")
    return "text-tertiary border-tertiary/40 bg-tertiary/10";
  if (verb === "uses" || verb === "drops" || verb === "downloads" || verb === "beacons-to")
    return "text-primary border-primary/40 bg-primary/10";
  return "text-on-surface-variant border-outline-variant bg-surface-container-high";
}

/** DBotScore → (label, Material-3 token classes). 0 unknown · 1 good · 2 suspicious · 3 bad. */
export function dbotMeta(score: number | null | undefined): { label: string; tone: string } {
  switch (score) {
    case 3:
      return { label: "Malicious", tone: "text-error border-error/40 bg-error/10" };
    case 2:
      return { label: "Suspicious", tone: "text-tertiary border-tertiary/40 bg-tertiary/10" };
    case 1:
      return { label: "Good", tone: "text-secondary border-secondary/40 bg-secondary/10" };
    default:
      return { label: "Unknown", tone: "text-on-surface-variant border-outline-variant bg-surface-container-high" };
  }
}
