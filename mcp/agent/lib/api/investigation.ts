/**
 * Investigation API client — Issues + Cases (v0.1.3).
 *
 * Thin typed wrappers over the /api/agent/issues|cases proxy routes (which
 * forward to the embedded MCP's /api/v1/issues|cases). Shared by the
 * Investigation UI pages so types + fetch shapes stay in one place.
 */

export type IssueStatus = "open" | "investigating" | "resolved" | "closed";
export type IssueSeverity = "low" | "medium" | "high" | "critical";

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
  created_at: string;
  updated_at: string;
  issue_count?: number;
}

export interface IssueDetail extends Issue {
  events: IssueEvent[];
  case: CaseRow | null;
}

export interface CaseDetail extends CaseRow {
  issues: Issue[];
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
