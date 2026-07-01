"use client";

/**
 * /help/user — operator-focused user guide.
 *
 * Companion to /help/architecture. Operators driving Guardian land here
 * for surface walks; architects extending Guardian go to /help/architecture
 * for the system-internals view. The split keeps each guide useful to
 * its audience without bloating either:
 *
 *   /help                — landing with two cards (User / Architecture)
 *   /help/user           — THIS page; daily-driver operator tasks only
 *   /help/architecture   — system-internals reference for architects
 *
 * What lives here: how to use each operator surface, common workflows,
 * slash commands, hook installation, plan mode, cost reading, plugin
 * install, agents page, connector reauth, troubleshooting decision tree.
 *
 * What lives in /help/architecture: service-stack topology, MCP
 * tool-registration internals, bundle layout, audit-row schema, REST
 * endpoint reference, the chat-route lifecycle, every subsystem&apos;s
 * implementation pattern, design decisions.
 *
 * Specialty pages live underneath:
 *   /help/journeys      — task-oriented walkthroughs
 *   /help/journeys/[id] — single journey detail
 *   /help/api           — REST endpoint reference
 *   /help/api/[id]      — single endpoint detail
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import {
  AuthLoginFlow,
  AuthChangePasswordFlow,
  AuthCliResetFlow,
} from "@/components/diagrams/auth-flows";
import { OperatorDailyLoop } from "@/components/diagrams/operator-daily-loop";

interface SectionDef {
  id: string;
  label: string;
  group: string;
  icon: string;
}

const SECTIONS: SectionDef[] = [
  { id: "overview", label: "What Guardian is", group: "Welcome", icon: "explore" },
  { id: "daily-workflow", label: "Daily Workflow", group: "Welcome", icon: "loop" },
  { id: "authentication", label: "Authentication", group: "Welcome", icon: "lock_person" },
  { id: "profile", label: "Your Profile", group: "Welcome", icon: "person" },
  { id: "upgrades", label: "Upgrading Guardian", group: "Welcome", icon: "system_update" },
  { id: "ui-tour", label: "Operator UI Tour", group: "Welcome", icon: "tour" },

  { id: "chat", label: "Chat", group: "Command", icon: "chat_bubble" },
  { id: "slash-commands", label: "Slash Commands", group: "Command", icon: "terminal" },
  { id: "plan-mode-ux", label: "Plan Mode", group: "Command", icon: "checklist" },
  { id: "tasks-ux", label: "Tasks", group: "Command", icon: "task_alt" },
  { id: "skills", label: "Skills", group: "Command", icon: "auto_awesome" },
  { id: "agents-ux", label: "Agents", group: "Command", icon: "smart_toy" },
  { id: "memory", label: "Memory", group: "Command", icon: "database" },
  { id: "knowledge", label: "Knowledge Bases", group: "Command", icon: "menu_book" },
  { id: "playbook-builder", label: "Playbook Builder", group: "Command", icon: "design_services" },
  { id: "jobs", label: "Jobs", group: "Command", icon: "schedule" },
  { id: "models-providers", label: "Models & Providers", group: "Command", icon: "psychology" },

  { id: "investigation", label: "Investigation — Issues & Cases", group: "Integration", icon: "frame_inspect" },
  { id: "connectors", label: "Connectors & Instances", group: "Integration", icon: "cable" },
  { id: "connector-health-ux", label: "Connector Health", group: "Integration", icon: "monitor_heart" },
  { id: "marketplace", label: "Marketplace", group: "Integration", icon: "storefront" },
  { id: "plugins-ux", label: "Plugins", group: "Integration", icon: "extension" },
  { id: "hooks-ux", label: "Hooks", group: "Integration", icon: "webhook" },
  { id: "approvals", label: "Approvals", group: "Integration", icon: "fact_check" },
  { id: "notifications", label: "Notifications", group: "Integration", icon: "notifications" },
  { id: "api-keys", label: "API Keys", group: "Integration", icon: "vpn_key" },

  { id: "obs-pipeline", label: "Pipeline Health", group: "Observability", icon: "account_tree" },
  { id: "obs-xsoar", label: "XSOAR Operational Metrics", group: "Observability", icon: "security" },
  { id: "obs-metrics", label: "Metrics & Traces", group: "Observability", icon: "monitoring" },
  { id: "obs-logs", label: "Logs & Events", group: "Observability", icon: "terminal" },
  { id: "cost-ux", label: "Cost Rollup", group: "Observability", icon: "payments" },
  { id: "telemetry-ux", label: "Telemetry", group: "Observability", icon: "insights" },
  { id: "obs-activity", label: "Live Activity", group: "Observability", icon: "history_toggle_off" },

  { id: "settings-services", label: "Services", group: "Settings", icon: "tune" },
  { id: "settings-personality", label: "Personality", group: "Settings", icon: "psychology_alt" },
  { id: "backup-restore", label: "Backup & Restore", group: "Settings", icon: "save" },
  { id: "settings-precedence", label: "Where Settings Live", group: "Settings", icon: "layers" },

  { id: "troubleshoot", label: "Where to Look When…", group: "Troubleshooting", icon: "support" },

  { id: "ref-architecture", label: "Architecture Guide", group: "References", icon: "schema" },
  { id: "ref-journeys", label: "User Journeys", group: "References", icon: "tour" },
  { id: "ref-api", label: "REST API", group: "References", icon: "api" },
];

const GROUP_ORDER = [
  "Welcome",
  "Command",
  "Integration",
  "Observability",
  "Settings",
  "Troubleshooting",
  "References",
] as const;

const glassStyle = {
  background: "var(--glass-bg-strong)",
  backdropFilter: "blur(12px)",
  border: "0.5px solid var(--glass-border)",
} as const;

export default function HelpPage() {
  const [active, setActive] = useState<string>(SECTIONS[0]?.id ?? "");
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const visible = new Map<string, number>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            visible.set(e.target.id, e.intersectionRatio);
          } else {
            visible.delete(e.target.id);
          }
        }
        let chosen: string | null = null;
        for (const s of SECTIONS) {
          if (visible.has(s.id)) {
            chosen = s.id;
            break;
          }
        }
        if (chosen) setActive(chosen);
      },
      {
        rootMargin: "-20% 0px -60% 0px",
        threshold: [0, 0.25, 0.5, 1],
      },
    );

    for (const s of SECTIONS) {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, []);

  function handleNavClick(id: string) {
    const el = document.getElementById(id);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    setActive(id);
  }

  // Section nav collapses INDEPENDENTLY of route navigation.
  // Same shape as the architecture page's collapse toggle. Operators
  // who want more horizontal room get it without losing their place.
  // Persisted in localStorage so the preference survives page reloads.
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(
        "guardian.help.user.sidebar-collapsed",
      );
      if (stored === "true") setSidebarCollapsed(true);
    } catch {
      // localStorage unavailable — accept default (expanded)
    }
  }, []);
  useEffect(() => {
    try {
      window.localStorage.setItem(
        "guardian.help.user.sidebar-collapsed",
        sidebarCollapsed ? "true" : "false",
      );
    } catch {
      // silent skip
    }
  }, [sidebarCollapsed]);

  return (
    <div className="h-screen overflow-hidden flex">
      {/* ── Left rail: sticky table of contents (expanded) ───── */}
      {!sidebarCollapsed && (
        <aside
          className="hidden lg:block w-80 shrink-0 border-r border-outline-variant/20 overflow-y-auto custom-scrollbar"
          aria-label="Help navigation"
        >
          <div className="p-6 sticky top-0">
            <div className="flex items-center justify-between gap-2 mb-1">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-2xl text-primary">
                  help_outline
                </span>
                <h2 className="font-headline text-xl font-bold tracking-tight text-on-surface">
                  Help
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setSidebarCollapsed(true)}
                className="w-7 h-7 flex items-center justify-center rounded-md text-on-surface-variant/70 hover:text-on-surface hover:bg-white/5 transition-colors"
                aria-label="Collapse section navigation"
                title="Collapse navigation (stays on this page)"
              >
                <span className="material-symbols-outlined text-lg">
                  chevron_left
                </span>
              </button>
            </div>
            <p className="text-sm text-on-surface-variant/80 mb-5 leading-relaxed">
              Operator guide to every Guardian capability. Click a section to
              jump.
            </p>

            <nav className="space-y-5">
              {GROUP_ORDER.map((group) => {
                const items = SECTIONS.filter((s) => s.group === group);
                if (items.length === 0) return null;
                return (
                  <div key={group}>
                    <div className="text-xs font-bold uppercase tracking-widest text-on-surface-variant/70 mb-2 px-2">
                      {group}
                    </div>
                    <div className="space-y-0.5">
                      {items.map((s) => {
                        const isActive = active === s.id;
                        return (
                          <button
                            key={s.id}
                            type="button"
                            onClick={() => handleNavClick(s.id)}
                            className={
                              "w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-sm text-left transition-colors " +
                              (isActive
                                ? "bg-secondary-container/30 text-secondary font-semibold"
                                : "text-on-surface-variant hover:bg-surface-container-low/50 hover:text-on-surface")
                            }
                            aria-current={isActive ? "true" : undefined}
                          >
                            <span className="material-symbols-outlined text-base">
                              {s.icon}
                            </span>
                            <span className="truncate">{s.label}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </nav>
          </div>
        </aside>
      )}

      {/* ── Left rail: collapsed mini-rail ────────────────────── */}
      {sidebarCollapsed && (
        <aside
          className="hidden lg:flex w-10 shrink-0 flex-col items-center pt-5 border-r border-outline-variant/20"
          aria-label="Help navigation (collapsed)"
        >
          <button
            type="button"
            onClick={() => setSidebarCollapsed(false)}
            className="w-7 h-7 flex items-center justify-center rounded-md text-on-surface-variant/70 hover:text-on-surface hover:bg-white/5 transition-colors"
            aria-label="Expand section navigation"
            title="Expand navigation"
          >
            <span className="material-symbols-outlined text-lg">
              chevron_right
            </span>
          </button>
        </aside>
      )}

      {/* ── Main content
          Content uses the full viewport width up to a 1400px ceiling
          (typography is still readable at that width because the
          inner reading-flow elements wrap naturally; pre-formatted
          blocks scroll inside their own boxes). Body text uses
          text-base for the same readability reasons. */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto custom-scrollbar text-base"
      >
        <div className="px-10 py-12 pb-32 space-y-16 max-w-[1400px]">
          {/* Header */}
          <header>
            <div className="flex items-center gap-3 mb-2">
              <span className="material-symbols-outlined text-3xl text-primary">
                menu_book
              </span>
              <h1 className="font-headline text-4xl font-bold tracking-tight text-on-surface">
                User Guide
              </h1>
            </div>
            <p className="text-base text-on-surface-variant leading-relaxed">
              Guardian is an AI incident-investigation agent for Cortex
              XSOAR: it monitors cases (incidents) on your XSOAR tenant,
              fetches their data, summarizes and investigates, enriches
              indicators, documents findings, and updates or closes the
              case — through an AI agent surface. This guide
              walks every operator surface end-to-end — what it does,
              where it lives in the UI, and how to drive it day-to-day.
            </p>
            <div
              className="mt-4 rounded-xl p-4 flex items-start gap-3"
              style={glassStyle}
            >
              <span className="material-symbols-outlined text-base text-tertiary shrink-0 mt-0.5">
                schema
              </span>
              <div className="text-sm text-on-surface leading-relaxed flex-1">
                <span className="font-semibold">Looking for technical
                depth?</span>{" "}
                The service stack, boot lifecycle, chat-route
                pipeline, every subsystem&apos;s implementation
                (memory, knowledge, skills, hooks, tasks, plan mode,
                subagents, plugins, jobs, notifications, approvals,
                models, providers, secret store, audit log), and the
                three external connectors (XSOAR / Cortex Docs / Web Browser)
                live in the dedicated{" "}
                <Link
                  href="/help/architecture"
                  className="text-primary hover:underline font-semibold"
                >
                  Architecture Guide
                </Link>
                . This page focuses on operator tasks.
              </div>
            </div>
          </header>

          {/* ============================================================
                                   WELCOME
              ============================================================ */}

          <Section id="overview" icon="explore" title="What Guardian is">
            <p>
              Guardian packages an AI incident-response agent into a
              Docker Compose stack: the agent container (Next.js UI +
              embedded MCP server), a headless-browser sidecar, the
              guardian-updater lifecycle daemon, and one container per
              connector instance. The agent is the human-facing surface
              — a UI where you chat, run jobs, configure connectors,
              and watch telemetry. Behind it sits an MCP server that
              aggregates tools from four connectors:{" "}
              <Term>xsoar</Term> for Cortex XSOAR cases (list / fetch /
              war room / indicators / notes / evidence / update / close),{" "}
              <Term>xsiam</Term> for Cortex XSIAM (XQL hunts, incidents /
              alerts / assets, and EDR response — endpoint isolate / scan /
              quarantine),{" "}
              <Term>cortex-docs</Term> for official Palo Alto Networks
              documentation search, and <Term>web</Term>{" "}
              for evidence-gathering browsing via the browser sidecar.
            </p>
            <p>
              The intended workflow is: a case (incident) opens on your
              Cortex XSOAR tenant → ask the agent to investigate → it
              fetches the case + war room, researches the unknowns in the
              docs and on the web, enriches the indicators → documents its
              findings on the case and updates or closes it → you review.
              The agent orchestrates all of that through natural-language
              chat plus optional scheduled jobs. You don&apos;t need API
              scripting to drive an investigation end-to-end.
            </p>
            <p>
              Who&apos;s it for? <Term>SOC tier-1 / tier-2 analysts</Term>{" "}
              who want investigation legwork — case reads, indicator
              enrichment, documentation — handled conversationally.{" "}
              <Term>Incident responders</Term> who need fast, repeatable
              access to case context on the XSOAR tenant.{" "}
              <Term>SOC leads</Term> who want a low-friction
              path from &ldquo;a case just opened&rdquo; to a documented,
              resolved incident.
            </p>
            <p>
              What it&apos;s not: a SIEM (it queries your Cortex tenant,
              it doesn&apos;t ingest telemetry itself); an autonomous
              responder (destructive actions gate behind operator
              approval); or a turnkey MSSP (it requires an operator to
              direct the investigation). Think of it as the
              <em> tireless analyst</em> between your Cortex tenant and
              your response decisions.
            </p>
            <Callout tone="info">
              Guardian ships zero native tools — every capability comes from
              the bundled connectors or runtime built-ins (memory,
              sessions, knowledge search). That keeps the surface honest:
              what you see in <Link href="/skills" className="link">/skills</Link>{" "}
              is what the agent can actually do.
            </Callout>
          </Section>

          <Section id="daily-workflow" icon="loop" title="Your Daily Workflow">
            <p>
              Three surfaces handle most of what you do day-to-day. The
              diagram below shows the typical loop and the side-branches
              that automate or gate parts of it.
            </p>

            <OperatorDailyLoop />

            <SubSection icon="chat_bubble" title="Chat — for ad-hoc work">
              <p>
                Type a request — &ldquo;pull the open high-severity cases
                from the last 24 hours&rdquo; or &ldquo;investigate
                incident 482 and document what you find&rdquo; — and the
                agent dispatches the right tool.
                For sensitive operations (creating jobs, rotating keys,
                deleting instances), an approval card appears inline; click
                Approve to unblock the call. Every chat session is
                browseable in the left sidebar; sessions persist for 30
                days.
              </p>
            </SubSection>

            <SubSection icon="schedule" title="Jobs — for scheduled work">
              <p>
                A job has a name, a cron, an action (prompt / tool_call),
                and persists across restarts. Click a card to see its
                run history with the model&apos;s reply for prompt actions or
                the tool result for tool_call. Two creation paths: declared
                in <Code>manifest.yaml:jobs[]</Code> (reconciled at boot,
                manifest is source of truth) or via the{" "}
                <Link href="/jobs/new" className="link">
                  Create Job form
                </Link>{" "}
                (operator-owned, survives boot).
              </p>
            </SubSection>

            <SubSection icon="monitoring" title="Observability — when something looks off">
              <p>
                Six surfaces share a unified Lucene-light query bar:{" "}
                <Term>Pipeline</Term> (component health graph),{" "}
                <Term>Events</Term> (paginated audit log), <Term>Logs</Term>{" "}
                (live SSE tail), <Term>Traces</Term> (span-flavored audit
                view), <Term>Metrics</Term> (Prometheus text), and{" "}
                <Term>Live Activity</Term> (streaming recent events). Every
                job card has icon buttons that deep-link with the right
                filter pre-applied.
              </p>
            </SubSection>

            <p className="pt-2">
              The loop in practice: a case lands in your Cortex tenant →
              switch to chat and ask the agent to investigate → watch the
              pipeline graph turn briefly amber as the connectors fire →
              check Events for the audit trail → review the evidence and
              decide the response → update the incident from the same
              thread. When you have a workflow that&apos;s working,
              promote it to a job for a recurring sweep.
            </p>
          </Section>

          <Section id="authentication" icon="lock_person" title="Authentication">
            <p>
              First boot drops you at a sign-in screen — no setup
              wizard, no questionnaire, just a username + password
              form. Sign in with the default credentials shown below,
              change them on first use, and you&apos;re in.
            </p>

            <SubSection icon="login" title="First-time login">
              <p>
                The installer auto-generates a random admin
                password per install and writes it to{" "}
                <Code>/opt/guardian/.env</Code> as{" "}
                <Code>GUARDIAN_DEFAULT_ADMIN_PASSWORD</Code>. No
                credential is baked into the guardian-agent image. You
                see the value in three places:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>The installer&apos;s &ldquo;First-time login&rdquo; banner at the end of <Code>sudo ./guardian-installer</Code>.</li>
                <li>Inside <Code>/opt/guardian/.env</Code> under <Code>GUARDIAN_DEFAULT_ADMIN_PASSWORD</Code> (mode 0600; root or installer-user only).</li>
                <li>Docker logs of the agent on the FIRST boot only — the entrypoint prints a credentials banner once when it seeds. Subsequent boots stay quiet (already-initialized branch).</li>
              </ul>
              <Pre>{`username:  admin
password:  <value of GUARDIAN_DEFAULT_ADMIN_PASSWORD from .env>`}</Pre>
              <p>
                Sign in. The UI will show a non-dismissible amber
                banner and auto-redirect you to <Code>/profile</Code>{" "}
                to change the password. You can&apos;t navigate
                anywhere else until you do. After you complete the
                change, the value in <Code>.env</Code> is never
                consulted again — your operator-set password lives
                in <Code>SecretStore</Code>, encrypted at rest with{" "}
                <Code>GUARDIAN_SECRET_KEK</Code>.
              </p>
              <p>
                If you lose the random value before completing the forced first-login change, run{" "}
                <Code>sudo /opt/guardian/guardian-reset-admin-password</Code> from the host to set a new one interactively.
              </p>
              <AuthLoginFlow />
            </SubSection>

            <SubSection icon="key" title="Authenticate with an API key">
              <p>
                For scripts, schedulers, CI, or any tool that drives the
                agent without a browser session, mint an{" "}
                <strong>API key</strong> instead of using your password.
                Go to <Code>/api-keys</Code>, click <strong>Create Key</strong>,
                pick a scope, and copy the key (shown once).
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>Send it as <Code>Authorization: Bearer guardian_ak_…</Code> to <Code>/api/chat</Code> or any <Code>/api/agent/*</Code> route.</li>
                <li>Scopes: <Code>agent:read</Code> (read-only), <Code>agent:write</Code> (includes running chat turns + mutations), <Code>agent:*</Code> (full non-credential access).</li>
                <li>Keys can never reach credential settings (providers, connector instances, API-key management) — those always require a logged-in session, so a leaked key stays bounded.</li>
                <li>Revoke any key instantly from <Code>/api-keys</Code>; it stops working within ~30 seconds.</li>
              </ul>
            </SubSection>

            <SubSection icon="lock_reset" title="Changing your password">
              <p>
                Go to <Code>/profile</Code> (linked in the sidebar
                under your username, or auto-redirected on first login).
                The form asks for your current password, new password,
                and confirm. Save:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>The server overwrites your password hash in the SecretStore (PBKDF2-HMAC-SHA256 at 600k iterations, encrypted at rest).</li>
                <li>All your active sessions are revoked server-side — including the one you used to make the change. Other tabs / devices sign out on their next API call.</li>
                <li>A security notification gets posted to <Code>/notifications</Code>: <em>&ldquo;Your password was changed at &lt;timestamp&gt;&rdquo;</em>. Canary if someone else ever changes it.</li>
                <li>You&apos;re force-logged-out and bounced back to the sign-in screen. Use your new password.</li>
              </ul>
              <p>
                The username (<Code>admin</Code>) is fixed.
                Share access via per-integration API keys minted at{" "}
                <Code>/api-keys</Code> — wired to the real MCP{" "}
                <Code>api_keys</Code> store, scoped by advisory
                scopes like <Code>audit:read</Code> or{" "}
                <Code>tools:call</Code>.
              </p>
              <AuthChangePasswordFlow />
            </SubSection>

            <SubSection icon="terminal" title="Forgot your password (host utility)">
              <p>
                If you can&apos;t log in (forgot the password, no
                browser session), reset from the host shell. No old
                password needed — the trust boundary is shell access
                to the machine running Guardian. A host script for
                this is installed at <Code>/opt/guardian/</Code>{" "}
                by every fresh installer run:
              </p>
              <Pre>{`# From the host running guardian-agent:
sudo /opt/guardian/guardian-reset-admin-password`}</Pre>
              <p>
                The wrapper validates the agent container is running,
                then exec-replaces itself with the in-container CLI.
                The CLI asks you to type <Code>RESET</Code> to confirm
                (prevents fat-finger triggers), then prompts for a new
                password twice. On success it tells you to restart the
                agent container so any in-memory caches get flushed:
              </p>
              <Pre>{`docker compose restart guardian-agent`}</Pre>
              <p>
                Then sign in with the new password as usual. The
                legacy invocation <Code>docker exec -it guardian_agent node /app/cli/reset-admin.mjs</Code>{" "}
                still works — the host script is just a thin wrapper
                around exactly that command. Use whichever is in your
                muscle memory.
              </p>
              <p className="text-sm text-on-surface-variant">
                <strong>Non-interactive mode (scripted /
                remote SSH / no-TTY contexts):</strong> the CLI accepts
                a <Code>--password-stdin --skip-confirm</Code> flag pair
                that reads the password from stdin and bypasses the
                <Code>RESET</Code> typo-prevention prompt — use it
                whenever stdin is piped (interactive readline prompts
                don&apos;t survive piped stdin):
              </p>
              <Pre>{`echo -n 'NewPassword' | docker exec -i guardian_agent \\
  node /app/cli/reset-admin.mjs --password-stdin --skip-confirm`}</Pre>
              <AuthCliResetFlow />
            </SubSection>

            <SubSection icon="restart_alt" title="Factory reset (host utility)">
              <p>
                If you want to start over from the customer-fresh
                shipped state — same blank-canvas Guardian a brand-new
                install boots into — use the factory-reset script.
                It&apos;s host-side by physical necessity (a container
                can&apos;t delete the docker volume it&apos;s mounting),
                ships in every install kit at{" "}
                <Code>/opt/guardian/</Code>, and asks for typed
                confirmation before wiping anything:
              </p>
              <Pre>{`# Show the plan without doing anything:
sudo /opt/guardian/guardian-factory-reset --dry-run

# Actually wipe + re-install:
sudo /opt/guardian/guardian-factory-reset

# Skip the 'Type FACTORY RESET' prompt (scripted use only):
sudo /opt/guardian/guardian-factory-reset --yes`}</Pre>
              <p>
                What gets wiped: every <Code>guardian_*</Code> docker
                volume (memories, instances + their secrets, API keys,
                audit log, sessions, jobs, notifications, journey-tested
                marks, metrics bookmarks, TLS certs, skills volume).
                After the wipe the script re-runs the installer so the
                stack comes back up healthy with shipped defaults.
              </p>
              <p>
                What survives: <Code>/opt/guardian/.env</Code> (so your{" "}
                <Code>GUARDIAN_SECRET_KEK</Code> + registry credentials
                + any operator-managed env vars are intact across the
                reset), the docker images already on disk (no image
                pulls needed for the recovery install), and both
                recovery scripts themselves.
              </p>
              <p>
                When the script returns, the UI shows the default
                first-login screen again — sign in with{" "}
                <Code>admin</Code> and the value of{" "}
                <Code>GUARDIAN_DEFAULT_ADMIN_PASSWORD</Code> from{" "}
                <Code>/opt/guardian/.env</Code>. The installer&apos;s
                output banner shows this on screen, and you can{" "}
                <Code>grep GUARDIAN_DEFAULT</Code>{" "}
                <Code>/opt/guardian/.env</Code> any time to retrieve
                it. The agent walks you through changing the
                password at <Code>/profile</Code> just like a fresh
                install.
              </p>
            </SubSection>

            <SubSection icon="visibility" title="Checking auth events in observability">
              <p>
                Every login, every password change, every session
                lifecycle event is recorded in Guardian&apos;s audit
                log. You don&apos;t have to trust that things worked —
                you can see them. Two places to look:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Code>/observability/events</Code> — the structured
                  audit stream. Filter or scroll to find your action.
                  Each row shows <em>when</em>, <em>who</em> (you, the
                  CLI, or the system), and <em>what</em> happened.
                </li>
                <li>
                  <Code>/notifications</Code> — the security canary.
                  Every password change posts a notification
                  &ldquo;Your password was changed at &lt;timestamp&gt;.&rdquo;
                  If you see one you didn&apos;t make, that&apos;s the
                  signal to investigate.
                </li>
              </ul>
              <p>
                What to expect to see for each path you&apos;ve walked:
              </p>
              <Pre>{`After a successful first-time login (default credentials):
  login_success        user:admin        user:admin

After changing your password from /profile:
  password_changed_ui  user:admin        user:admin
  session_revoked      system            session:<id>     × (N revoked sessions)
  + a /notifications entry about the change

After a CLI reset (forgot-password path):
  password_changed_cli cli:<hostname>    user:admin
  session_revoked      system            session:<id>     × (N revoked sessions)
  + a /notifications entry about the change

After a failed login attempt:
  login_failed         ip:<source>       user:admin
  (if you cross the 5-fails/60s threshold, you'll see one more
   row marking the rate-limit lockout)`}</Pre>
              <p>
                If the action you took doesn&apos;t show up in{" "}
                <Code>/observability/events</Code>, that&apos;s a real
                problem to report — every auth path is supposed to be
                auditable. Conversely, if you see events you{" "}
                <em>didn&apos;t</em> make (especially{" "}
                <Code>password_changed_cli</Code> with an unfamiliar
                hostname), treat it as a host-compromise signal and
                investigate.
              </p>
            </SubSection>

            <SubSection icon="help" title="What if&hellip;">
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li><strong>The default credentials banner doesn&apos;t go away after changing the password.</strong> Hard-refresh the page (clears the AuthGate&apos;s cached state). If it persists, check the docker logs for entrypoint errors during the auth seed.</li>
                <li><strong>Login says &ldquo;Authentication service unavailable.&rdquo;</strong> The agent can&apos;t reach the MCP. Check <Code>docker compose ps</Code> — guardian-agent should be <Code>Up (healthy)</Code>.</li>
                <li><strong>Login says &ldquo;Too many failed attempts. Try again in Ns.&rdquo;</strong> Per-IP rate limit fired (5 failures in 60s). Wait it out; the lockout is 60s.</li>
                <li><strong>You changed your password and another tab still loads.</strong> The server-side cache is up to 30s. Click around — the next API call will get 401 and bounce you to sign in. (Or wait 30s.)</li>
                <li><strong>You upgrade Guardian and your password stops working.</strong> Auth state lives on the persistent <Code>guardian_data</Code> volume. As long as the volume isn&apos;t dropped (<Code>docker compose down -v</Code> would do that), credentials survive upgrades. If you DID drop the volume, you&apos;re back to the default credentials banner.</li>
              </ul>
            </SubSection>

            <SubSection icon="security" title="Where credentials live">
              <p>
                Guardian&apos;s admin password lives in EXACTLY one
                place: the SecretStore at{" "}
                <Code>/app/data/secrets/ui/auth/admin/</Code>{" "}
                inside the agent container (mapped to the{" "}
                <Code>guardian_data</Code> docker volume). It&apos;s
                stored as a PBKDF2-HMAC-SHA256 hash with a 32-byte
                random salt and 600,000 iterations, then encrypted at
                rest with the SecretStore&apos;s KEK-derived AES-256-GCM
                cipher.
              </p>
              <p>
                Session cookies are random 32-byte tokens. The server
                stores their SHA-256 hash + metadata (username, expiry,
                user-agent fingerprint) in{" "}
                <Code>auth_sessions.db</Code>, never the raw token.
                Cookies are <Code>HttpOnly</Code> +{" "}
                <Code>Secure</Code> + <Code>SameSite=Strict</Code> with
                a 2-hour absolute expiry, no remember-me. Each session
                is independently revocable; a successful password
                change revokes them all.
              </p>
            </SubSection>

            <SubSection
              icon="shield"
              title="API surface is server-side gated"
            >
              <p>
                Every <Code>/api/agent/*</Code> endpoint, plus{" "}
                <Code>/api/chat</Code> and <Code>/api/skills/*</Code>,
                requires a valid <Code>guardian_session</Code> cookie on
                EVERY request. The check happens at a Next.js
                middleware layer before any route handler runs — same
                cookie the UI uses, same validation path{" "}
                <Code>/api/auth/status</Code> uses.
              </p>
              <p>
                If you script against the Guardian API (curl, Python
                requests, etc.), include the session cookie in every
                call:
              </p>
              <Pre>{`# 1. Log in to get the session cookie
curl -c /tmp/cookies.txt -k -X POST https://localhost:3001/api/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"username":"admin","password":"<your password>"}'

# 2. Use the cookie on every subsequent call
curl -b /tmp/cookies.txt -k https://localhost:3001/api/agent/memory`}</Pre>
              <p className="text-sm text-on-surface-variant">
                Two endpoints are exempt by design:{" "}
                <Code>GET /api/agent/health</Code> (Docker compose
                healthcheck) and{" "}
                <Code>POST /api/agent/internal/fire-hook</Code> (called
                by the embedded MCP subprocess with bearer auth, not
                the session cookie). All other endpoints — read or
                write — require login.
              </p>
            </SubSection>
          </Section>

          <Section id="upgrades" icon="upload" title="Upgrading Guardian">
            <p>
              Guardian updates ship as numbered releases on{" "}
              <a
                href="https://github.com/kite-production/guardian/releases"
                className="link"
                target="_blank"
                rel="noopener noreferrer"
              >
                GitHub Releases
              </a>
              . Each release includes a <Code>guardian-installer</Code>{" "}
              binary stamped at that version, plus the docker images on
              GHCR. You can upgrade two ways: the in-app button (no SSH,
              best for routine updates) or the installer binary (for a
              clean re-install or a specific pinned version).
            </p>

            <SubSection icon="system_update_alt" title="In-app upgrade (About modal)">
              <p>
                Click <Term>About</Term> in the sidebar (or{" "}
                <Term>Check for updates</Term> in its menu). When a newer
                release is available you&apos;ll see an{" "}
                <em>Update available</em> banner with the running and
                latest versions and an <Term>Upgrade</Term> button.
              </p>
              <p className="text-sm text-on-surface-variant mt-2">
                Clicking <Term>Upgrade</Term> pulls the new images and
                swaps the containers in place, streaming live progress
                (fetching manifest → pulling images → swapping →
                healthcheck) into the modal. The agent itself restarts
                briefly during the swap — the page detects this, waits
                for the agent to come back, and reloads onto the new
                version automatically. You don&apos;t need to do anything
                while it runs; leaving the page won&apos;t cancel the
                update.
              </p>
              <Callout tone="info">
                If the banner shows &quot;You&apos;re on the latest
                release,&quot; no images need pulling. If an update is
                already running (e.g. started from another tab), the
                modal attaches to the in-progress run instead of starting
                a second one.
              </Callout>
            </SubSection>

            <SubSection icon="auto_awesome" title="Installer upgrade flow">
              <ol className="list-decimal pl-5 space-y-1.5 text-sm">
                <li>
                  Download the <Code>guardian-installer</Code> binary
                  for the version you want from the releases page.
                  Each binary is sealed to a single version.
                </li>
                <li>
                  <Code>chmod +x guardian-installer</Code>
                </li>
                <li>
                  <Code>sudo ./guardian-installer</Code>
                </li>
              </ol>
              <p className="text-sm text-on-surface-variant mt-2">
                The installer preserves <Code>/opt/guardian/.env</Code>{" "}
                secrets (KEK, registry token, UI password), strips the
                stale <Code>GUARDIAN_VERSION</Code> +{" "}
                <Code>DIGEST_GUARDIAN_*</Code> lines, appends the new
                manifest, and runs <Code>docker compose pull / up -d</Code>.
                Only services whose image content actually changed
                get recreated.
              </p>
            </SubSection>

            <SubSection icon="visibility" title="Auditing image versions">
              <p>
                Two operator surfaces show running image digests:
              </p>
              <ul className="list-disc pl-5 space-y-1 text-sm">
                <li>
                  <Term>About modal:</Term> click the version chip in
                  the sidebar, expand &quot;Image versions&quot; — shows
                  GUARDIAN_VERSION + 5 stack-tier digests.
                </li>
                <li>
                  <Term>Observability panel:</Term>{" "}
                  <Code>/observability/connectors</Code> has an{" "}
                  &quot;Image digests&quot; section with the 5 stack
                  rows + per-instance connector rows. Each row carries
                  a digest-vs-legacy-tag badge so operators can spot
                  any drift at a glance.
                </li>
              </ul>
              <p className="text-sm">
                For programmatic audit (e.g. piping into an incident
                report), hit <Code>GET /api/agent/digests</Code> — same
                content as the observability panel, structured JSON.
              </p>
            </SubSection>

            <SubSection icon="tune" title="Pinning a specific version">
              <p>
                Each <Code>guardian-installer</Code> binary is sealed
                to one version (its embedded digest manifest is only
                valid for that version). To install a specific
                version, download that version&apos;s installer binary
                from the GitHub Release. The{" "}
                <Code>--upgrade-to N.N.N</Code> flag is preserved for
                backward compat but only accepted when N.N.N matches
                the binary&apos;s stamp:
              </p>
              <pre className="text-xs bg-surface-container-low p-3 rounded">
{`# Download the binary for the version you want:
gh release download <version> --repo kite-production/guardian \\
  --pattern guardian-installer
chmod +x guardian-installer
sudo ./guardian-installer`}
              </pre>
              <Callout tone="info">
                Each installer embeds a per-version digest manifest,
                so one binary equals one installable version. The
                mental model maps directly to production-grade
                container deployment patterns (Kubernetes manifest
                pinning, ECS task-def digest refs, Nomad job spec
                digests).
              </Callout>
            </SubSection>

            <SubSection icon="error" title="Troubleshooting">
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>
                    &ldquo;invalid reference format&rdquo; on{" "}
                    <Code>compose up</Code>
                  </Term>{" "}
                  → <Code>.env</Code> is missing{" "}
                  <Code>DIGEST_GUARDIAN_*</Code> values. Re-run the
                  installer; the strip + append logic is idempotent.
                </li>
                <li>
                  <Term>Installer rejects --upgrade-to N.N.N</Term>{" "}
                  with &quot;doesn&apos;t match this binary&apos;s
                  version&quot; → expected behaviour. Download
                  the installer for the version you want.
                </li>
                <li>
                  <Term>
                    Yellow &quot;tag (legacy)&quot; badge in
                    /observability/connectors
                  </Term>{" "}
                  → an env var (e.g.{" "}
                  <Code>DIGEST_GUARDIAN_CONNECTOR_XSOAR</Code>) is
                  missing from{" "}
                  <Code>/opt/guardian/.env</Code> or wasn&apos;t
                  forwarded into the affected service&apos;s container.
                  Re-run installer to refresh; if still showing,
                  inspect the running container&apos;s env to confirm
                  the value made it through.
                </li>
              </ul>
            </SubSection>
          </Section>

          <Section id="ui-tour" icon="tour" title="Operator UI Tour">
            <p>
              The sidebar groups every page under five top-level sections,
              expandable / collapsible via the chevron in each header:
            </p>
            <ul className="list-disc pl-5 space-y-1.5 text-sm">
              <li>
                <Term>Command</Term> — the daily-driver surfaces (chat,
                skills, memory, knowledge, jobs, models, providers).
              </li>
              <li>
                <Term>Integration</Term> — external connections (connectors,
                approvals, notifications, API keys).
              </li>
              <li>
                <Term>Observability</Term> — runtime visibility (overview,
                metrics, traces, logs, events, pipeline, live activity).
              </li>
              <li>
                <Term>Settings</Term> — service configuration and the
                agent&apos;s personality.
              </li>
              <li>
                <Term>Learn</Term> — this hub plus User Journeys and the
                REST API reference.
              </li>
            </ul>
            <p>
              The whole sidebar collapses to icons via the chevron at the
              top. Below the nav lives a theme toggle (dark Ocean Navy ↔
              light Pale Azure), the Notifications shortcut (with a count
              badge for unread / pending approvals), and an Operator user
              card.
            </p>
            <p>
              Most pages share a common shape: a <Term>page header</Term>{" "}
              with icon + title + subtitle (jobs-style — icon directly on
              the surface, no boxed background), an optional{" "}
              <Term>action button</Term> on the right, a{" "}
              <Term>filter / search bar</Term> below the header, and a{" "}
              <Term>content area</Term> using glass panels for cards and
              tables. Tabs (where used) are green when active, matching
              the sidebar&apos;s active-link color.
            </p>
          </Section>

          {/* ============================================================
                                 COMMAND
              ============================================================ */}

          <Section id="chat" icon="chat_bubble" title="Chat">
            <p>
              The default landing page (<Link href="/" className="link">/</Link>) is
              the chat interface. The left rail lists every session in
              date-grouped buckets (Today, Yesterday, Last Week, Older),
              with a New Chat button at the top. Sessions persist for 30
              days; each has its own conversation history, memory scope,
              and pending tool-call state.
            </p>

            <SubSection icon="account_tree" title="Session lifecycle">
              <p>
                A session is created when you start a new chat. The agent
                writes one row to <Code>sessions</Code> sqlite, and
                appends every user/assistant/tool message to the{" "}
                <Code>messages</Code> table. On reload, the right-side
                telemetry panel rehydrates from messages — but only
                tool-round-trips, not raw model deltas (those aren&apos;t
                persisted to keep storage tractable).
              </p>
            </SubSection>

            <SubSection
              icon="smart_toy"
              title="Automated sessions are hidden by default"
            >
              <p>
                The autonomous investigation loop runs on a schedule and
                creates its own chat sessions every tick — on a busy
                install those can vastly outnumber your own conversations.
                The session rail <strong>hides scheduled-job sessions by
                default</strong> so your conversations are easy to find.
                Use the <strong>Automated sessions</strong> toggle under
                the New Chat button to switch between{" "}
                <Code>HIDDEN</Code> (your sessions only) and{" "}
                <Code>SHOWN</Code> (everything, including loop runs you
                want to inspect). The choice is remembered per browser.
              </p>
            </SubSection>

            <SubSection icon="bolt" title="Tool calls in chat">
              <p>
                When the agent decides to call a tool, you see an inline
                tool-call card with the tool name, arguments, and a status
                spinner. Tier-2+ tools (jobs_create, personality_update,
                instances_delete, api_keys_*) gate behind an{" "}
                <Link href="/approvals" className="link">approval</Link> —
                the call blocks server-side, an approval card renders
                inline, and the agent resumes once you click Approve.
                Tier-1 tools (read-only queries, non-destructive runs)
                execute immediately without prompt.
              </p>
            </SubSection>

            <SubSection icon="lightbulb" title="Common patterns">
              <p>Useful prompts to try:</p>
              <ul className="list-disc pl-5 space-y-1 text-sm">
                <li>
                  <em>&quot;Show me the open critical cases and pull the
                  extra data for the newest one&quot;</em> — picks the
                  right connector instance + the right case tools.
                </li>
                <li>
                  <em>&quot;What does the
                  <Code>xsoar_case_investigation</Code> skill do?&quot;</em>{" "}
                  — pulls from the skill catalog and explains.
                </li>
                <li>
                  <em>&quot;Remember that I prefer JSON output for
                  detection rules&quot;</em> — writes to memory under
                  scope <Code>user</Code>.
                </li>
                <li>
                  <em>&quot;What did I tell you about output format?&quot;</em>{" "}
                  — searches memory semantically.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="auto_awesome_motion" title="Auto-compaction & context guard">
              <p>
                Long sessions can outgrow the model&apos;s context window.
                Guardian guards against this in two ways. First, the chat
                handler estimates input + reserved-output tokens before each
                turn; at &gt;= 90% of the model cap it emits a{" "}
                <Code>context_warning</Code> event and the chat input shows
                a yellow banner with a one-click <Code>/compress</Code>{" "}
                action. Second, when token-budgeted history walking would
                drop more than ~5 prior messages (tunable in{" "}
                <Link href="/settings/personality" className="link">
                  Personality &rarr; Tuning
                </Link>
                ), the dropped portion is summarized into a checkpoint
                automatically — the operator sees the &ldquo;auto-compacted
                N messages&rdquo; divider in the message thread.
              </p>
            </SubSection>

            <SubSection icon="bolt" title="Vertex prompt caching">
              <p>
                When using a Vertex Gemini model, the chat route can cache
                the stable system prompt with Vertex&apos;s{" "}
                <Code>cachedContents</Code> API — cached input tokens bill
                at ~25% of the standard rate. The model selector chip
                shows a small amber dot when the previous turn registered
                a cache hit; hover for the cached/prompt token ratio.
                Disable per session via{" "}
                <Link href="/settings/personality" className="link">
                  Personality &rarr; Tuning &rarr; Vertex prompt caching
                </Link>
                .
              </p>
            </SubSection>

            <SubSection icon="terminal" title="Slash commands">
              <p>
                Type <Code>/help</Code> at the start of any message for the
                full list. Quick reference: <Code>/compress</Code> rolls
                prior turns into a checkpoint; <Code>/clear</Code> ends the
                session and starts a fresh one (transcript stays
                exportable); <Code>/model &lt;name&gt;</Code> overrides the
                model for this session. See the dedicated{" "}
                <a href="#slash-commands" className="link">
                  Slash Commands
                </a>{" "}
                section for the full behavior + side effects.
              </p>
            </SubSection>

            <SubSection icon="data_object" title="Direct tool invocation">
              <p>
                Type <Code>^toolname arg=value</Code> at the start of any
                message to call a connector tool directly &mdash; bypassing
                the model entirely. The result renders as a JSON code block
                in the chat transcript, visually distinct from a normal
                model reply.
              </p>
              <p className="text-sm leading-relaxed">
                Examples:
              </p>
              <ul className="list-disc pl-5 space-y-1 text-sm">
                <li>
                  <Code>^list_incidents query=&quot;status:active&quot;</Code> &mdash;
                  bare name resolves to <Code>xsoar_list_incidents</Code>{" "}
                  (the only registered tool with that suffix). Returns the
                  raw open-case list.
                </li>
                <li>
                  <Code>
                    ^xsoar_get_incident incident_id=&quot;482&quot;
                  </Code>{" "}
                  &mdash; quoted strings support whitespace.
                </li>
                <li>
                  <Code>
                    ^list_incidents &#123;&quot;query&quot;:&quot;status:active&quot;, &quot;limit&quot;:3&#125;
                  </Code>{" "}
                  &mdash; JSON-literal args for structured shapes (arrays,
                  nested objects).
                </li>
                <li>
                  <Code>^cortex-docs.search query=&quot;close incident&quot; product=xsoar</Code>{" "}
                  &mdash; fully-qualified <Code>connector.tool</Code> form
                  also works.
                </li>
              </ul>
              <p className="text-sm leading-relaxed mt-2">
                Auto-typing on key=value args: <Code>true</Code> /
                <Code> false</Code> become booleans, <Code>null</Code>{" "}
                becomes null, <Code>10</Code> / <Code>3.14</Code> become
                numbers, everything else is a string. ISO timestamps,
                UUIDs, IPs, hostnames: pass them as-is &mdash; they stay
                strings (no mangling).
              </p>
              <p className="text-sm leading-relaxed mt-2">
                <strong>Critical property:</strong> direct tool invocation
                works <em>even without a provider configured</em>. On a
                fresh install before you&apos;ve set up Gemini or Vertex,
                you can still <Code>^xsoar_list_incidents query=&quot;...&quot;</Code>{" "}
                to validate the connector. The model is never called; the
                tool dispatches through the embedded MCP&apos;s JSON-RPC
                surface (POST <Code>/api/agent/tool/call</Code>) which
                requires only your UI session cookie.
              </p>
              <p className="text-sm leading-relaxed mt-2">
                Use cases:
              </p>
              <ul className="list-disc pl-5 space-y-1 text-sm">
                <li>
                  Validating a connector instance you just created (does it
                  actually return rows?).
                </li>
                <li>
                  Testing arg shapes before authoring chat prompts the
                  model would dispatch.
                </li>
                <li>
                  Pre-LLM smoke on a fresh install (deterministic, free,
                  doesn&apos;t consume model tokens).
                </li>
                <li>
                  Debugging connector container state (
                  <Code>^xsoar_list_incidents</Code> with no args
                  proves the container is reachable + auth is valid).
                </li>
              </ul>
            </SubSection>
          </Section>

          {/* Slash commands reference. Lives between the Chat overview
              and the Skills page so the navigation flow goes "what is
              chat → what can I type → what skills can I invoke". */}
          <Section id="slash-commands" icon="terminal" title="Slash Commands">
            <p>
              Slash commands let you control the chat session itself
              (&ldquo;meta&rdquo; actions) instead of asking the model
              to do something. Type at the very start of your message;
              everything else is sent to the model normally.
            </p>

            <SubSection icon="compress" title="/compress">
              <p>
                Roll all prior turns in this session into a single summary
                checkpoint. Use it when the chat is getting long and the
                model is having trouble remembering early context.
              </p>
              <ul className="list-disc pl-5 space-y-1 text-sm">
                <li>
                  <Term>What it does</Term> — fetches the session history,
                  summarizes it via the same model you&apos;re chatting
                  with, persists the summary as a{" "}
                  <Code>system</Code> message tagged{" "}
                  <Code>kind:&quot;compaction-checkpoint&quot;</Code>.
                </li>
                <li>
                  <Term>Side effects</Term> — emits{" "}
                  <Code>compaction_start</Code> and{" "}
                  <Code>compaction_end</Code> SSE events; the message
                  thread gets a horizontal divider at the checkpoint
                  position; the chat header shows a &ldquo;Compacted N
                  messages&rdquo; badge.
                </li>
                <li>
                  <Term>Audit</Term> — durable rows under{" "}
                  <Code>action:chat_compaction_*</Code> in{" "}
                  <Link href="/observability/events" className="link">
                    /observability/events
                  </Link>
                  .
                </li>
                <li>
                  <Term>When to use</Term> — manually before a long
                  research session, or when the auto-suggest banner fires
                  at 80% context utilization.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="restart_alt" title="/clear">
              <p>
                End the current session and start a fresh one in the same
                window. The previous transcript is preserved (still
                listed in the sidebar, still exportable) — you just won&apos;t
                accidentally continue from it.
              </p>
              <ul className="list-disc pl-5 space-y-1 text-sm">
                <li>
                  <Term>What it does</Term> — POSTs to the MCP&apos;s{" "}
                  <Code>/api/v1/sessions/&#123;id&#125;/end</Code>, then
                  creates a new session, then emits a{" "}
                  <Code>session_cleared</Code> SSE event so the chat UI
                  can swap its active session pointer without a page
                  reload.
                </li>
                <li>
                  <Term>Idempotent on new sessions</Term> — running
                  <Code>/clear</Code> on a brand-new session is a no-op
                  (there&apos;s nothing to clear).
                </li>
                <li>
                  <Term>When to use</Term> — when you want a fresh
                  context budget without losing the history of what
                  you&apos;ve done.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="help" title="/help">
              <p>
                List the registered slash commands with their one-line
                descriptions. Built from the same{" "}
                <Code>SLASH_COMMANDS</Code> table the chat handler
                dispatches against, so the help output stays in sync
                automatically.
              </p>
            </SubSection>

            <SubSection icon="tune" title="/model &lt;name&gt;">
              <p>
                Override the model for THIS session. Persists into{" "}
                <Code>session.metadata.preferred_model</Code>; subsequent
                turns read it on entry. The header dropdown still wins
                if you also pick a model there.
              </p>
              <ul className="list-disc pl-5 space-y-1 text-sm">
                <li>
                  <Code>/model</Code> (no args) — show the current
                  preference (or the runtime default).
                </li>
                <li>
                  <Code>/model gemini-2.5-pro</Code> — set the
                  preference.
                </li>
                <li>
                  <Code>/model auto</Code> — clear the override; future
                  turns use the runtime default.
                </li>
                <li>
                  <Term>SSE</Term> — emits{" "}
                  <Code>model_preference_changed</Code> when set; the
                  next turn&apos;s <Code>model</Code> event includes{" "}
                  <Code>override_source: &quot;session&quot;</Code> so
                  the UI can distinguish header vs session overrides.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="add_circle" title="Adding a new slash command">
              <p>
                Slash commands are a registry pattern. Each command is one
                entry in <Code>SLASH_COMMANDS</Code> at the top of{" "}
                <Code>app/api/chat/route.ts</Code> with a name,
                description, and async handler. The handler runs inside
                the SSE stream and owns its own controller close. See{" "}
                <Code>lib/slash-commands.ts</Code> for the framework.
              </p>
            </SubSection>
          </Section>

          {/* Plan mode operator workflow. */}
          <Section id="plan-mode-ux" icon="checklist" title="Plan Mode">
            <p>
              Plan mode lets you ask the agent to <em>propose</em> a
              multi-step plan before running anything — useful when a
              request is ambiguous, cross-system, or destructive enough
              that you want to review the steps before tools fire. Type{" "}
              <Code>/plan</Code> at the start of a chat message and the
              agent switches into proposal mode for that turn.
            </p>

            <SubSection icon="play_circle" title="Triggering">
              <p>
                Three entry points, same effect:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Code>/plan investigate incident 4112, then update
                  its severity from the findings</Code> — explicit slash command.
                </li>
                <li>
                  Type your request normally and click the{" "}
                  <Term>Plan first</Term> chip on the chat input — same
                  outcome, lower friction.
                </li>
                <li>
                  Set <Code>plan_mode_default: true</Code> in{" "}
                  <Link href="/settings/personality" className="link">
                    Personality
                  </Link>{" "}
                  for sessions where you always want a plan first.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="reviews" title="Reviewing the proposal">
              <p>
                The agent renders an inline plan card showing the steps it
                would take. You then choose how to proceed:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Approve &amp; run</Term> — the button on the plan
                  card re-runs the original prompt and executes the whole
                  plan with a <em>one-shot</em> approval bypass, so Tier-2/3
                  tools run without a card per tool. The bypass applies only
                  to that single execution; the next prompt re-gates
                  normally.
                </li>
                <li>
                  <Term>Run it step-by-step</Term> — re-send the original
                  prompt yourself (without <Code>/plan</Code>). That path
                  still surfaces per-tool approval cards for Tier-2/3 tools.
                </li>
                <li>
                  <Term>Revise</Term> — type a follow-up to ask for changes
                  (&quot;plan again but skip step 3&quot;).
                </li>
                <li>
                  <Term>Discard</Term> — send a different prompt; the
                  proposal goes away.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="article" title="Audit + observability">
              <p>
                Each proposal writes a <Code>chat_plan_proposed</Code>{" "}
                audit row; failures (model couldn&apos;t produce a valid
                plan) write <Code>chat_plan_failed</Code>. An{" "}
                <Term>Approve &amp; run</Term> execution writes{" "}
                <Code>chat_plan_executed</Code> so the one-shot bypass
                leaves a forensic trace even though it skips the per-tool
                approval rows. Filter on{" "}
                <Code>action:chat_plan_*</Code> in{" "}
                <Link href="/observability/events" className="link">
                  /observability/events
                </Link>{" "}
                to see proposals and runs across sessions.
              </p>
            </SubSection>

            <Callout tone="info">
              <Term>Approve &amp; run</Term> grants a deliberate one-shot
              approval bypass for that single plan execution — that is the
              point of approving once. If you want to step through Tier-2/3
              tools individually, re-send the prompt yourself without{" "}
              <Code>/plan</Code> instead; that path keeps every per-tool
              approval card.
            </Callout>
          </Section>

          {/* Tasks page + /tasks command. */}
          <Section id="tasks-ux" icon="task_alt" title="Tasks">
            <p>
              Long-running operations the agent kicks off (a multi-step
              subagent, a deferred job dispatch) land
              in the <Term>tasks registry</Term> rather than blocking the
              chat. View them at{" "}
              <Link href="/tasks" className="link">/tasks</Link> or list
              the active set inline with <Code>/tasks</Code> in any chat.
            </p>

            <SubSection icon="account_tree" title="Lifecycle">
              <p>
                Every task moves through the same state machine. The
                tasks page color-codes each row by current state:
              </p>
              <Pre>{`pending      ── created, not yet picked up by a worker
running      ── worker is actively executing
completed    ── finished successfully
failed       ── worker raised an unrecoverable error
aborted      ── operator clicked Cancel before completion`}</Pre>
              <p>
                Each transition writes an audit row{" "}
                (<Code>action:task_started</Code>,{" "}
                <Code>action:task_completed</Code>, etc.). Long-lived
                tasks emit <Code>task_transitioned</Code> on every
                intermediate hop, so you can replay precisely when state
                changed.
              </p>
            </SubSection>

            <SubSection icon="timeline" title="The /tasks page">
              <p>
                Three tabs: <Term>Active</Term> (pending + running),{" "}
                <Term>Recent</Term> (last 24h, all states), and{" "}
                <Term>All</Term> (full history with date filter). Each
                row shows: task ID, kind (subagent / job /
                tool), target (the thing being acted on), elapsed time,
                originating session, and a status pill.
              </p>
              <p>
                Click any row to open the detail drawer with: the
                originating chat link, the full audit-row trail (all
                state transitions), the worker&apos;s last heartbeat,
                and the output preview where applicable.
              </p>
            </SubSection>

            <SubSection icon="cancel" title="Cancelling + retrying">
              <p>
                Active tasks have a <Term>Cancel</Term> button in the
                detail drawer. Cancel signals the worker to abort at its
                next checkpoint; the task transitions to{" "}
                <Code>aborted</Code> and any partially-applied side
                effects are documented in the run output. Failed tasks
                show a <Term>Retry</Term> button that re-creates the
                task with the same inputs.
              </p>
            </SubSection>

            <SubSection icon="terminal" title="The /tasks slash command">
              <p>
                Inside a chat, <Code>/tasks</Code> renders a compact
                inline table of active tasks (same data as the page&apos;s
                Active tab). Each row links to the task detail. Useful
                when you want to keep working in chat while monitoring
                in-flight work without switching tabs.
              </p>
            </SubSection>
          </Section>

          <Section id="skills" icon="auto_awesome" title="Skills">
            <p>
              <Link href="/skills" className="link">/skills</Link> is the
              registry of every behavior Guardian knows about. Skills are
              markdown documents the agent reads at the start of relevant
              sessions to bias its tool selection — think &quot;procedural
              recipes&quot; rather than runnable code.
            </p>

            <SubSection icon="category" title="Four categories">
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Foundation</Term> — reusable building blocks.
                  Guardian ships five: the Cortex KB search discipline
                  (<Code>cortex_kb_search</Code>), its query-patterns
                  and raw-API companions, the XSOAR case-triage
                  reference (<Code>xsoar_case_triage</Code>), and the
                  XSOAR platform reference
                  (<Code>xsoar_platform_reference</Code>) — the War
                  Room / <Code>!command</Code> / query-syntax card the
                  agent consults before running an XSOAR command or
                  filtering cases. The agent draws on these to compose
                  larger flows.
                </li>
                <li>
                  <Term>Scenarios</Term> — operator-authored multi-step
                  runbooks for recurring incident types (phishing
                  triage, ransomware response, account-compromise
                  sweeps). Empty by default — author your own.
                </li>
                <li>
                  <Term>Validation</Term> — verification flows
                  (confirm a query returns the expected evidence,
                  post-incident checks). Empty by default.
                </li>
                <li>
                  <Term>Workflows</Term> — multi-step orchestration.
                  Guardian ships <Code>xsoar_case_investigation</Code>,
                  the load-first chain that takes an XSOAR case from
                  &ldquo;it just opened&rdquo; to documented + resolved.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="article" title="Skill anatomy">
              <p>
                Each skill is a markdown file with optional YAML
                front-matter:
              </p>
              <Pre>{`---
name: cortex_kb_search
displayName: Cortex KB Search
category: foundation
locked: false              # platform-enforced when true; can't be disabled
loadingMode: on-demand     # vs "always"
---

# Cortex KB Search

Answers Cortex product questions by searching the official Palo Alto
Networks documentation and returning evidence-backed, cited answers.

## When to use
...

## Steps
1. Call \`cortex_suggest\` to find the exact doc title
2. ...`}</Pre>
            </SubSection>

            <SubSection icon="lock" title="Lock state and overrides">
              <p>
                Each card shows a lock icon (platform-enforced skills
                can&apos;t be disabled by the operator), a toggle for
                enable/disable, and click-through to a detail panel with
                the full markdown content and analytics (calls in last
                24h / 7d / 30d). Skills are global to the install —
                Guardian is single-tenant, so a skill is either on or off
                for the whole agent.
              </p>
            </SubSection>

            <SubSection icon="edit" title="Create / Edit / Download / Delete / Import">
              <p>
                Every skill card&apos;s detail panel has three header
                actions: <Term>Download</Term> grabs the live MD as a
                .md file (handy for offline edits or sharing);{" "}
                <Term>Save</Term> commits textarea edits — click into
                the body editor first to lazy-load the live MD, then
                Save calls <Code>PUT /api/skills</Code>. The backend
                writes a <Code>.md.bak</Code> next to the original
                before overwriting, so a one-line shell fix recovers
                an unwanted change. <Term>Delete</Term> soft-deletes:
                the MD moves to <Code>/app/skills/.deleted/</Code> on
                the volume, recoverable via <Code>docker exec</Code>{" "}
                + <Code>mv</Code>. Locked skills render Delete as
                disabled — they&apos;re foundational and breaking
                them breaks the agent.
              </p>
              <p>
                <Term>Create</Term>: button in the page header opens
                the editor. Display name auto-derives the on-disk
                filename via slugify (e.g. &ldquo;Phishing Triage
                Runbook&rdquo; → <Code>phishing_triage_runbook.md</Code>);
                you can override the filename if needed. Pick a
                category (foundation / scenarios / validation /
                workflows), write a description (this is what the chat
                agent sees in <Code>&lt;available_skills&gt;</Code> —
                be concise and specific), then write the body. Submit
                composes minimal frontmatter and POSTs.
              </p>
              <p>
                <Term>Import</Term>: button next to Create.
                Pick a <Code>.md</Code> file from your local machine —
                if the file has a YAML frontmatter block, the import
                pulls <Code>name</Code> and <Code>category</Code> from
                it; otherwise the filename becomes the canonical name
                and category defaults to <Code>scenarios</Code>. Useful
                for porting skills between deployments (export with
                Download → Import on the target). Imports of an
                already-existing skill name fail with an explicit
                &ldquo;already exists&rdquo; error so you can&apos;t
                accidentally overwrite — delete the existing skill
                first or rename the import.
              </p>
              <p>
                Operator edits land on the volume immediately — the
                next chat turn picks them up because the system prompt
                fetches the skills registry per turn. No restart required.
              </p>
            </SubSection>

            <SubSection icon="psychology" title="Chat agent skill awareness">
              <p>
                The chat system prompt now includes an{" "}
                <Code>## AVAILABLE SKILLS</Code> block listing every
                installed skill&apos;s name, display name, category,
                description, and ATT&amp;CK tactics. The{" "}
                <em>bodies</em> stay out of the prompt — they&apos;d
                add tens of kilobytes per turn, breaking the prompt
                cache every time anyone edits a skill. Instead, the
                model decides which skill (if any) to apply based on
                metadata, then calls <Code>skills_read</Code> to pull
                the full body when it&apos;s actually going to use it.
              </p>
              <p>
                Practical effect: ask the agent to &ldquo;investigate
                the newest open critical case&rdquo; and it picks{" "}
                <Code>workflows/xsoar_case_investigation.md</Code>{" "}
                from the registry on its own. You don&apos;t have to
                tell it where to look. The metadata is also fresh per
                turn — adding a new skill via the UI makes it
                immediately discoverable in the next chat message.
              </p>
            </SubSection>

            <Callout tone="warn">
              Editing skills under{" "}
              <Code>bundles/spark/mcp/skills/*.md</Code> in the repo
              only reaches the running container after a build +{" "}
              <Code>FORCE_SKILLS_SYNC=1</Code> on the next run, or
              after a <Code>docker compose down -v</Code> drops the
              volume. <strong>UI-driven CRUD bypasses this</strong> —
              creates / edits / deletes go straight to the volume via
              the MCP, so the in-flight container picks them up
              without a restart. The repo→volume drift only matters
              for source-tracked skills the operator wants to ship to
              fresh installs. See{" "}
              <Link href="/help/architecture#manifest" className="link">
                Architecture &rarr; Manifest &amp; Bundle
              </Link>{" "}
              for the why.
            </Callout>
          </Section>

          {/* Agents page (subagents + operator-authored definitions). */}
          <Section id="agents-ux" icon="smart_toy" title="Agents">
            <p>
              <Link href="/agents" className="link">/agents</Link> lists
              every agent definition the runtime knows about — built-in
              subagents, plugin-contributed agents, and ones you author
              yourself. Each agent is a scoped persona: its own system
              prompt, tool/skill allow-list, model preference, and origin.
            </p>

            <SubSection icon="badge" title="Origin badges">
              <p>
                Three badges distinguish where a definition came from:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>built-in</Term> — ships with the bundle. Cannot
                  be deleted, but can be disabled via the agent toggle
                  on the card.
                </li>
                <li>
                  <Term>plugin</Term> — contributed by an installed plugin
                  (see <a href="#plugins-ux" className="link">Plugins</a>).
                  Reloaded when the plugin reloads.
                </li>
                <li>
                  <Term>operator</Term> — authored by you via the{" "}
                  <Term>New agent</Term> button or duplicated from an
                  existing definition. Stored in the runtime DB and
                  survives restarts.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="edit_note" title="The edit drawer">
              <p>
                Click any agent row to open the edit drawer. Built-in /
                plugin agents are read-only at the source level but can be
                forked into operator-owned copies. Editable fields:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Display name + description</Term> — what surfaces
                  in <Code>/spawn</Code> typeahead and chat references.
                </li>
                <li>
                  <Term>System prompt</Term> — the persona&apos;s base
                  instructions. Markdown-friendly; supports the same
                  template variables the chat persona uses
                  (<Code>$&#123;workspace&#125;</Code>,{" "}
                  <Code>$&#123;operator&#125;</Code>).
                </li>
                <li>
                  <Term>Allowed tools / skills</Term> — scoped catalogs.
                  An agent only sees the intersection of its allow-list
                  and the runtime&apos;s active set. Wildcards supported
                  (<Code>xsoar_*</Code>, <Code>xsoar_get_incident</Code>).
                </li>
                <li>
                  <Term>Model preference</Term> — overrides the runtime
                  default for this agent. Useful when a focused agent
                  benefits from a smaller faster model
                  (<Code>gemini-2.5-flash</Code>) vs the chat
                  default&apos;s <Code>gemini-2.5-pro</Code>.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="rocket_launch" title="Spawning from chat">
              <p>
                Type <Code>/spawn case-triage incident=INC-4112</Code>{" "}
                to dispatch a subagent. The chat shows an inline{" "}
                <Term>subagent panel</Term> with the agent&apos;s
                streaming output, tool calls, and final summary. Multiple
                subagents can run in parallel — each gets its own panel.
                The parent chat resumes once all dispatched subagents
                report back.
              </p>
              <p>
                Subagents run in the foreground (their output streams
                back into the parent thread) rather than as background
                tasks — see{" "}
                <Link
                  href="/help/architecture#design-decisions"
                  className="link"
                >
                  Architecture &rarr; Design Decisions
                </Link>{" "}
                for the rationale.
              </p>
            </SubSection>

            <SubSection icon="article" title="Audit trail">
              <p>
                Lifecycle audit rows: <Code>chat_subagent_started</Code>,{" "}
                <Code>chat_subagent_completed</Code>,{" "}
                <Code>chat_subagent_failed</Code>. Edits to agent
                definitions write <Code>agent_definition_upsert</Code>{" "}
                /<Code>_enabled</Code>/<Code>_disabled</Code>/
                <Code>_deleted</Code>. Filter on{" "}
                <Code>action:agent_definition_*</Code> in{" "}
                <Link href="/observability/events" className="link">
                  /observability/events
                </Link>{" "}
                to audit who changed what.
              </p>
            </SubSection>

            <SubSection icon="route" title="When to spawn vs ask the parent">
              <p>
                Subagents are a delegation tool, not a default. They
                cost an extra Gemini call cycle (system-prompt
                tokens + tool-catalogue tokens for the scoped child),
                they don&apos;t share the parent&apos;s short-term
                memory, and their transcript doesn&apos;t bubble up
                to the parent&apos;s context. Use them when the cost
                buys you something concrete:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Different persona / tighter tool scope</Term>
                  {" "}— the parent is a general-purpose assistant;
                  a triage subagent needs investigation-only
                  framing and a tool list that excludes
                  incident-mutating tools. The
                  scoped tool catalogue is the security argument: a
                  tool not in the catalogue can&apos;t be called
                  through a hook injection or a prompt-injection
                  attempt.
                </li>
                <li>
                  <Term>Long sub-task you don&apos;t want polluting
                  parent context</Term> — the parent already has 80%
                  of its context window full; you don&apos;t want a
                  150-tool-call evidence sweep to consume the rest.
                  The subagent runs in its own session; only the
                  final summary returns to the parent.
                </li>
                <li>
                  <Term>Parallel exploration</Term> — dispatch two
                  subagents at once (e.g. one sweeping endpoint
                  telemetry + one reviewing identity logs) to look at
                  the same incident
                  from two angles. Each gets its own panel; their
                  summaries arrive independently.
                </li>
              </ul>
              <p className="text-sm text-on-surface-variant">
                When you DON&apos;T need a subagent: short follow-up
                questions, debugging the parent&apos;s last tool
                call, anything that needs the parent&apos;s working
                memory of the current incident. A subagent
                won&apos;t see the parent&apos;s recent context — it
                starts fresh with only its system prompt + your{" "}
                <Code>/spawn</Code> argument.
              </p>
            </SubSection>

            <SubSection icon="bug_report" title="Debugging subagents">
              <p>
                When a subagent isn&apos;t doing what you expect,
                walk this ladder:
              </p>
              <ol className="list-decimal pl-5 space-y-1.5 text-sm">
                <li>
                  Open the <Term>sidechain</Term> link in the
                  subagent panel. The full subagent transcript opens
                  in a new tab — every tool call, every model reply,
                  the final summary. The parent panel only shows the
                  summary by design; sidechain has the detail.
                </li>
                <li>
                  Open{" "}
                  <Link href="/observability/events" className="link">
                    /observability/events
                  </Link>{" "}
                  and filter <Code>action:chat_subagent_*</Code>. You
                  get the lifecycle audit (started / completed /
                  failed) plus per-tool-call rows tagged with the
                  subagent session id. A subagent that finished{" "}
                  <em>failed</em> shows the failure reason in the row
                  metadata.
                </li>
                <li>
                  Check <Term>blocked tool</Term> events. If the
                  subagent tried a tool outside its scope, the
                  sidechain shows a <Code>subagent_tool_blocked</Code>{" "}
                  SSE event. Either widen the allow-list (on{" "}
                  <Link href="/agents" className="link">/agents</Link>{" "}
                  edit drawer) OR refine the system prompt so the
                  model doesn&apos;t reach for that tool.
                </li>
                <li>
                  Check the <Term>max_turns</Term> cap on the agent
                  definition. A subagent that returns a thin summary
                  may simply have run out of turns before completing
                  its task. The audit row carries{" "}
                  <Code>statusReason: &apos;max-turns-reached&apos;</Code>{" "}
                  when this happens.
                </li>
                <li>
                  Cost rollup — the per-subagent cost shows up in{" "}
                  <Link href="/observability/cost" className="link">
                    /observability/cost
                  </Link>{" "}
                  filtered to that session id. Subagents inherit the
                  parent&apos;s model unless the agent definition
                  overrides; switching a heavy subagent to a smaller
                  model (e.g. <Code>gemini-2.5-flash</Code>) is the
                  fastest cost lever.
                </li>
              </ol>
            </SubSection>
          </Section>

          <Section id="memory" icon="database" title="Memory">
            <p>
              <Link href="/memory" className="link">/memory</Link> is a
              vector-indexed key/value store. The agent writes here when
              the operator says &quot;remember X&quot; or when it captures
              durable context across sessions. Each row carries a key,
              value, scope, timestamps, optional TTL, and free-form
              metadata.
            </p>

            <SubSection icon="layers" title="Four scopes">
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>agent</Term> — applies to every session. Use for
                  &quot;facts the agent should always know.&quot;
                </li>
                <li>
                  <Term>session</Term> — current chat only. Cleared when
                  the session ends. Use for &quot;don&apos;t pollute the
                  agent scope, just remember this for now.&quot;
                </li>
                <li>
                  <Term>user</Term> — per-operator preferences. The agent
                  picks these up across sessions but they don&apos;t
                  affect other operators if you ever add multi-user.
                </li>
                <li>
                  <Term>system</Term> — platform-managed entries. Created
                  by background jobs (e.g., periodic open-case snapshots)
                  — read by the agent, not directly by the operator.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="search" title="Semantic search">
              <p>
                The search bar runs vector similarity (Vertex
                <Code>text-embedding-004</Code>, 768 dims). So{" "}
                <em>&quot;detection rules I prefer&quot;</em> matches an
                entry literally written{" "}
                <em>&quot;output JSON for detections&quot;</em> — same
                meaning, different words.
              </p>
            </SubSection>

            <SubSection icon="diversity_3" title="MMR + temporal decay + FTS hybrid">
              <p>
                Three ranking improvements layer over the base vector
                similarity:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>MMR (maximal marginal relevance)</Term> — after
                  the top-K is pulled by similarity, each candidate is
                  re-scored with{" "}
                  <Code>λ × similarity − (1 − λ) × max_pairwise_sim</Code>.
                  λ near 1 favors relevance; λ near 0 favors diversity.
                  Default 0.7. Prevents the result list from being
                  dominated by 5 near-duplicate rows.
                </li>
                <li>
                  <Term>Temporal decay</Term> — exponential decay applied
                  to row age in days:{" "}
                  <Code>exp(−age_days × λ)</Code>. Default λ = 0.01 means
                  a 10-day-old row keeps ~90% of its score; a 100-day-old
                  row keeps ~37%. The <em>fresh / recent / old</em>{" "}
                  bucket badge on each result row shows the rough decay
                  bucket the row falls into.
                </li>
                <li>
                  <Term>FTS5 keyword promotion</Term> — for queries with
                  literal terms (UUIDs, hostnames, IP addresses), the
                  pure-similarity recall sometimes misses obvious matches.
                  An FTS5 index (porter stemmer + unicode61 tokenizer)
                  promotes literal hits into the result set with an{" "}
                  <Term>FTS hit</Term> badge. Useful for{" "}
                  <em>&quot;find the entry mentioning UUID
                  abc-123&quot;</em>.
                </li>
              </ul>
              <p className="mt-2">
                Defaults are configured in{" "}
                <Link
                  href="/settings/personality"
                  className="link"
                >
                  Personality &rarr; Tuning
                </Link>
                . For one-off tuning, use the <Term>Advanced</Term>{" "}
                disclosure on{" "}
                <Link href="/memory" className="link">/memory</Link> —
                lambda overrides apply to the next search and reset on
                close.
              </p>
            </SubSection>

            <SubSection icon="schedule" title="TTL and cleanup">
              <p>
                Optional <Code>ttl_seconds</Code> per entry. The runtime
                sweeps expired entries on a 5-minute tick, so a 60-second
                TTL is in practice 60-360 seconds. For shorter half-lives,
                consider scope <Code>session</Code> (auto-cleared on end)
                instead.
              </p>
            </SubSection>
          </Section>

          <Section id="knowledge" icon="menu_book" title="Knowledge Bases">
            <p>
              <Link href="/knowledge" className="link">/knowledge</Link>{" "}
              browses the bundle&apos;s loaded knowledge bases — curated,
              schema-validated, semantically searchable reference content.
              KBs differ from memory in three ways: read-only at the agent
              surface, sourced from the bundle (not chat), and indexed at
              boot rather than on-write. Open a KB and use the{" "}
              <strong>tag filter chips</strong> to narrow by
              tactic, platform, or any label — e.g. on{" "}
              <Code>mitre-attack-enterprise</Code>, click{" "}
              <Term>credential-access</Term> + <Term>windows</Term> to see
              only Windows credential-access techniques; both browse and
              semantic search respect the selected tags. On large KBs the
              header shows the full entry count and a <strong>Load more</strong>{" "}
              button pages through every entry — e.g.{" "}
              <Code>mitre-attack-enterprise</Code> is 697 entries,{" "}
              <Code>soar-playbooks</Code> 798.
            </p>

            <SubSection icon="library_books" title="Bundled KB — SOC Investigation">
              <p>
                Guardian ships one knowledge base —{" "}
                <Link href="/knowledge/soc-investigation" className="link">
                  soc-investigation
                </Link>{" "}
                — a curated corpus of <strong>30 reference docs</strong> the
                investigation agent searches to <em>ground</em> its analysis:
              </p>
              <ul className="list-disc pl-5 space-y-1 mt-2">
                <li>
                  <strong>20 MITRE ATT&amp;CK technique guides</strong>{" "}
                  (category <Code>attack-technique</Code>, id = the ATT&amp;CK
                  id, e.g. <Code>T1071.004</Code> DNS C2): how the technique
                  manifests in telemetry, the ordered investigation steps, the
                  data sources to pull, and pivot/related techniques.
                </li>
                <li>
                  <strong>10 IR playbooks</strong> (category{" "}
                  <Code>playbook</Code>, id = <Code>pb-&lt;slug&gt;</Code>,
                  e.g. <Code>pb-ransomware</Code>): triage, blast-radius
                  scoping, containment, evidence to collect, and the
                  TRUE/FALSE-positive verdict criteria.
                </li>
              </ul>
              <p className="mt-2">
                <strong>How it differs from memory.</strong> Knowledge is{" "}
                <em>curated reference material</em> — shipped in the image,
                indexed at boot, read-only at the agent surface. Memory is the
                agent&apos;s <em>accumulated, mutable org facts</em> (crown-jewel
                hosts, prior incidents) it writes as it works. The agent{" "}
                <em>reads</em> knowledge to know how to investigate;{" "}
                it <em>writes</em> memory to remember your environment. Both use
                the same Vertex <Code>text-embedding-004</Code> embedder, but
                only knowledge is operator-curated and version-controlled in the
                bundle.
              </p>
              <p className="mt-2">
                The investigation skill consults the KB as its{" "}
                <strong>first research step</strong> on every case — searching{" "}
                <Code>category=&quot;attack-technique&quot;</Code> by the
                observed behavior and <Code>category=&quot;playbook&quot;</Code>{" "}
                by the case kind, then citing the matching doc in the case
                Issue. To add or revise a doc, edit{" "}
                <Code>bundles/spark/kbs/soc-investigation/entries/</Code> and
                redeploy; the loader hash-detects changes and re-embeds only
                what changed.
              </p>
            </SubSection>

            <SubSection icon="query_stats" title="XQL query authoring">
              <p>
                Guardian can author <strong>Cortex XSIAM XQL queries</strong>{" "}
                for you — ad-hoc (&quot;write an XQL query for failed logins in
                the last hour&quot;) or mid-investigation (&quot;hunt this host
                for lateral movement&quot;). Three pieces work together:
              </p>
              <ul className="list-disc pl-5 space-y-1 mt-2">
                <li>
                  The{" "}
                  <Link href="/knowledge/xql-examples" className="link">
                    xql-examples
                  </Link>{" "}
                  knowledge base — <strong>383 example queries</strong>:
                  reusable patterns, per-vendor alert-mapping queries, an{" "}
                  ATT&amp;CK-tagged <strong>IR / threat-hunting set</strong>{" "}
                  (brute force, C2 beaconing, lateral movement, exfiltration,
                  ransomware, cloud abuse, …), the full stage/function coverage
                  matrix, correlation-rule bodies, and the complete 20-scenario
                  coverage program — with <strong>146 added by running them
                  live</strong> against a real XSIAM tenant. Browse it under{" "}
                  <Link href="/knowledge" className="link">Knowledge</Link>.
                </li>
                <li>
                  The <Code>cortex_xql_query_authoring</Code> skill (under{" "}
                  <Link href="/skills" className="link">Skills</Link>) — finds
                  similar examples, confirms each stage&apos;s syntax against the
                  live Palo Alto Cortex docs, and writes a cited query.
                </li>
                <li>
                  Mid-incident, it pivots from the case&apos;s indicators to XQL
                  hunts that scope blast radius, and (with an XSIAM instance
                  configured) runs them to enumerate affected assets.
                </li>
                <li>
                  <strong>Compute-Unit (CU) quota awareness.</strong> XSIAM
                  meters data-lake queries in Compute Units against a daily
                  limit. Ask the agent &quot;what&apos;s my XQL quota?&quot; and
                  it reads the live quota (no CU spent) via{" "}
                  <Code>xsiam_get_xql_quota</Code>; every query it runs now
                  reports its <Code>compute_units_used</Code> and remaining
                  budget. The <Code>cortex_compute_unit_forecasting</Code> skill
                  (under <Link href="/skills" className="link">Skills</Link>)
                  explains how CU is consumed — cost scales with data scanned, so
                  narrowing the time window is the biggest lever — and forecasts
                  how many queries your daily limit allows.
                </li>
                <li>
                  <strong>It verifies before it returns.</strong> Before handing
                  you a query, the agent runs it on a narrow window via{" "}
                  <Code>xsiam_xql_verify</Code> and checks that it parses, that
                  the expected columns and sample values come back, and what it
                  costs — so a <em>silently-wrong</em> query (one that returns
                  rows that look right but aren&apos;t) is caught before you act
                  on it. It also discovers a dataset&apos;s real field names from
                  the live schema (<Code>xsiam_datamodel_describe</Code>) rather
                  than guessing — across the hundreds of datasets a tenant
                  ingests (cloud audit logs, firewall events, forensic
                  artifacts), not just endpoint telemetry.
                </li>
                <li>
                  <strong>Authoring detections, not just hunts.</strong> The{" "}
                  <Code>cortex_detection_rule_authoring</Code> skill (under{" "}
                  <Link href="/skills" className="link">Skills</Link>) turns a
                  hunt into a scheduled <strong>correlation rule</strong>: the{" "}
                  <em>filter → bucket-time → aggregate → threshold → project
                  entities</em> shape, which output columns map to the alert,
                  suppression to avoid alert storms, and which settings live in
                  the rule editor (schedule, severity, MITRE) rather than the
                  query. Ask &quot;turn that hunt into a correlation rule.&quot;
                </li>
              </ul>
            </SubSection>

            <SubSection icon="shield" title="Bundled KB — MITRE ATT&CK Enterprise">
              <p>
                <Link href="/knowledge/mitre-attack-enterprise" className="link">
                  mitre-attack-enterprise
                </Link>{" "}
                is the <strong>complete</strong> MITRE ATT&amp;CK Enterprise
                matrix — <strong>~697 docs</strong>, one per technique and
                sub-technique. Where <Code>soc-investigation</Code> is curated
                narrative, this is the exhaustive <em>reference</em>: each doc
                carries the technique&apos;s description, tactics, platforms,
                <strong> detection analytics + log sources</strong>, and
                <strong> mitigations</strong>, with the ATT&amp;CK id as the doc
                id (<Code>T1059</Code>, <Code>T1059.001</Code>).
              </p>
              <p className="mt-2">
                It&apos;s <strong>generated deterministically</strong> from the
                official ATT&amp;CK STIX bundle (never hand-edited), so it stays a
                faithful mirror and regenerates cleanly on each MITRE release
                (~2×/yr); the <Code>framework_version</Code> on every doc pins
                the source. Its 697 embeddings are <strong>pre-computed and baked
                into the bundle</strong>, so the KB loads
                with <strong>zero Vertex calls</strong> at boot — no multi-minute
                first-boot indexing. Search it with plain English (e.g.{" "}
                <em>&quot;dumping credentials from lsass&quot;</em> →{" "}
                <Code>T1003.001</Code>) and the agent uses it to ground every
                investigation in the authoritative technique definition.
              </p>
              <p className="mt-2 text-xs text-on-surface-variant/70">
                ATT&amp;CK® is © The MITRE Corporation, reproduced under the
                ATT&amp;CK Terms of Use; Guardian is not endorsed or certified by
                MITRE (see the KB&apos;s <Code>NOTICE.txt</Code>).
              </p>
            </SubSection>

            <SubSection icon="smart_toy" title="Bundled KB — MITRE ATLAS (AI security)">
              <p>
                <Link href="/knowledge/mitre-atlas" className="link">
                  mitre-atlas
                </Link>{" "}
                is <strong>MITRE ATLAS</strong> — the ATT&amp;CK-style framework
                for attacks on <strong>AI / ML systems</strong>: prompt
                injection, model evasion, data poisoning, model theft, agent
                hijacking. <strong>227 docs</strong> in two flavors:
              </p>
              <ul className="list-disc pl-5 space-y-1 mt-2">
                <li>
                  <strong>170 techniques</strong> (<Code>category=attack-technique</Code>,
                  e.g. <Code>AML.T0051</Code> LLM Prompt Injection) — description,
                  tactics, mitigations, and the mapped ATT&amp;CK Enterprise id
                  where ATLAS declares one.
                </li>
                <li>
                  <strong>57 real-world AI-incident case studies</strong>{" "}
                  (<Code>category=case-study</Code>, <Code>AML.CS####</Code>) —
                  each a documented attack with its step-by-step procedure,
                  target, and actor. High-value grounded evidence for AI
                  investigations.
                </li>
              </ul>
              <p className="mt-2">
                Why it matters: Guardian is itself an AI agent and customers
                increasingly run AI/LLM workloads — ATLAS is the canonical
                language for investigating AI-targeting incidents. Generated
                deterministically from the official ATLAS data; embeddings baked
                in (boots with zero Vertex calls). ATLAS™ is a project of The
                MITRE Corporation (see the KB&apos;s <Code>NOTICE.txt</Code>).
              </p>
            </SubSection>

            <SubSection icon="automation" title="Bundled KB — SOAR Playbooks">
              <p>
                <Link href="/knowledge/soar-playbooks" className="link">
                  soar-playbooks
                </Link>{" "}
                is ~800 Cortex XSOAR <strong>out-of-the-box response
                playbooks</strong> from the MIT-licensed{" "}
                <Term>demisto/content</Term> repo (SOC-relevant packs across ~77
                products). Where the other KBs answer <em>what happened</em>,
                this answers <strong>how to respond / automate</strong> — e.g.
                &quot;a generic phishing-investigation playbook&quot; or
                &quot;a CrowdStrike host-isolation playbook&quot;.
              </p>
              <p className="mt-2">
                Per the design, the <strong>embedded text is a reviewed
                description</strong> of what each playbook does (its purpose,
                inputs/outputs, and the integrations it calls) so search matches
                intent — and the <strong>raw playbook YAML is kept</strong>
                (open an entry to see it). Each is <strong>dual-labeled</strong>:
                by <em>product/pack</em> (e.g. <Code>product:crowdstrike</Code>,{" "}
                <Code>support:partner</Code>) and by{" "}
                <em>investigation-type / use-case</em> (e.g.{" "}
                <Code>phishing</Code>, <Code>endpoint</Code>,{" "}
                <Code>threat-intel</Code>) — both filterable via the tag
                chips. They also double as worked examples for an agent that
                helps <em>build</em> playbooks.
              </p>
              <p className="mt-2 text-xs text-on-surface-variant/70">
                Playbook YAML © Palo Alto Networks / Demisto under the MIT
                License; product names are nominative (see{" "}
                <Code>NOTICE.txt</Code>).
              </p>
            </SubSection>

            <SubSection icon="lan" title="Bundled KBs — ATT&CK ICS + Mobile">
              <p>
                Rounding out the MITRE ATT&amp;CK matrix family:{" "}
                <Link href="/knowledge/mitre-attack-ics" className="link">
                  mitre-attack-ics
                </Link>{" "}
                (97 docs — the OT / Industrial-Control-Systems matrix, for
                SCADA/PLC/HMI attacks) and{" "}
                <Link href="/knowledge/mitre-attack-mobile" className="link">
                  mitre-attack-mobile
                </Link>{" "}
                (124 docs — Android/iOS). Same deterministic generator + baked
                embeddings as ATT&amp;CK Enterprise. They&apos;re always loaded;
                when an investigation is IT-only, scope a search to{" "}
                <Code>mitre-attack-enterprise</Code> (or filter by the{" "}
                <Code>ecosystem</Code> tag) so OT/mobile techniques don&apos;t
                add noise.
              </p>
            </SubSection>

            <SubSection icon="search" title="How the agent researches a case">
              <p>
                When a case references something the agent can&apos;t
                interpret from the record alone, it researches rather than
                guesses, in priority order:{" "}
                (1)&nbsp;<Code>knowledge_search</Code> against the bundled{" "}
                <Term>soc-investigation</Term> KB <em>first</em> — the internal,
                instant, curated tradecraft (technique manifestation signals,
                ordered investigation steps, the matching response playbook);
                (2)&nbsp;<Code>cortex_search</Code> / <Code>cortex_suggest</Code>{" "}
                → <Code>cortex_fetch_topic</Code> against the live Cortex docs
                for anything Cortex-specific the KB doesn&apos;t cover;
                (3)&nbsp;for external context (IP/domain reputation, CVE
                advisories), the <Code>web</Code> connector;
                (4)&nbsp;it cites each source — KB doc id included — when it
                writes findings back onto the case. The{" "}
                <Code>cortex_kb_search</Code> skill governs the query
                discipline.
              </p>
            </SubSection>

            <SubSection icon="settings" title="Adding entries">
              <p>
                The boot loader reads{" "}
                <Code>bundles/spark/kbs/&lt;name&gt;/entries/*.md</Code>,
                validates each against the KB&apos;s{" "}
                <Code>schema.json</Code>, and writes one row per entry
                into a per-KB SQLite database with the embedding cached
                alongside. Source-hash detection means re-running boot
                without changes is a no-op (no Vertex calls). Adding an
                entry is therefore: drop a markdown file, redeploy. Future
                Tier-3 will add runtime CRUD — the page is currently
                read-only by design.
              </p>
            </SubSection>
          </Section>

          <Section id="playbook-builder" icon="design_services" title="Playbook Builder">
            <p>
              <Link href="/playbooks/build" className="link">/playbooks/build</Link>{" "}
              drafts a new <strong>Cortex XSOAR playbook</strong> from a
              plain-English use-case, grounded in the ~800 real playbooks in the{" "}
              <Code>soar-playbooks</Code> knowledge base — and it keeps a record
              of everything you build so you can come back to it.
            </p>
            <SubSection icon="grid_view" title="The build history">
              <p>
                The page opens on your <strong>build history</strong>: four stat
                cards across the top (<strong>Total</strong>,{" "}
                <strong>Deployed</strong>, <strong>Validated</strong>,{" "}
                <strong>Failed</strong>), status tabs to filter by stage
                (Drafted / Validated / Deployed / Tested / Failed), a search box,
                and a grid of every playbook you&apos;ve built. It works like the{" "}
                <Link href="/skills" className="link">Skills</Link> page — search
                or tab to find a past build, then click its card.
              </p>
              <p>
                Each build records its lifecycle as it progresses:{" "}
                <Code>drafted</Code> when first created,{" "}
                <Code>validated</Code> once the structure check passes,{" "}
                <Code>deployed</Code> after it&apos;s imported into your tenant,
                and <Code>tested</Code> after a test-run — or <Code>failed</Code>{" "}
                if a step didn&apos;t complete. The cards and stat counts update
                to match.
              </p>
            </SubSection>
            <SubSection icon="bolt" title="Build a new playbook">
              <p>
                Click <strong>New playbook</strong> to open the builder panel.
                Describe what the playbook should do (e.g. &quot;investigate a
                phishing email end to end, then delete similar messages on
                confirmation&quot;), optionally name a product/integration
                (CrowdStrike, Defender, generic), and build it. The agent finds
                the closest existing playbooks, studies their task structure, and
                drafts a new one in that shape — then <strong>validates</strong>{" "}
                it (required fields, the task graph wiring, reachability) so you
                know it will import. The new build appears in your history as a
                card.
              </p>
            </SubSection>
            <SubSection icon="rocket_launch" title="Deploy + test-run">
              <p>
                On a draft, click <strong>Deploy + test-run</strong>{" "}
                and confirm. Guardian <strong>imports</strong> the playbook into
                your connected Cortex XSOAR tenant, creates a throwaway{" "}
                <Code>[Guardian test]</Code> incident, <strong>runs</strong> the
                playbook on it, shows you the <strong>outcome</strong> (which
                tasks ran, any errors), and <strong>closes</strong> the test
                incident. Every tenant write is approval-gated. The agent can do
                the same if you just ask it to &quot;deploy and test-run this
                playbook&quot;.
              </p>
              <p>
                <strong>If auto-import isn&apos;t available</strong> (a Cortex 8
                tenant without the Core REST API integration, where the API
                doesn&apos;t expose playbook import), Guardian tells you so and
                gives you the manual step — import the downloaded YAML via{" "}
                <strong>Settings → Playbooks → Import</strong> (or enable the Core
                REST API integration for one-click) — then runs the test once the
                playbook exists. Direct one-click import works on XSOAR 6 and on
                Cortex 8 with that integration.
              </p>
            </SubSection>
            <SubSection icon="article" title="Open a past build">
              <p>
                Click any card to open its <strong>detail panel</strong>. It
                shows the generated <strong>YAML</strong>, the{" "}
                <strong>validation</strong> result, the{" "}
                <strong>deploy summary</strong> (and the test incident, if it was
                run), a <strong>Download .yml</strong> button, and a{" "}
                <strong>Delete</strong> action to remove a build you no longer
                need. Re-open a draft any time to deploy and test-run it later.
              </p>
            </SubSection>
          </Section>

          <Section id="jobs" icon="schedule" title="Jobs">
            <p>
              <Link href="/jobs" className="link">/jobs</Link> manages
              recurring scheduled work — the same prompts you&apos;d type
              in chat, but fired on cron. Each job card shows a name,
              schedule, action type, last-run status, and a quick-link to
              run history.
            </p>

            <SubSection icon="alarm" title="Cron syntax">
              <p>
                Standard 5-field cron (minute / hour / day-of-month /
                month / day-of-week). Common cadences:
              </p>
              <Pre>{`*/5 * * * *      every 5 minutes
0 */1 * * *      every hour on the hour
0 9 * * 1-5      9am Mon–Fri (workday morning)
0 0 */7 * *      every 7 days at midnight
0 6 * * 0        Sunday 6am (weekly report)`}</Pre>
            </SubSection>

            <SubSection icon="add_circle" title="Two creation paths">
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Manifest-declared</Term> — listed in{" "}
                  <Code>manifest.yaml:jobs[]</Code>. Reconciled at boot:
                  the manifest is the source of truth, so editing a
                  manifest job and redeploying overwrites whatever&apos;s
                  in the runtime DB. Use for jobs that come with the
                  bundle.
                </li>
                <li>
                  <Term>Operator-created</Term> — via{" "}
                  <Link href="/jobs/new" className="link">/jobs/new</Link>.
                  Persists to the runtime DB and survives boot. Use for
                  ad-hoc schedules (a one-off weekly demo, an experimental
                  cadence).
                </li>
              </ul>
            </SubSection>

            <SubSection icon="history" title="Run history">
              <p>
                Click any job to see its run history table — one row per
                fire, with status (succeeded / failed / running), trigger
                source (cron / manual), duration, and a link to the run
                detail page. The detail page renders the model&apos;s
                full reply (for prompt actions) or the tool result (for
                tool_call actions). Telemetry from the run is preserved
                so you can replay what happened minutes or weeks later.
              </p>
            </SubSection>

            <SubSection id="permission-policies" icon="shield_lock" title="Permission policy">
              <p>
                Each job carries a declarative <Term>permission policy</Term>{" "}
                — a tool allowlist enforced by the chat route&apos;s
                tool-dispatch loop. Without a policy, every job-dispatched
                chat turn could call ANY tool the agent has access to;
                a scheduled &quot;morning case sweep&quot; job could
                technically also call <Code>xsoar_close_incident</Code>{" "}
                if the model decided to. Permission policies let you
                scope what each job can touch.
              </p>
              <p>
                The form (Section 01, below Extended-thinking) has three
                comma-separated glob inputs:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Allowed tools</Term> — whitelist when non-empty.
                  Tools not matching any pattern are denied. Example:{" "}
                  <Code>xsoar_*, cortex_*</Code> restricts the job to
                  the xsoar and cortex-docs tool families.
                </li>
                <li>
                  <Term>Denied tools</Term> — blacklist. Denies even
                  tools that matched the allowed list (denied wins).
                  Example: <Code>*_delete, xsoar_close_incident</Code>{" "}
                  forbids destructive tools.
                </li>
                <li>
                  <Term>Require approval</Term> — forces the standard
                  approval card for matching tools, regardless of the
                  job&apos;s <Code>bypass_approvals</Code> setting.
                  Example: <Code>xsoar_update_incident, xsoar_close_incident</Code>{" "}
                  routes state-mutating tools through operator
                  confirmation.
                </li>
              </ul>
              <p>
                Empty all three = no policy (no restrictions). Glob
                syntax: <Code>*</Code> matches any sequence,{" "}
                <Code>?</Code> matches one char, comma-separated for OR.
                When a tool is denied, the chat thread surfaces a tool-
                error response with the denial reason; the model
                continues with that signal.
              </p>
              <Callout tone="info">
                Permission policies are <strong>not a security
                boundary</strong> by themselves — the MCP-side approval
                gate stays the authoritative defense for destructive
                tools. The policy is an operator-facing scope check
                that runs BEFORE the approval gate. Defense in depth.
              </Callout>
              <Callout tone="info">
                Per-skill permission policies are deferred to a
                follow-up release (skills affect chat-turn dispatches —
                different code path than scheduled jobs — and land in
                their own release window).
              </Callout>
            </SubSection>

            <SubSection id="model-routing" icon="psychology" title="Model override">
              <p>
                Each job picks its own model + extended-thinking
                preference, independent of the runtime default. The
                form&apos;s <Term>Model</Term> dropdown (Section 01,
                below Bypass-approvals) defaults to{" "}
                <strong>Router default (no override)</strong> — meaning
                &ldquo;use whatever <Code>runtimeConfig.GEMINI_MODEL</Code>{" "}
                is at dispatch time.&rdquo; Pick a specific model when:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <strong>You want cheaper dispatches</strong> on a
                  routine / high-volume job (e.g.{" "}
                  <Code>gemini-2.5-flash</Code> for a job that fires
                  every 5 minutes sweeping for new cases — Flash is
                  ~10× cheaper and the work doesn&apos;t need Pro
                  reasoning).
                </li>
                <li>
                  <strong>You want better quality</strong> on a job
                  that does real analysis (e.g.{" "}
                  <Code>gemini-3.1-pro-preview</Code> on a nightly
                  &ldquo;summarize the alert backlog&rdquo; job where
                  cost-per-fire is amortized over real insight).
                </li>
                <li>
                  <strong>You want to test a model</strong> against a
                  specific scheduled workload before promoting it to
                  the runtime default. Set the override on the job,
                  watch a week of runs in <Code>/observability/cost</Code>,
                  then make an informed change.
                </li>
              </ul>
              <p>
                The <Term>Extended thinking</Term> toggle right below
                the dropdown hints the model to use its deeper
                reasoning path (Gemini&apos;s thinkingConfig). The UI
                disables the toggle when the picked model doesn&apos;t
                support thinking — Flash variants silently ignore it.
                <em>Caveat:</em> the toggle is stored,
                dispatched, and visible in the form, but the
                chat-route&apos;s Gemini call payload doesn&apos;t yet
                wire <Code>body.thinking</Code> through to{" "}
                <Code>thinkingConfig</Code> — that lands in a
                follow-up release. Today, enabling thinking on a job
                has no visible effect; the storage path is forward-
                compat.
              </p>
              <Callout tone="info">
                The override is per-job, not per-skill. If you invoke a
                skill from a job&apos;s prompt, the skill runs under
                the job&apos;s model override. Per-skill overrides are
                a planned feature (skills affect chat-turn dispatches
                rather than scheduled-job dispatches — separate code
                path with its own integration window).
              </Callout>
            </SubSection>

            <SubSection icon="edit" title="Edit a job">
              <p>
                The <Code>⋯</Code> kebab on each job row has an{" "}
                <Term>Edit</Term> item between Pause and Duplicate. Click
                it → the new-job form opens with every field
                pre-populated from the existing row: schedule (loaded as
                Custom + raw cron — switch to Repeating to re-derive),
                timezone, action type and body, enabled flag, approval
                bypass.
              </p>
              <p>
                The <Term>name is locked</Term> — the backend PATCH
                endpoint is name-keyed and there&apos;s no rename today.
                If you need to rename, delete the job and create a new
                one (you&apos;ll lose run history). Submit changes from
                the &quot;Save Changes&quot; button at the bottom of the
                form (label flips from &quot;Create Job&quot; in
                edit mode).
              </p>
              <p>
                Manifest-source jobs accept the patch but the next
                manifest reconciliation (boot) reverts it; a runtime
                source badge tells you which is which.
              </p>
            </SubSection>

            <SubSection icon="layers" title="Two action types">
              <p>
                Every job runs as one of exactly two types — chosen at
                create time, switchable on edit:
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>
                  <Term>Prompt</Term> — a natural-language message
                  (&quot;check XSOAR for new high-severity cases and
                  summarize what changed overnight&quot;). Runs through the
                  same chat pipeline as your interactive sessions:
                  personality from{" "}
                  <Link href="/settings/personality" className="link">
                    /settings/personality
                  </Link>{" "}
                  is applied to the system prompt, the agent can call{" "}
                  <Code>memory_search</Code> /{" "}
                  <Code>knowledge_search</Code> on demand, every fired
                  tool is audited, and any{" "}
                  <Code>humanRequired</Code> tool surfaces the same
                  approval card flow (or auto-approves when the
                  job&apos;s &quot;bypass approvals&quot; toggle is on).
                  Best for fuzzy intent, multi-step reasoning, and
                  anything where the exact tool sequence isn&apos;t
                  known up-front.
                </li>
                <li>
                  <Term>Tool call</Term> — direct MCP tool invocation
                  with explicit args (<Code>name</Code> +{" "}
                  <Code>args</Code>). No LLM, no chat handler.
                  Deterministic. Best for recurring
                  queries, anything where the args are known and the
                  same exact call needs to fire on schedule.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="extension" title="Bind a job to a specific skill">
              <p>
                Prompt-action jobs grew an optional{" "}
                <Term>Skill</Term> dropdown below the prompt textarea.
                Default is <em>Let agent decide</em> — the model
                sees the full skills registry in its system prompt
                (every chat turn fetches it live, including scheduled
                runs) and picks one based on intent. Pick a specific
                skill instead if you want the run to be deterministic
                regardless of model drift: at fire time, the
                scheduler resolves the skill MD body and prepends it
                to your prompt inside{" "}
                <Code>&lt;skill name=&quot;…&quot;&gt;</Code> tags so
                the agent treats it as authoritative runbook context.
              </p>
              <p>
                Useful for reproducible scheduled runs — &ldquo;run
                the weekly incident summary every Sunday
                at 06:00&rdquo; should always run the same runbook,
                not whatever the model thinks fits the prompt that
                week. The dropdown is grouped by category and
                populated live from the skills registry, so newly
                created skills appear in it without restart.
              </p>
              <p>
                If a skill is later deleted but a job still references
                it, the run logs a warning and falls back to the plain
                prompt — the job doesn&apos;t fail. Edit the job to
                pick a different skill (or none) when you see the
                warning.
              </p>
            </SubSection>

            <SubSection icon="notifications_active" title="Notifications on every run">
              <p>
                Every scheduled job run now publishes a notification
                on completion. Two topics:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Code>job-run-completed</Code> (severity{" "}
                  <Term>info</Term>) — fired on success.
                </li>
                <li>
                  <Code>job-run-failed</Code> (severity{" "}
                  <Term>warning</Term>) — fired on failure; the
                  payload includes the error string and a one-line
                  summary so the bell card has something readable
                  without parsing result_json.
                </li>
              </ul>
              <p>
                Skipped runs (cron-cap squelching, paused jobs)
                don&apos;t emit — they&apos;re scheduling noise.
                Notifications appear on{" "}
                <Link href="/notifications" className="link">
                  /notifications
                </Link>{" "}
                and update the bell badge in the top nav. The
                payload also carries{" "}
                <Code>{`{job_name, run_id, trigger, action_name, duration_ms, next_due_at}`}</Code>{" "}
                so a click-through can route back to the run detail
                page.
              </p>
            </SubSection>

            <SubSection icon="import_export" title="Export + Import">
              <p>
                Two export options, both JSON, both surfaced under the{" "}
                <Code>⋯</Code> kebab:
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>
                  <Term>Export definition (.json)</Term> — pure
                  definition. The blob is exactly what{" "}
                  <Code>POST /api/v1/jobs</Code> accepts, so it imports
                  cleanly into another deployment. Available on every
                  row in the list view AND on the detail page.
                </li>
                <li>
                  <Term>Export runs (.json)</Term> — definition +
                  every run from the run-history table. Detail page
                  only (the list view doesn&apos;t load runs). Filename
                  ends in <Code>-with-runs.json</Code>. For forensic
                  snapshots — the runs are NOT importable as run history
                  (per policy below).
                </li>
              </ul>
              <p>
                The <Term>Import</Term> button on the{" "}
                <Link href="/jobs" className="link">/jobs</Link> page
                (next to Create Job) accepts either export shape.
                Behavior:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  Pick a <Code>.json</Code> file → the import button
                  reads it, extracts the <Code>job</Code> block,
                  validates the envelope&apos;s <Code>schema_version</Code>,
                  POSTs to the create endpoint.
                </li>
                <li>
                  If the file came from a <Code>-with-runs.json</Code>{" "}
                  export, the <Code>runs</Code> array is silently
                  dropped — only the definition is imported. Run
                  history is read-only ground truth, not portable
                  state.
                </li>
                <li>
                  On a name conflict (the imported job&apos;s name is
                  already taken), the create endpoint returns 400 with
                  the exact error: &quot;job &apos;X&apos; already
                  exists&quot;. Edit the JSON&apos;s <Code>name</Code>{" "}
                  field and re-import.
                </li>
                <li>
                  The MCP&apos;s create endpoint also rejects unknown
                  action types — if you import an old export with{" "}
                  <Code>type: log</Code>, you&apos;ll get &quot;must be
                  one of tool_call|prompt&quot;. Export-then-import a
                  fresh definition (boot migration normalizes legacy
                  shapes) and it&apos;ll round-trip.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="cycle" title="Autonomous investigation loop (demo harness)">
              <p>
                A reference set of three jobs runs an unattended
                investigate-and-improve cycle — useful as a demo/training
                harness (it seeds <strong>synthetic</strong> incidents, so
                point it at a non-production tenant). They&apos;re codified in{" "}
                <Code>scripts/bootstrap_loop_jobs.sh</Code>; re-run it after a
                fresh install to (re)provision them.
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <strong>guardian-incident-seeder</strong> (hourly) — creates
                  one synthetic <Code>[guardian-loop]</Code> XSOAR incident +
                  its tracking Issue.
                </li>
                <li>
                  <strong>guardian-investigation-loop</strong> (every 30 min) —
                  investigates the oldest open tracked Issue end-to-end
                  (enrich → scope → attack-chain + relations diagrams → resolve
                  with a verdict), and groups related incidents into a Case.
                </li>
                <li>
                  <strong>guardian-investigation-judge</strong> (every 6h) —
                  scores recent resolved investigations and, on a systematic
                  weakness, refines the investigation skill itself. Every skill
                  edit is snapshotted (<Code>skills/.history/</Code>) and
                  audited (<Code>skill_updated</Code>), so you can review or
                  roll back any autonomous change from{" "}
                  <Link href="/observability/events" className="link">
                    /observability/events
                  </Link>.
                </li>
              </ul>
            </SubSection>
          </Section>

          <Section
            id="models-providers"
            icon="psychology"
            title="Models & Providers"
          >
            <p>
              <Link href="/models" className="link">/models</Link> shows every
              model the agent can route to, grouped by interaction kind
              (Chat, CLI, Embedding, Image, Voice). Each model card lists
              its provider, capability flags (streaming, tool_use), and
              context window. The active tab uses the same green-active
              treatment as the sidebar.
            </p>
            <p>
              <Link href="/providers" className="link">/providers</Link> manages
              credentials. Vertex AI is the default — the setup form
              writes the service-account JSON into the secret store, and
              the bundle&apos;s <Code>requiredSecrets</Code> declares
              where it lands.
            </p>
            <SubSection icon="hub" title="Cohere North — a private Cohere model">
              <p>
                To run Guardian on a private / on-prem Cohere deployment
                (e.g. an air-gapped or sovereignty deployment), open the{" "}
                <strong>Cohere North</strong> card on{" "}
                <Link href="/providers" className="link">/providers</Link> and
                enter the <strong>Endpoint URL</strong>, the{" "}
                <strong>Agent ID</strong>, and the <strong>Bearer Token</strong>.
                Click <em>Test Connection</em>, then <em>Save</em>. Once saved,{" "}
                <strong>Cohere North</strong> appears in the model dropdown on{" "}
                <Link href="/models" className="link">/models</Link> and in the
                chat / jobs / subagent model pickers — pick it to run the full
                tool-using investigation loop on your Cohere model instead of
                Gemini.
              </p>
              <p>
                The bearer token is stored encrypted in the secret store and is
                never exposed to the agent. Keep <strong>TLS verification on</strong>;
                for a private certificate authority, add the CA to the container
                trust store rather than disabling verification. Embeddings for the
                knowledge base continue to use Vertex.
              </p>
            </SubSection>

            <SubSection icon="route" title="Resolution logic">
              <p>
                The bundle&apos;s <Code>modelRequirements</Code> in{" "}
                <Code>manifest.yaml</Code> declares minimum capabilities:
              </p>
              <Pre>{`modelRequirements:
  primary:
    kind: chat
    mustSupport: [streaming, tool_use]
    contextWindowMin: 100000
    preferFamily: [gemini-3, gemini-2.5, gpt-4o]
  fallback:
    kind: chat
    mustSupport: [streaming, tool_use]
    contextWindowMin: 32000`}</Pre>
              <p>
                At chat time, the resolver scans available providers,
                picks the first model that meets <Code>primary</Code>
                requirements, and falls back to <Code>fallback</Code> if
                primary is unavailable. The chosen model shows in the
                chat&apos;s telemetry panel.
              </p>
            </SubSection>

            <SubSection icon="star" title="Default model">
              <p>
                Pick your default chat model on{" "}
                <Link href="/models" className="link">
                  Settings → Models
                </Link>
                : open any model card and click{" "}
                <strong>Set as default</strong>. New chats use it
                automatically — the model dropdown chip shows{" "}
                <strong>Default — &lt;model&gt;</strong> instead of
                &ldquo;auto&rdquo; — and you can still switch models
                per chat without affecting the default.
              </p>
            </SubSection>
          </Section>

          {/* ============================================================
                               INTEGRATION
              ============================================================ */}

          <Section
            id="investigation"
            icon="frame_inspect"
            title="Investigation — Issues & Cases"
          >
            <p>
              The <Link href="/investigation/issues" className="link">Investigation</Link>{" "}
              area is where Guardian keeps its own record of the
              work it does on an alert. It holds two object types:{" "}
              <Term>Issues</Term> and <Term>Cases</Term>.
            </p>

            <SubSection icon="bug_report" title="What an Issue is">
              <p>
                An <Term>Issue</Term> is Guardian&apos;s local investigation
                record — its own write-up of one thing it looked into. It is
                deliberately distinct from an upstream{" "}
                <Term>XSOAR incident</Term>: the XSOAR incident lives on the
                Cortex platform and is owned by your SOAR; the Issue lives
                inside Guardian and is owned by you and the agent. When the
                agent works an incident it opens an Issue and stores the
                originating incident id as the Issue&apos;s{" "}
                <Code>source_ref</Code>, so you always have a back-link to
                the platform record without conflating the two.
              </p>
            </SubSection>

            <SubSection icon="folder_special" title="What a Case is">
              <p>
                A <Term>Case</Term> is a group of related Issues. When several
                Issues turn out to be the same campaign, the same actor, or
                otherwise belong together, you (or the agent) collect them
                under one Case so the bigger picture is visible in one place.
                An Issue belongs to at most one Case; a Case can hold many
                Issues.
              </p>
            </SubSection>

            <SubSection icon="auto_awesome" title="Who creates them">
              <p>
                Guardian opens and maintains Issues{" "}
                <Term>automatically</Term> during investigations. When the
                agent starts working a case it opens an Issue, logs each
                step and finding to the Issue&apos;s timeline as it goes, and
                records the final verdict when it concludes — you don&apos;t
                have to ask it to. It also groups related Issues into Cases
                on its own.
              </p>
              <p>
                You can create them yourself too. The sidebar{" "}
                <Term>Investigation</Term> group has{" "}
                <strong>New Issue</strong> and <strong>New Case</strong>{" "}
                actions for opening a record by hand — useful when you want
                to track something you noticed that didn&apos;t arrive as an
                alert.
              </p>
            </SubSection>

            <SubSection icon="description" title="The Issue layout">
              <p>
                Opening an Issue shows a full-width, tabbed layout built for an
                analyst write-up. A header carries the
                title, a <Term>VERDICT</Term> banner (the structured verdict
                with its confidence when set, falling back to the summary&apos;s
                leading verdict line), the{" "}
                <Term>status / severity</Term> controls, and the{" "}
                <Term>case assignment</Term>; the body is organised into tabs:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Overview</Term> — <Term>Summary</Term>,{" "}
                  <Term>Scope</Term>, and <Term>Recommendations</Term>, editable;
                  the agent fills these in as it works and you can refine them.
                </li>
                <li>
                  <Term>Assessment</Term> — the <Term>structured outcome</Term>:
                  the verdict (true positive, false positive, benign,
                  needs escalation, or inconclusive), a confidence meter, the{" "}
                  <Term>blast radius</Term> (which hosts, accounts, and data the
                  attack touched), and <Term>ATT&amp;CK technique</Term> chips —
                  over the editable <Term>Conclusions</Term> (the verdict
                  reasoning) and <Term>Next steps</Term>.
                </li>
                <li>
                  <Term>Report</Term> — a generated, shareable markdown
                  closure report that pulls the verdict, blast radius, ATT&amp;CK
                  techniques, indicators, and timeline into one document. Click{" "}
                  <strong>Generate report</strong> (or <strong>Regenerate</strong>)
                  to (re)build it on demand; Guardian also writes it when it
                  finishes an investigation.
                </li>
                <li>
                  <Term>Activity</Term> — the timeline of every step and finding
                  logged against the Issue. Filter by event type (action /
                  finding / note) and sort oldest- or newest-first.
                </li>
                <li>
                  <Term>Attack chain</Term> — an SVG causality diagram
                  of the attack (entry &#8594; pivots &#8594; action &#8594;
                  impact), drawn by Guardian when it resolves the investigation.
                  Use <strong>Regenerate</strong> on the tab to redraw it on
                  demand. It is rendered sandboxed, so it can&apos;t run code.
                </li>
                <li>
                  <Term>Relations</Term> — a STIX graph of the Issue&apos;s
                  indicators and how they relate to each other and to ATT&amp;CK
                  techniques, malware, campaigns, and threat-actors. The
                  relational companion to the causal Attack chain. Click{" "}
                  <strong>Generate</strong> (or <strong>Regenerate</strong>) on
                  the tab to draw it on demand — also sandboxed.
                </li>
              </ul>
              <p>
                <strong>Multi-source depth</strong> — when it works a
                case, Guardian doesn&apos;t stop at the XSOAR incident. It hunts
                the <Term>blast radius</Term> in your XSIAM telemetry with an XQL
                query (finding the other hosts and accounts a bad indicator
                touched — over a window wide enough to cover the incident, not
                just the last few minutes), writes its final{" "}
                <Term>verdict back to the XSOAR incident&apos;s war room</Term> as
                a pinned evidence entry so the disposition lives where your SOC
                works the case, and — for a true positive — attaches a{" "}
                <Term>recommended containment</Term> step (isolate host, disable
                account, block indicator, run a playbook) with the exact action
                ready for you to approve. Guardian only <em>recommends</em>; it
                never isolates a host or disables an account on its own —
                containment runs only when you approve it.
              </p>
              <p>
                The <Link href="/investigation/issues" className="link">Issues</Link>{" "}
                and <Link href="/investigation/cases" className="link">Cases</Link>{" "}
                lists are full-width, with summary stat cards and status
                filters; opening a Case shows its grouped Issues together, so a
                multi-Issue campaign reads as one investigation.
              </p>
              <p>
                <strong>Case-level diagrams</strong> — a Case detail is
                itself tabbed (Issues · Campaign · Attack chain · Relations). The
                case&apos;s <Term>Attack chain</Term> and{" "}
                <Term>Relations</Term> tabs draw <em>campaign-level</em>{" "}
                diagrams synthesized across <em>all</em> the issues in the case:
                one causal chain for the shared kill-chain, one STIX graph over
                the union of the case&apos;s indicators. Generate them on demand,
                the same way as the per-issue diagrams.
              </p>
              <p>
                <strong>Campaign rollup</strong> — the case&apos;s{" "}
                <Term>Campaign</Term> tab turns a pile of related incidents into
                one picture: the combined <Term>ATT&amp;CK techniques</Term> seen
                across the campaign, the <Term>shared infrastructure</Term> (the
                indicators that show up on more than one issue), the overall
                severity and verdict mix, and links to <Term>related cases</Term>{" "}
                (same campaign, escalation, reopen). Click <strong>Roll up
                campaign</strong> to (re)build it, or Guardian rolls it up
                automatically when it resolves an incident that belongs to a
                campaign — and it can suggest which prior case a new one belongs
                to, so a long-running campaign reads as one story.
              </p>
              <p>
                <strong>Export &amp; handoff</strong> — a finished
                investigation is portable. The Report tab and the Campaign tab
                each have an <strong>Export STIX 2.1</strong> download (a standard
                bundle of the incident/campaign, ATT&amp;CK techniques, indicators,
                and their relationships) that any threat-intel platform or SIEM can
                ingest. Guardian can also render the report three ways on request —
                an <em>executive</em> brief, the full <em>technical</em> write-up,
                or a machine-pasteable <em>IOC list</em>. And if you configure an
                outbound webhook (a SOAR/ticketing/chat ingress), Guardian can push
                the verdict + report + IOCs to it — but that handoff is{" "}
                <strong>opt-in and off by default</strong>, sends only to the URL{" "}
                <em>you</em> configure, and asks for your approval before every
                send; it shows you exactly what it would send first.
              </p>
            </SubSection>

            <SubSection icon="fingerprint" title="Indicators">
              <p>
                <Link href="/investigation/indicators" className="link">Indicators</Link>{" "}
                is Guardian&apos;s deduped record of every <Term>IoC</Term>{" "}
                (indicator of compromise) it sees — IPs, domains, URLs, file
                hashes, emails, CVEs, hosts, accounts. Deduped by value + type:
                re-seeing one updates its last-seen and links the new Issue rather
                than duplicating. Two things feed it:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  Guardian records each IoC it <Term>enriches</Term> during an
                  investigation (with its DBotScore + enrichment).
                </li>
                <li>
                  When it <Term>fetches an XSOAR case</Term>, the indicators the
                  SOAR already extracted are imported — the platform&apos;s
                  enrichment carries straight into Guardian.
                </li>
              </ul>
              <p>
                Click an indicator for its reputation, enrichment, and{" "}
                <strong>every Issue it appears in</strong> — how you spot the same
                actor or infrastructure across cases. Each Issue also has an{" "}
                <Term>Indicators</Term> tab listing just its own IoCs.
              </p>
            </SubSection>

            <SubSection icon="hub" title="Relations & attribution">
              <p>
                Guardian records typed <Term>relationships</Term> between
                indicators and other entities using the same{" "}
                <Term>STIX</Term> vocabulary the SOAR uses — so a domain{" "}
                <em>resolves-to</em> an IP, a URL <em>indicates</em> a malware
                family, an indicator <em>uses</em> an ATT&amp;CK technique, or an
                IoC is <em>attributed-to</em> a campaign or threat-actor. Because
                the verbs are STIX verbs, they round-trip with XSOAR&apos;s
                EntityRelationship model and MITRE ATT&amp;CK. Each indicator&apos;s
                detail page lists its relationships (source &#8594; verb &#8594;
                target).
              </p>
              <p>
                Those edges feed the Issue&apos;s <Term>Relations</Term> tab — an
                on-demand, layered graph of the Issue&apos;s indicators and how
                they relate. Generate it from the tab (a one-pass agent draw,
                about a minute), the same way you generate the Attack chain. The
                Attack chain answers <em>what happened in what order</em>; the
                Relations canvas answers <em>how the entities connect</em>.
              </p>
            </SubSection>

            <SubSection icon="dashboard_customize" title="Per-issue-type layouts">
              <p>
                The Issue detail adapts to the case kind — a kind-specific icon +
                accent and a one-line investigative <Term>focus</Term> (what to
                look at first for phishing vs malware vs lateral movement vs access
                violation), with IoC-type emphasis on the Indicators tab — so the
                layout surfaces the data that matters for each incident type.
              </p>
            </SubSection>
          </Section>

          <Section id="connectors" icon="cable" title="Connectors & Instances">
            <p>
              <Link href="/connectors" className="link">/connectors</Link> is
              where you manage two related concepts:
            </p>
            <ul className="list-disc pl-5 space-y-1.5 text-sm">
              <li>
                A <Term>connector</Term> is the catalogue entry — an id,
                config schema, secret slots, tool list, and the OCI
                container image that runs when an instance is created.
                Two flavors:{" "}
                <Code>origin: bundle</Code> (the 4 connectors shipped in
                the agent image: cortex-docs, web, xsoar, xsiam) and{" "}
                <Code>origin: user</Code> (connectors you upload via
                the marketplace).
              </li>
              <li>
                An <Term>instance</Term> is a configured copy of a
                connector — credentials bound, target URL set, ready
                to dispatch tool calls. Fresh installs come up with{" "}
                <Term>zero</Term> instances. Instance creation
                requires you to install the connector from the
                marketplace first; tool registration requires both
                installed AND at least one enabled instance. The
                install gate is functional, not decorative.
              </li>
            </ul>
            <p className="text-sm text-on-surface-variant">
              Universal container-mode: every instance runs as its own{" "}
              <Code>guardian-connector-&lt;id&gt;-&lt;name&gt;</Code>{" "}
              container, started by guardian-updater when the instance
              row is created. Tool calls flow from the agent&apos;s MCP
              to the container over loopback HTTPS.
            </p>

            <SubSection icon="siren" title="Cortex XSIAM connector">
              <p>
                The <Term>xsiam</Term> connector connects Guardian to a
                Cortex XSIAM tenant over the Cortex public API — the same
                add-an-instance flow as Cortex XSOAR. Create an instance with
                your tenant <strong>API host</strong> (the connector appends{" "}
                <Code>/public_api/v1</Code>), the <strong>API key ID</strong>{" "}
                (sent as <Code>x-xdr-auth-id</Code>), and the{" "}
                <strong>API key</strong> (the <Code>Authorization</Code> value).
                Mint these in XSIAM under Settings → Configurations → API Keys.
              </p>
              <p>
                It brings <strong>54 tools</strong>: investigation — XQL
                queries over the data lake, incidents / alerts / issues,
                assets, audit logs, datamodel, parsers — and{" "}
                <strong>EDR response</strong>: isolate / unisolate / scan /
                quarantine an endpoint, run a script or snippet, and blocklist
                a hash or IOC. Response actions write to your tenant, so they
                are <strong>approval-gated</strong> (you confirm at{" "}
                <Link href="/approvals" className="link">/approvals</Link>);
                the one destructive lookup deletion is blocked entirely. Ask
                in chat: &quot;run an XQL query for failed logins in the last
                hour&quot;, &quot;list the open XSIAM incidents&quot;, or
                &quot;isolate endpoint &lt;id&gt;&quot;.
              </p>
            </SubSection>

            <SubSection icon="dynamic_form" title="The instance creation form">
              <p>
                Click <strong>Create Instance</strong> on any installed
                connector card. The form has two sections:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <strong>Instance Identity</strong> — instance name +
                  optional description.
                </li>
                <li>
                  <strong>Configuration</strong> — one input per field
                  declared by the connector. The widget type is picked
                  by the connector schema (text, masked password,
                  multiline textarea, dropdown, radio buttons, chip
                  list, toggle switch). Required fields are marked with
                  a red asterisk; the <strong>Create Instance</strong>{" "}
                  button stays disabled until every required field has
                  a value.
                </li>
              </ul>
              <p className="text-sm leading-relaxed mt-2">
                Every field renders in one unified
                Configuration section in the order the connector
                declares them. Sensitive fields (API keys, passwords)
                render masked with an eye-toggle to reveal; non-sensitive
                fields (URLs, IDs, hostnames) render in clear text.
              </p>
              <p className="text-sm leading-relaxed mt-2">
                <strong>Version-aware fields:</strong> some connectors
                show fields that depend on an earlier choice. The XSOAR form
                leads with a <strong>Version</strong> dropdown — pick{" "}
                <Term>v6</Term> (on-prem) or <Term>v8</Term> (Cortex cloud) and
                the fields below adapt: the <Term>API key ID</Term> appears only
                for v8 (v6 authenticates with the API key alone). The form also
                exposes <Term>Playground / War Room ID</Term> — optional, but
                required to run commands (<Code>run_command</Code>) and the
                get/set/append list tools on either version.
              </p>
            </SubSection>

            <SubSection icon="check_circle" title="What happens when you click Create">
              <p className="text-sm leading-relaxed">
                The instance is saved immediately. For container-style
                connectors, guardian-updater then starts a dedicated
                container for that instance. Whatever happens, the form now
                tells you:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <strong>Success</strong> — the dialog closes and the new
                  instance appears in the <strong>Instances</strong> tab.
                </li>
                <li>
                  <strong>Couldn&apos;t create</strong> — a red banner
                  explains why (for example a duplicate name) and the form
                  stays open so you can fix it.
                </li>
                <li>
                  <strong>Still starting</strong> — an amber notice means the
                  instance was created but its container hasn&apos;t come up
                  yet. This is not an error: Guardian retries on its own
                  every few minutes, so the container comes online shortly.
                  Click <strong>Done</strong> to dismiss.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="alt_route" title="Running multiple instances (e.g. XSOAR v6 + v8)">
              <p className="text-sm leading-relaxed">
                You can enable <strong>more than one instance of the
                same connector at the same time</strong> — for example a
                Cortex XSOAR 6 (on-prem) tenant and a Cortex XSOAR 8 (cloud)
                tenant running side by side. Guardian routes each request to
                the right tenant on its own; you just talk about the tenant
                you mean.
              </p>
              <p className="text-sm leading-relaxed mt-2">
                To set this up on XSOAR:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  Create an instance for your v6 tenant. Give it a
                  distinct name (for example <Code>xsoar-v6</Code>) and pick{" "}
                  <strong>v6</strong> from the <strong>Version</strong>{" "}
                  dropdown on the form.
                </li>
                <li>
                  Create a second instance for your v8 tenant with a
                  different name (for example <Code>xsoar-v8</Code>) and pick{" "}
                  <strong>v8</strong> from the <strong>Version</strong>{" "}
                  dropdown.
                </li>
                <li>
                  <strong>Enable both</strong> instances. Each runs in its
                  own container, so they don&apos;t interfere with each other.
                </li>
              </ul>
              <p className="text-sm leading-relaxed mt-2">
                Once two (or more) instances of a connector are enabled, the
                agent picks the target tenant from your wording. Ask
                &ldquo;investigate the v6 case 12345&rdquo; and it works
                against your v6 tenant; ask about a v8 case and it targets v8.
                If a request is <strong>ambiguous</strong> about which tenant
                you mean, the agent asks which one rather than guessing — it
                never silently picks the wrong tenant. Connectors with a
                single enabled instance are unchanged: you keep talking to
                them exactly as before.
              </p>
            </SubSection>

            <SubSection icon="cable" title="The other connectors (xsoar · cortex-docs · web)">
              <p className="text-sm mb-2">
                Alongside the Cortex XSIAM connector (above), Guardian bundles
                three more — the XSOAR investigation gateway plus two read-only
                research surfaces:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>xsoar</Term> — Cortex XSOAR gateway, the
                  investigation surface (23 tools). Read/lifecycle:{" "}
                  <Code>list_incidents</Code>, <Code>get_incident</Code>,{" "}
                  <Code>get_war_room</Code>,{" "}
                  <Code>search_indicators</Code>, <Code>add_note</Code>,{" "}
                  <Code>add_entry</Code>, <Code>save_evidence</Code>,{" "}
                  <Code>update_incident</Code>, <Code>close_incident</Code>.
                  Action toolset:{" "}
                  <Code>run_command</Code>, <Code>enrich_indicator</Code>,{" "}
                  <Code>complete_task</Code>, <Code>get_list</Code> /{" "}
                  <Code>set_list</Code> / <Code>append_to_list</Code>,{" "}
                  <Code>create_incident</Code>, <Code>run_playbook</Code>.
                  Supports XSOAR 6 (on-prem) and XSOAR 8 / Cortex cloud —
                  the connector auto-detects the version from the instance
                  config. See <a href="#connectors" className="link">the
                  playground_id note below</a> for the command tools.
                </li>
                <li>
                  <Term>cortex-docs</Term> — official Palo Alto Networks
                  documentation search (case research). Tools include{" "}
                  <Code>search</Code>, <Code>suggest</Code>,{" "}
                  <Code>fetch_topic</Code>, <Code>fetch_toc</Code>,{" "}
                  <Code>deep_research</Code>.
                </li>
                <li>
                  <Term>web</Term> — evidence-gathering browsing via the
                  headless-browser sidecar. Tools include{" "}
                  <Code>navigate</Code>, <Code>get_text</Code>,{" "}
                  <Code>screenshot</Code>, <Code>extract_links</Code>.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="bolt" title="XSOAR command tools & the playground_id">
              <p>
                The XSOAR connector&apos;s action toolset lets you ask
                Guardian to <em>do</em> things, not just read. For example:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <em>&ldquo;which integrations are configured and what
                  commands can I run?&rdquo;</em> — list the configured
                  integration instances + each one&apos;s commands, via{" "}
                  <Code>list_integrations</Code>. The discovery
                  companion to <Code>run_command</Code>: Guardian learns which{" "}
                  <Code>!commands</Code> actually exist (ask{" "}
                  <em>&ldquo;list the VirusTotal commands&rdquo;</em> to also
                  see each command&apos;s arguments) instead of guessing. No{" "}
                  <Code>playground_id</Code> needed.
                </li>
                <li>
                  <em>&ldquo;why is my Splunk integration&apos;s fetch
                  failing?&rdquo;</em> — troubleshoot a configured integration
                  without reading XSOAR logs:{" "}
                  <Code>get_integration_status</Code> reports each instance&apos;s
                  enabled state + its last fetch error,{" "}
                  <Code>test_integration_instance</Code> re-runs the
                  Settings → Integrations <em>Test</em> button and surfaces the
                  exact error, and <Code>get_integration_fetch_history</Code>{" "}
                  reads the recent fetch runs (the failed-fetch source on
                  XSOAR 8). No <Code>playground_id</Code> needed.
                </li>
                <li>
                  <em>&ldquo;run <Code>!Print value=hi</Code> in
                  XSOAR&rdquo;</em> — any XSOAR command, via{" "}
                  <Code>run_command</Code>.
                </li>
                <li>
                  <em>&ldquo;enrich 8.8.8.8&rdquo;</em> — IP / URL / domain /
                  file / CVE reputation (DBotScore), via{" "}
                  <Code>enrich_indicator</Code>.
                </li>
                <li>
                  <em>&ldquo;add 1.2.3.4 to the blocklist&rdquo;</em> — manage
                  XSOAR Lists via <Code>get_list</Code> /{" "}
                  <Code>set_list</Code> / <Code>append_to_list</Code>.
                </li>
                <li>
                  <em>&ldquo;open an incident for this finding&rdquo;</em> /{" "}
                  <em>&ldquo;run the Phishing playbook on case 42&rdquo;</em> /{" "}
                  <em>&ldquo;did the playbook on case 42 finish cleanly?&rdquo;</em> /{" "}
                  <em>&ldquo;complete task 7 on case 42&rdquo;</em> —{" "}
                  <Code>create_incident</Code>, <Code>run_playbook</Code>,{" "}
                  <Code>get_playbook_state</Code> (per-task state +
                  ran-to-success + failed-task errors),{" "}
                  <Code>complete_task</Code>.
                </li>
              </ul>
              <p className="text-sm leading-relaxed mt-2">
                <strong>Setup:</strong> the three command tools
                (<Code>run_command</Code>, <Code>enrich_indicator</Code>,{" "}
                <Code>complete_task</Code>) run inside an XSOAR{" "}
                <strong>Playground / War Room</strong>, so they need a{" "}
                <Code>playground_id</Code> set on the XSOAR instance
                (Settings → Connectors → your XSOAR instance →{" "}
                <Code>playground_id</Code> field). To find it: open your
                Playground in XSOAR and copy the investigation id from the
                URL. The field is <strong>optional</strong> — the other 18
                tools work without it; if it&apos;s blank, the command tools
                return a clear &quot;playground_id not configured&quot; message.
              </p>
            </SubSection>

            <SubSection icon="inventory_2" title="Evidence on XSOAR 6 vs 8">
              <p>
                When the agent pins proof to a case&apos;s Evidence Board
                (<Code>save_evidence</Code>) and lists it back
                (<Code>search_evidence</Code>), the mechanics differ by XSOAR
                generation — but you call the same tools and the agent handles
                it. Both work end-to-end on both versions:
              </p>
              <ul className="list-disc pl-6 space-y-1 text-sm">
                <li>
                  <strong>XSOAR 6</strong> — evidence is saved as a formal
                  evidence record and listed straight from the evidence board.
                </li>
                <li>
                  <strong>XSOAR 8 / Cortex cloud</strong> — the public API
                  doesn&apos;t expose the evidence board the same way, so
                  Guardian marks the war-room entry with an{" "}
                  <Code>evidence</Code> tag and lists evidence by reading those
                  tagged entries. The result looks identical to you.
                </li>
              </ul>
              <p className="text-sm mt-2">
                Either way you get a compact list — id, the war-room entry it
                points at, who marked it, when, and any tags — so a reviewer can
                see what justified the verdict without scrolling the timeline.
              </p>
            </SubSection>

            <SubSection icon="lock" title="Secret storage">
              <p>
                Per-instance credentials live encrypted at rest under a
                <Code>GUARDIAN_SECRET_KEK</Code> envelope (AES-256-GCM).
                Secrets never leave the MCP container; the API redacts
                them as <Code>***</Code> on read. Rotating a credential
                writes a new envelope; the old one is GC&apos;d on the
                next sweep.
              </p>
            </SubSection>

            <SubSection icon="verified_user" title="Per-instance trusted flag">
              <p>
                Each instance config supports a <Code>trusted</Code>{" "}
                boolean. Default is <Code>false</Code>; set
                to <Code>true</Code> to mark the instance as a trusted
                lab connector — tool calls against it bypass the
                approval gate even if the manifest re-adds those tools to
                the gate list. Untrusted instances respect whatever the
                manifest says.
              </p>
              <p className="text-sm text-on-surface-variant mt-2">
                Set via PATCH:
              </p>
              <pre className="text-xs bg-surface-container-low p-3 rounded">
{`curl -X PATCH /api/v1/agent/instances/<id> \\
  -H 'Content-Type: application/json' \\
  -d '{"config": {"trusted": true}}'`}
              </pre>
              <p className="text-sm text-on-surface-variant mt-2">
                A UI checkbox affordance is on the roadmap. The
                manifest&apos;s <Code>humanRequired</Code> list gates the
                xsoar case-write tools (<Code>update_incident</Code>,{" "}
                <Code>close_incident</Code>, <Code>add_entry</Code>,{" "}
                <Code>add_note</Code>, <Code>save_evidence</Code>); a
                trusted lab instance bypasses that gate.
              </p>
            </SubSection>
          </Section>

          {/* Connector health page operator UX. */}
          <Section
            id="connector-health-ux"
            icon="monitor_heart"
            title="Connector Health"
          >
            <p>
              <Link
                href="/observability/connectors"
                className="link"
              >
                /observability/connectors
              </Link>{" "}
              is the per-instance state-machine view. While{" "}
              <a href="#connectors" className="link">/connectors</a> shows
              you the static catalog and credentials, this page shows the
              live state of each instance — last probe result, current
              state, and a reauth shortcut when credentials have expired.
            </p>

            <SubSection icon="account_tree" title="The five states">
              <Pre>{`enabled         ── healthy + reachable; tools dispatch normally
disabled        ── operator-paused; tools refuse to dispatch
failed          ── last probe returned an error; auto-retried with backoff
auth_required   ── 401 / token-expired; needs operator credential refresh
probed          ── transient state during an in-flight probe`}</Pre>
              <p>
                State transitions write{" "}
                <Code>connector_enabled</Code>,{" "}
                <Code>connector_disabled</Code>,{" "}
                <Code>connector_failed</Code>,{" "}
                <Code>connector_auth_required</Code>,{" "}
                <Code>connector_probed</Code> audit rows so the page can
                reconstruct full state history.
              </p>
            </SubSection>

            <SubSection icon="key" title="Reauth flow">
              <p>
                When an instance hits <Code>auth_required</Code> (the
                most common cause: an XSOAR API key revoked or rotated
                on the tenant), the row turns amber and a <Term>Reauth</Term>{" "}
                button appears. Click it → the setup form opens with that
                instance&apos;s fields prefilled (URL, auth ID, etc.) and
                only the secret slots empty. Submit → the instance flips
                back to <Code>enabled</Code> on the next probe (within
                30s).
              </p>
              <p>
                You can also reauth proactively from the connector detail
                drawer — useful before a long-running investigation where
                you&apos;d rather not have a token expire mid-run.
              </p>
            </SubSection>

            <SubSection icon="history" title="Probe history">
              <p>
                Each row expands into a <Term>last 50 probes</Term>{" "}
                table: timestamp, HTTP code, latency, error message (if
                any). Useful for distinguishing &quot;intermittent
                network blip&quot; from &quot;the connector has been
                degraded for 4 hours and we just noticed.&quot;
              </p>
            </SubSection>

            <Callout tone="info">
              Disabled instances are <em>operator-paused</em>, not broken —
              tools just refuse to dispatch. Use this when running
              maintenance on a downstream system you don&apos;t want the
              agent calling. Re-enable from the same page; nothing else
              changes.
            </Callout>
          </Section>

          <Section id="marketplace" icon="storefront" title="Marketplace">
            <p>
              The Marketplace tab on{" "}
              <Link href="/connectors" className="link">/connectors</Link>{" "}
              shows the connector catalogue: 3 bundle-shipped connectors
              (cortex-docs, web, xsoar)
              plus any user-uploaded connectors. Every card shows
              version, tool count, install state, origin (bundle or
              user), tags, and instances count.
            </p>
            <p>
              Fresh installs come up with all 3 bundle connectors in
              the catalogue marked &quot;available, not installed.&quot;
              No instances exist yet. The marketplace is the explicit
              first-step entry point — you install, then you create
              instances from the Instances tab.
            </p>

            <SubSection icon="install_desktop" title="Install + Uninstall">
              <p>
                Click a marketplace card → a drawer opens with the
                connector&apos;s tool list, config schema, and the
                Install button (or Installed badge + Uninstall button
                when already installed).
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Install Connector</Term> — flips the install
                  state row in{" "}
                  <Code>/app/data/marketplace.db</Code>. Makes the
                  connector AVAILABLE for instance creation. Does NOT
                  create an instance yet — that&apos;s a separate
                  step in the Instances tab where you wire up
                  credentials and config.
                </li>
                <li>
                  <Term>Uninstall</Term> — removes the install state
                  row. Refuses with a 409 toast if any instances
                  exist for the connector — delete the instances
                  first. The connector stays in the catalogue (bundle
                  ones are image-baked, can&apos;t actually be
                  removed); future Install clicks succeed without
                  re-downloading anything.
                </li>
              </ul>
              <p className="text-sm">
                Install state is a real gate: instance creation
                against an uninstalled connector returns 409{" "}
                <Code>connector_not_installed</Code>. Both actions
                emit audit events (<Code>marketplace_install</Code> /{" "}
                <Code>marketplace_uninstall</Code>) visible in{" "}
                <Link href="/observability/events" className="link">
                  /observability/events
                </Link>.
              </p>
            </SubSection>

            <SubSection icon="dns" title="Emulated services">
              <p>
                The marketplace has two kinds of entry: <Term>connectors</Term>{" "}
                (integrations the agent calls) and <Term>services</Term>{" "}
                (emulated upstreams reached by an <em>external</em> system, not
                the agent). Services carry a <Term>Service</Term> badge and live
                under the <Term>Services</Term> filter. They advertise no agent
                tools — their card shows &quot;Emulated&quot; instead of a tool
                count, and a service instance has no Test Connection (the agent
                never calls it).
              </p>
              <p className="text-sm">
                The first service is <Term>Splunk (Emulated)</Term>. It speaks
                the splunkd REST API the Cortex XSOAR <Code>SplunkPy</Code>{" "}
                integration uses, returning simulated notable events — so you can
                run SplunkPy <em>fetch-incidents</em>, <Code>!splunk-search</Code>,
                and the Indicator Hunting playbook end-to-end with no real Splunk
                server. To wire it up:
              </p>
              <ol className="list-decimal pl-5 space-y-1.5 text-sm">
                <li>Install <Term>Splunk (Emulated)</Term>, then create an instance (accepted username, default <Code>admin</Code>; password optional — blank accepts any).</li>
                <li>Guardian starts the service container and publishes host port <Code>8089</Code> on the Guardian host.</li>
                <li>On your Cortex XSOAR server, configure the standard SplunkPy integration: host = your Guardian host, port = <Code>8089</Code>, the matching username/password, and <Code>unsecure=true</Code> (the mimic serves a self-signed cert by default, just like an on-prem splunkd).</li>
                <li>Test the SplunkPy instance (green), then run <Code>!splunk-search query=&quot;search `notable`&quot;</Code> or enable fetch to pull simulated Splunk notable incidents.</li>
              </ol>
              <p className="text-sm">
                Note: the XSOAR host must be able to reach tcp/8089 on the
                Guardian host (a firewall rule may be required). For a
                production-faithful TLS posture, mount an operator cert via{" "}
                <Code>SPLUNK_MIMIC_TLS_CERT</Code> / <Code>SPLUNK_MIMIC_TLS_KEY</Code>{" "}
                and leave SplunkPy verifying.
              </p>
            </SubSection>

            <SubSection icon="upload_file" title="Upload your own connector">
              <p>
                You can upload custom <Code>connector.yaml</Code> files
                to add your own connectors to the marketplace alongside
                the 5 bundle-shipped ones. Workflow:
              </p>
              <ol className="list-decimal pl-5 space-y-1.5 text-sm">
                <li>
                  Build + publish your connector container image to any
                  OCI registry guardian-updater can pull from (GHCR,
                  Docker Hub, ECR, your private registry, etc.). The
                  image must run the{" "}
                  <Code>guardian-connector-runtime</Code> entrypoint
                  (FROM <Code>ghcr.io/kite-production/guardian-connector-runtime:latest</Code>{" "}
                  is the supported base — see{" "}
                  <Code>bundles/spark/connectors/_runtime/Dockerfile</Code>{" "}
                  for the pattern).
                </li>
                <li>
                  Write your <Code>connector.yaml</Code> with{" "}
                  <Code>runtimeMapping.style: container</Code> + an{" "}
                  <Code>image</Code> field carrying the published
                  reference (e.g.{" "}
                  <Code>image: ghcr.io/your-org/your-connector:v1.0</Code>).
                  See{" "}
                  <Code>bundles/spark/connectors/connector.schema.json</Code>{" "}
                  for the full schema. The schema validator runs at
                  upload time + at boot; drift fails fast with a
                  path-into-the-field error.
                </li>
                <li>
                  Click the{" "}
                  <Term>Upload Connector</Term> button on the
                  Marketplace tab → file picker → select your YAML →
                  submit. (Or use curl with bearer{" "}
                  <Code>MCP_TOKEN</Code>:{" "}
                  <Code>curl -F connector_yaml=@your-connector.yaml https://&lt;host&gt;:8080/api/v1/marketplace/upload</Code>.)
                </li>
                <li>
                  The connector appears in the marketplace with a{" "}
                  <Term>Custom</Term> badge. Install it, then create
                  an instance from the Instances tab. Same flow as
                  any bundle connector from there on.
                </li>
              </ol>
              <p className="text-sm text-on-surface-variant">
                <Term>Deleting a custom connector.</Term> Open the
                connector&apos;s card on the Marketplace tab — a{" "}
                <Term>Delete</Term> button appears for{" "}
                <Term>Custom</Term> (user-uploaded) connectors. It
                permanently removes the connector&apos;s uploaded
                definition (a confirmation step guards it, since this
                can&apos;t be undone). Delete its instances first from
                the Instances tab — Delete refuses while any instance
                still exists and tells you so. Bundle connectors have
                no Delete button: they&apos;re image-baked and
                can&apos;t be removed at runtime — use{" "}
                <Term>Uninstall</Term> to hide them from instance
                creation instead.
              </p>
            </SubSection>

            <SubSection icon="smart_toy" title="Ask the agent to manage the marketplace">
              <p>
                The chat agent has 4 marketplace tools in its
                catalogue:{" "}
                <Code>marketplace_list</Code> (read-only catalogue +
                install state),{" "}
                <Code>marketplace_install(connector_id)</Code>,{" "}
                <Code>marketplace_uninstall(connector_id)</Code>, and{" "}
                <Code>connector_upload(yaml_content)</Code>. So you
                can say things like &ldquo;install the web
                connector,&rdquo; &ldquo;what connectors do I have
                installed?,&rdquo; or &ldquo;upload this connector
                YAML&rdquo; and the agent will do the catalogue
                management.
              </p>
              <p className="text-sm">
                Instance creation stays operator-only by design — the
                instance form takes credentials (API keys, service
                URLs, etc.), and the agent credential guardrail
                keeps the agent away from anything that writes a
                secret. The agent can hand you a fully-installed
                connector but you fill in the credentials yourself.
              </p>
            </SubSection>

            <SubSection icon="apps" title="Container-style vs module-style connectors">
              <p>
                Connectors come in two runtime flavors, set by{" "}
                <Code>connector.yaml:runtimeMapping.style</Code>:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>module</Term> (legacy) — connector code runs
                  in-process inside the agent. Tool calls are direct
                  Python function invocations. No bundle connector
                  ships module-style today.
                </li>
                <li>
                  <Term>container</Term> (used by every bundle connector
                  today) — each
                  instance gets its own Docker container that{" "}
                  guardian-updater starts when you create the instance and
                  stops when you delete it. The agent&apos;s tool-dispatch
                  loader becomes a routing proxy that forwards calls over
                  MCP-over-HTTP to{" "}
                  <Code>http://guardian-connector-&lt;id&gt;-&lt;name&gt;:9000</Code>.
                  Crash isolation, resource isolation, independent
                  versioning. See the{" "}
                  <Link
                    href="/help/architecture#connector-containers"
                    className="link"
                  >
                    Connector Containers architecture section
                  </Link>{" "}
                  for the full design.
                </li>
              </ul>
              <p className="text-sm text-on-surface-variant/80">
                Operator-facing experience is identical regardless of
                style — Install + Create Instance work the same way. The
                only operational difference: container-style connectors
                need <Code>guardian-updater</Code> running and need pull
                access to the connector&apos;s GHCR image. For
                disconnected installs, see the{" "}
                <Link
                  href="/help/architecture#guardian-updater"
                  className="link"
                >
                  guardian-updater
                </Link>{" "}
                section&apos;s &quot;cached&quot; pull-fallback note.
              </p>
            </SubSection>

            <SubSection icon="toggle_on" title="Per-instance tool toggle">
              <p>
                Each connector ships a defined set of tools the agent
                can call. By default every tool the connector exposes
                is enabled. For instances with larger tool catalogs
                (the XSOAR connector ships the full case-investigation
                family), you can selectively disable tools to bound the
                agent&apos;s catalog noise OR to lock down destructive
                case-write actions.
              </p>
              <ol className="list-decimal pl-5 space-y-1.5 text-sm">
                <li>
                  Expand any instance row in <Term>Instances</Term> tab,
                  click <Term>Show Tools</Term>.
                </li>
                <li>
                  A grid of checkboxes appears, one per tool. The
                  header shows &quot;N/M tools enabled for the agent.&quot;
                </li>
                <li>
                  Uncheck a tool to hide it from the agent. The change
                  PATCH-es to the instance, audit-logs as{" "}
                  <Code>instance_tool_toggle</Code>, and takes effect
                  on the next tool call.
                </li>
                <li>
                  Mass actions: <Term>Enable all</Term> /{" "}
                  <Term>Disable all</Term> apply to every tool the
                  connector ships.
                </li>
              </ol>
              <p className="text-sm">
                Use cases: hide{" "}
                <Code>xsoar_close_incident</Code> (high-impact),
                disable the case-write tools (<Code>xsoar_update_incident</Code>,
                <Code>xsoar_add_entry</Code>) on a read-only deployment,
                trim agent context budget by disabling tools you
                never use.
              </p>
              <p className="text-sm text-on-surface-variant">
                Toggle state is per-instance. Two XSOAR tenants (two
                instances) can have different sets of tools enabled
                — the agent picks the right set based on which
                instance handles the request.
              </p>
            </SubSection>

            <SubSection icon="dashboard" title="Instance state + tabs">
              <p>
                The Instances tab next to Marketplace lists configured
                connector instances with health status and last-edit
                timestamps. Clicking an instance opens a config panel
                where you can rotate credentials or edit the
                wire-up. The agent automatically picks the right instance
                when you mention a system by name in chat (&quot;check
                the prod tenant&quot; → primary-xsoar).
              </p>
              <p className="text-sm">
                Install state has two sources today, union&apos;d server-side:
              </p>
              <ul className="list-disc pl-5 space-y-1 text-sm">
                <li>
                  Explicit operator clicks (the JSON store written by the
                  Install button).
                </li>
                <li>
                  Instance presence — any connector with ≥1 instance
                  counts as installed even without the explicit ack,
                  so the marketplace card shows
                  &quot;Installed&quot; without the operator ever
                  clicking the button.
                </li>
              </ul>
            </SubSection>
          </Section>

          {/* Plugins page operator workflow. */}
          <Section id="plugins-ux" icon="extension" title="Plugins">
            <p>
              Plugins are vendor-shipped or operator-authored bundles
              that contribute extra tools, skills, hooks, or agent
              definitions to the runtime without touching the core
              Guardian image. View installed plugins at{" "}
              <Link href="/plugins" className="link">/plugins</Link>.
            </p>

            <SubSection icon="inventory_2" title="What a plugin can contribute">
              <p>
                Each plugin&apos;s manifest declares any of:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>tools</Term> — additional MCP tools surfaced
                  through a plugin-namespaced prefix
                  (<Code>plugin:&lt;name&gt;:&lt;tool&gt;</Code>).
                </li>
                <li>
                  <Term>skills</Term> — markdown skills loaded into the
                  catalog and toggleable from{" "}
                  <Link href="/skills" className="link">/skills</Link>{" "}
                  like any other.
                </li>
                <li>
                  <Term>hooks</Term> — pre-installed hook definitions
                  (see <a href="#hooks-ux" className="link">Hooks</a>).
                  Operator can disable individually.
                </li>
                <li>
                  <Term>agents</Term> — agent definitions that show up
                  on <a href="#agents-ux" className="link">/agents</a>{" "}
                  with the <Term>plugin</Term> origin badge.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="install_desktop" title="Install + reload">
              <p>
                The <Term>Install</Term> button takes a plugin URL or
                manifest YAML upload. The plugin is staged into{" "}
                <Code>/app/runtime/plugins/&lt;name&gt;/</Code> and the
                runtime reloads contributions automatically. Reload also
                fires manually via the <Term>Reload</Term> button at the
                top of the page — useful when you&apos;ve edited a plugin
                in place during development.
              </p>
              <p>
                Reloads write a <Code>plugins_reloaded</Code> audit row
                with the contribution counts (tools / skills / hooks /
                agents added or removed). Find them at{" "}
                <Link
                  href="/observability/events?action=plugins_reloaded"
                  className="link"
                >
                  /observability/events?action=plugins_reloaded
                </Link>
                .
              </p>
            </SubSection>

            <SubSection icon="conflict" title="Overwrite policy">
              <p>
                If two sources declare the same agent definition name
                (e.g., a plugin and an operator-authored agent), the{" "}
                <Term>operator</Term> source wins — operator-owned
                customizations are never silently overwritten by a
                plugin reload. Plugin-vs-plugin conflicts surface as a
                warning toast on the plugins page; you pick which source
                to keep.
              </p>
            </SubSection>

            <Callout tone="warn">
              Plugins run inside the same MCP container as the rest of
              Guardian — they can call any internal API the MCP can
              reach. Treat plugin installation with the same care as
              installing a vendor library: review the manifest, scope
              the tools you allow, and check audit rows after the first
              run to confirm only expected calls happened.
            </Callout>

            <SubSection
              icon="inventory_2"
              title="Distributable plugins"
            >
              <p>
                The <Code>/plugins</Code> page above covers the older
                filesystem-discovered plugin system. A parallel surface
                lives at{" "}
                <Link
                  href="/observability/plugins"
                  className="link"
                >
                  /observability/plugins
                </Link>{" "}
                for <strong>pip-installable</strong> plugins that target
                one of five reserved entry-point groups
                (<Code>guardian.skills</Code>,{" "}
                <Code>guardian.connectors</Code>,{" "}
                <Code>guardian.hooks</Code>,{" "}
                <Code>guardian.scanners</Code>,{" "}
                <Code>guardian.providers</Code>).
              </p>
              <p>
                The page hosts:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  An <Term>install form</Term> at the top — paste a pypi
                  name, a <Code>git+https://...</Code> URL, or a local
                  path; click Install. The server runs{" "}
                  <Code>pip install --user --quiet &lt;spec&gt;</Code>{" "}
                  in the agent container and refreshes the catalog
                  below.
                </li>
                <li>
                  Per-row <Term>Uninstall buttons</Term> on each
                  discovered plugin. Click → confirm → server runs{" "}
                  <Code>pip uninstall -y &lt;dist&gt;</Code> and
                  refreshes.
                </li>
              </ul>
              <p>
                Both actions audit via the standard event log; filter at{" "}
                <Link
                  href="/observability/events?action=plugin_install"
                  className="link"
                >
                  /observability/events?action=plugin_install
                </Link>{" "}
                or{" "}
                <Link
                  href="/observability/events?action=plugin_uninstall"
                  className="link"
                >
                  ?action=plugin_uninstall
                </Link>
                .
              </p>
              <Callout tone="info">
                The cross-language bridge is closed — plugin
                handlers in the <Code>guardian.hooks</Code> group are{" "}
                <strong>callable</strong> from{" "}
                <Link href="/settings/hooks" className="link">
                  /settings/hooks
                </Link>{" "}
                via the <Term>plugin</Term> transport (Add hook →
                pick the plugin handler from the dropdown → fill the
                JSON config). Install/uninstall hot-reloads the
                plugin-hook cache; other contribution types (skills,
                connectors, providers, scanners) still need a
                guardian-agent restart to wire into their respective
                registries.
              </Callout>
            </SubSection>
          </Section>

          {/* Hooks management UX. */}
          <Section id="hooks-ux" icon="webhook" title="Hooks">
            <p>
              Hooks let you attach policy actions to runtime events — get
              a Slack notification when a Tier-3 tool runs, block a
              specific tool from firing in production, mirror tool
              outputs to an external SIEM. Manage them at{" "}
              <Link href="/settings/hooks" className="link">
                /settings/hooks
              </Link>
              .
            </p>
            <p>
              <strong>The page</strong> opens with summary cards
              (total · enabled · disabled · fail-closed), an event-group +
              name filter over the hook list, and slimmed hook rows showing
              the event, transport, and a fail-closed flag at a glance. The
              create/edit drawer groups its fields into tabs —{" "}
              <Term>Metadata</Term>, <Term>Matching</Term>,{" "}
              <Term>Transport</Term>, <Term>Execution</Term> — so a hook is
              configured one concern at a time.
            </p>

            <SubSection icon="bolt" title="The event taxonomy">
              <p>
                Every hook subscribes to one of these event names; the
                fire-site is fixed in the chat lifecycle so you know
                exactly when a handler runs:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Code>PreToolUse</Code> — before any tool call.
                  Handler can <em>deny</em> the call, transforming the
                  agent&apos;s next turn into an error message instead.
                </li>
                <li>
                  <Code>PostToolUse</Code> — after a tool call returns
                  (success or failure). Read-only side effects only.
                </li>
                <li>
                  <Code>UserPromptSubmit</Code> — when the operator
                  sends a chat message. Handler can rewrite or annotate
                  the prompt.
                </li>
                <li>
                  <Code>Notification</Code> — when the agent emits a
                  notification event (approval requested, job run
                  complete). Common hook target for Slack mirrors.
                </li>
                <li>
                  <Code>Stop</Code> / <Code>SubagentStop</Code> — at the
                  end of a chat turn / subagent completion. Useful for
                  end-of-run summaries.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="security" title="Guardian IR built-ins">
              <p>
                Two built-in hooks ship for the incident-response workflow —
                install either from the <Term>Transport → Built-in</Term>{" "}
                dropdown with a tool glob; no code, no subprocess:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Block close without verdict</Term> —{" "}
                  <Code>PreToolUse</Code> on{" "}
                  <Code>xsoar_close_incident</Code>. Denies the close when the
                  Guardian Issue tracking that incident has no recorded
                  disposition — either the structured verdict or the
                  legacy <Code>VERDICT:</Code> line — so no incident is closed
                  without one. Use <Code>failurePolicy: block</Code>{" "}
                  (fail-closed). Conservative by default — closes of incidents
                  Guardian isn&apos;t tracking pass through; flip{" "}
                  <Term>block_if_untracked</Term> for strict mode.
                </li>
                <li>
                  <Term>Flag malicious indicator</Term> —{" "}
                  <Code>PostToolUse</Code> on{" "}
                  <Code>xsoar_enrich_indicator</Code>. When an enrichment
                  returns a DBotScore of 3 (malicious), injects a confirmed-bad
                  flag into the agent&apos;s next turn — nudging it to record the
                  indicator and recommend containment. Informational only
                  (can&apos;t block); use <Code>failurePolicy: warn</Code>.
                </li>
              </ul>
              <p>
                Both read only investigation metadata (or inspect the tool
                result) and never touch a stored secret — they sit on the
                catalog side of the credential guardrail.
              </p>
            </SubSection>

            <SubSection icon="add_circle" title="Installing a hook">
              <p>
                Click <Term>New hook</Term> on{" "}
                <Link href="/settings/hooks" className="link">
                  /settings/hooks
                </Link>
                . The form asks for:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Name</Term> — human label shown in audit rows
                  and the hooks list.
                </li>
                <li>
                  <Term>Event</Term> — which fire-site to attach to (one
                  of the seven above).
                </li>
                <li>
                  <Term>Matcher</Term> — optional filter to scope when
                  the handler runs. Tool patterns
                  (<Code>xsoar_*</Code>), session tags
                  (<Code>session.tag:prod</Code>), or actor filters
                  (<Code>actor:user:*</Code>).
                </li>
                <li>
                  <Term>Transport</Term> — how the handler runs. Four
                  options:
                  <ul className="list-disc pl-5 mt-1 space-y-1">
                    <li>
                      <Term>Built-in</Term> — pick a named
                      handler that ships with the agent image (e.g.,
                      Slack approval). Form fields appear automatically
                      from the built-in&apos;s config schema. No
                      subprocess, no HTTP — runs in-process. Recommended
                      starter.
                    </li>
                    <li>
                      <Term>HTTP webhook</Term> — POST the event payload
                      to a URL you operate. Right when you have your own
                      policy service / SIEM mirror / Slack receiver.
                    </li>
                    <li>
                      <Term>Shell command</Term> — runtime spawns the
                      command with the event payload on stdin, parses
                      stdout as the handler outcome. Right when policy
                      lives in a local script.
                    </li>
                    <li>
                      <Term>Agent tool</Term> — reserved. Plugin
                      handlers (see below) cover the
                      vendor-distributed path; this discriminator is
                      kept on the form for forward compatibility.
                    </li>
                  </ul>
                </li>
              </ul>
              <p>
                On submit, the runtime writes the hook config and emits
                a <Code>hook_upsert</Code> audit row. The hook is
                immediately active — no restart needed.
              </p>
            </SubSection>

            <SubSection id="hooks-builtin" icon="extension" title="Built-in handlers">
              <p>
                Built-in handlers are policy primitives that ship with
                every Guardian deployment. Pick one from the dropdown,
                fill its config form, save. The agent calls the handler
                in-process on each matching event — no subprocess to
                manage, no HTTP service to operate.
              </p>
              <p>
                The current built-in catalogue:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Slack approval</Term> — On{" "}
                  <Code>PreToolUse</Code>, POSTs the tool details to a
                  webhook receiver you operate. Your receiver pings
                  Slack with Approve/Deny buttons, waits for an analyst
                  click, returns the decision. Guardian blocks the tool
                  on <Code>deny</Code> and lets it through on{" "}
                  <Code>allow</Code>. Config: webhook URL + optional
                  auth header.
                </li>
              </ul>
              <p>
                The catalogue is enumerable at runtime via{" "}
                <Code>GET /api/agent/hooks/builtins</Code> — that
                endpoint reflects exactly what the current install
                offers. Additional built-ins (memory-injection, pre-
                compact warning, cost-warn-over-budget) ship in image
                updates and appear automatically in the form&apos;s
                dropdown.
              </p>
              <Callout tone="info">
                Built-ins run with the agent&apos;s privileges. They
                can read tool args and call the agent&apos;s services
                directly. Operators who need stricter isolation should
                continue using the <Code>http</Code> transport, which
                forces the handler into a separate process boundary.
              </Callout>
            </SubSection>

            <SubSection
              id="hooks-plugin"
              icon="inventory_2"
              title="Plugin handlers"
            >
              <p>
                A fifth transport — <Term>Plugin handler</Term> — wires
                in handlers contributed by pip-installable Python
                packages targeting the <Code>guardian.hooks</Code>{" "}
                entry-point group. Discovery + lifecycle for those
                packages happens at{" "}
                <Link
                  href="/observability/plugins"
                  className="link"
                >
                  /observability/plugins
                </Link>{" "}
                (see the Plugins section); the hook form picks them up
                automatically once the package is pip-installed and the
                agent restarts.
              </p>
              <p>
                In the Add-hook form, picking <Term>Plugin handler</Term>{" "}
                from the transport dropdown surfaces a fetched dropdown
                of currently-discovered handler names + a generic JSON
                config textarea + an optional per-hook timeout in
                seconds. Schema for the config is plugin-defined — TS
                can&apos;t introspect Python entry-points, so the form
                ships a JSON editor and the plugin author documents
                their own contract.
              </p>
              <p>
                Click <Term>Refresh</Term> in the section header to
                re-walk entry-points (useful when you just installed a
                plugin in a different tab and want it to appear without
                a full page reload). Each invocation audits as{" "}
                <Code>plugin_hook_invoked</Code> with handler name +
                outcome category at{" "}
                <Link
                  href="/observability/events?action=plugin_hook_invoked"
                  className="link"
                >
                  /observability/events?action=plugin_hook_invoked
                </Link>
                .
              </p>
              <Callout tone="warn">
                Plugin handlers run in the MCP process with full agent
                privileges — same trust boundary as installing a vendor
                library. Review the plugin source before{" "}
                <Code>pip install</Code>. Use the timeout field
                aggressively for handlers you don&apos;t fully trust:
                MCP caps invocation at 60s server-side, but a tighter
                bound prevents a misbehaving handler from sitting on a
                hook fire.
              </Callout>
            </SubSection>

            <SubSection icon="toggle_on" title="Lifecycle controls">
              <p>
                Each hook row has a toggle (enabled/disabled), an{" "}
                <Term>Edit</Term> button (re-opens the form with current
                values), and a <Term>Delete</Term> button. Disabled
                hooks stay in the list — useful to pause a noisy hook
                without losing its config. Edits write{" "}
                <Code>hook_enabled</Code> /{" "}
                <Code>hook_disabled</Code> /{" "}
                <Code>hook_deleted</Code> audit rows.
              </p>
            </SubSection>

            <SubSection icon="article" title="Audit + dispatch trail">
              <p>
                Every hook fire writes a <Code>hook_dispatched</Code>{" "}
                audit row with the hook name, event, matcher hit, and
                handler outcome (allowed / denied / errored). Filter on{" "}
                <Code>action:hook_dispatched</Code> in{" "}
                <Link href="/observability/events" className="link">
                  /observability/events
                </Link>{" "}
                to confirm a hook is firing and (for deny hooks) what
                got blocked.
              </p>
            </SubSection>

            <Callout tone="info">
              Hooks load <em>fresh</em> from disk on each fire, not from
              an in-memory cache — so editing a hook&apos;s handler
              command takes effect on the very next event, no reload
              needed. This is intentional for fast policy iteration; see{" "}
              <Link
                href="/help/architecture#design-decisions"
                className="link"
              >
                Architecture &rarr; Design Decisions
              </Link>{" "}
              for the trade-offs.
            </Callout>

            <SubSection icon="bug_report" title="Debugging hooks">
              <p>
                When a hook isn&apos;t doing what you expect, walk this
                short ladder:
              </p>
              <ol className="list-decimal pl-5 space-y-1.5 text-sm">
                <li>
                  Open{" "}
                  <Link href="/observability/events" className="link">
                    /observability/events
                  </Link>{" "}
                  and filter by <Code>action:hook_dispatched</Code>. Every
                  fire writes a row with the hook id, event
                  name, matched payload, and the returned decision. No
                  rows for your hook means the matcher didn&apos;t hit
                  (check toolGlob / triggerPrefix) or the
                  event itself never fired. Tool globs are{" "}
                  <Term>separator-insensitive</Term>: a glob of{" "}
                  <Code>xsoar_close_incident</Code> matches the same tool
                  whether the model invokes it as{" "}
                  <Code>xsoar_close_incident</Code> or in the dotted
                  connector form <Code>xsoar.close_incident</Code> — so you
                  no longer need to author both. The same rule applies to{" "}
                  job permission-policy globs and subagent allow/deny scopes.
                </li>
                <li>
                  Look for <Code>hook_denied</Code> (the hook actively
                  denied) and <Code>hook_error</Code> (the transport
                  raised). <Code>hook_error</Code> rows carry the
                  stderr / response body / exception trace in the{" "}
                  <Code>error</Code> metadata field — that&apos;s where
                  to start when a Slack webhook 404s, when a shell
                  script segfaults, or when a builtin throws.
                </li>
                <li>
                  Use the dry-run endpoint to fire a hook against a
                  synthetic payload:{" "}
                  <Code>POST /api/agent/hooks/&lt;id&gt;/test</Code>{" "}
                  with <Code>{`{ "payload": {...} }`}</Code> in the
                  body. The hook runs but no agent state changes; the
                  response carries the same <Code>HookResult</Code>{" "}
                  shape the real fire-site would see. Use this to
                  iterate on matchers + handlers without driving the
                  agent through a real tool call.
                </li>
                <li>
                  Toggle <Term>Enabled</Term> off on{" "}
                  <Link href="/settings/hooks" className="link">
                    /settings/hooks
                  </Link>{" "}
                  to remove a hook from the pipeline without deleting
                  its config. Useful when a hook is producing too many
                  denials and you want to confirm the agent path works
                  without it.
                </li>
                <li>
                  Check the <Term>Failure policy</Term> column. A hook
                  with <Code>block</Code> failure policy that hits an
                  error denies the tool — operators sometimes set this
                  too aggressively on observability hooks. Switch to{" "}
                  <Code>warn</Code> or <Code>allow</Code> for
                  best-effort notification handlers; reserve{" "}
                  <Code>block</Code> for true policy enforcers.
                </li>
              </ol>
            </SubSection>
          </Section>

          <Section id="approvals" icon="fact_check" title="Approvals">
            <p>
              Approvals gate the tools where the agent is changing
              <em> its own runtime state</em> — schedules, persona, settings,
              notifications — plus the XSOAR tools that <em>write to a
              live case</em> (update, close, war-room entries, evidence).
              Read-only connector calls (case reads, indicator searches,
              documentation lookups) do <em>not</em> require approval —
              those are explicit operator intent at chat level.
            </p>
            <p>
              When a gated call fires, it lands in{" "}
              <Link href="/approvals" className="link">/approvals</Link> with
              the agent name, tool, args, and risk tier.
            </p>

            <SubSection icon="check_circle" title="What requires approval">
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Self-modification</Term>: <Code>jobs_create</Code>,
                  <Code> jobs_update</Code>, <Code>jobs_run_now</Code>,
                  <Code> personality_update</Code>, <Code>personality_patch</Code>,
                  <Code> settings_update</Code>,
                  <Code> notifications_dismiss</Code>,{" "}
                  <Code>approvals_resolve</Code>.
                </li>
                <li>
                  <Term>Destructive</Term>: <Code>jobs_delete</Code>,
                  <Code> skills_delete</Code>, <Code>personality_reset</Code>,
                  <Code> settings_reset</Code>, <Code>instances_delete</Code>,
                  <Code> providers_delete</Code>, plus the XSOAR case-write
                  tools (<Code>xsoar_update_incident</Code>,{" "}
                  <Code>xsoar_close_incident</Code>,{" "}
                  <Code>xsoar_add_entry</Code>, <Code>xsoar_add_note</Code>,{" "}
                  <Code>xsoar_save_evidence</Code>). Same gate; UI shows a
                  red banner.
                </li>
                <li>
                  <Term>Credentials</Term>: <Code>api_keys_create</Code>,
                  <Code> api_keys_rotate</Code>, <Code>api_keys_revoke</Code>.
                  Same gate; UI requires typing CONFIRM in a text field
                  before the Approve button activates.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="block" title="What does NOT require approval">
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>XSOAR reads</Term> — <Code>xsoar_list_incidents</Code>,{" "}
                  <Code>xsoar_get_incident</Code>,{" "}
                  <Code>xsoar_get_war_room</Code>,{" "}
                  <Code>xsoar_search_indicators</Code>. Run inline.
                </li>
                <li>
                  <Term>Docs &amp; web</Term> — documentation search,
                  evidence-gathering browsing. Run inline.
                </li>
                <li>
                  <Term>Reads</Term> — anything classified as a read query
                  (the agent&apos;s view of its own state, audit search, etc).
                </li>
              </ul>
              <p className="text-sm text-on-surface-variant mt-2">
                Per-instance opt-in to gating exists via the connector
                instance&apos;s <Code>trusted: false</Code> flag — see the{" "}
                <Link href="#connectors" className="link">Connectors</Link>{" "}
                section. By default new instances are untrusted-but-ungated
                (manifest-driven), letting operators tune per-deployment.
              </p>
            </SubSection>

            <SubSection icon="timer" title="Lifecycle">
              <p>
                Pending approvals time out server-side after 5 minutes —
                the chat unblocks with an error. Resolved approvals stay
                in the history tab indefinitely (subject to audit-log
                retention). The sidebar shows a count badge for pending
                approvals so you don&apos;t miss them while in another
                tab.
              </p>
              <Callout tone="info">
                Today, you click Approve on the <Code>/approvals</Code>{" "}
                page; the chat-side inline approval card is on the
                roadmap. If the timeout fires before you approve, re-issue
                the chat command — the agent will create a fresh request.
              </Callout>
            </SubSection>

            <SubSection icon="record_voice_over" title="Preamble + key args">
              <p>
                Before any approval card lands in the chat thread, you
                always see context for what&apos;s about to happen.
                Two layers cooperate to guarantee this:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Model narration (preferred)</Term> — the system
                  prompt instructs the agent to write a short
                  &quot;here&apos;s what I&apos;m about to do and
                  why&quot; sentence before any gated tool call. When
                  the model complies, that text streams into the chat
                  thread first; the approval card lands below it.
                </li>
                <li>
                  <Term>Server-side preamble (fallback)</Term> — when
                  the model is silent (function call only, no
                  accompanying text), the chat-route synthesizes a
                  one-line{" "}
                  <Code>I&apos;ll call `tool_name` with key=value, …</Code>
                  {" "}preamble per pending tool call and streams it
                  before the approval card. Up to four args are surfaced
                  (preferring human-meaningful keys like name, cron, url,
                  query, instance_id); secret-looking keys (api_key,
                  password, token, …) are hidden.
                </li>
                <li>
                  <Term>Approval-card &quot;Will be called with&quot; panel</Term>
                  {" "}— the card itself shows the same key=value summary
                  above the Approve / Deny buttons. Defense-in-depth:
                  even if the preamble didn&apos;t render, the card is
                  never opaque. Click the small &quot;Raw arguments&quot;
                  expander to see the full args object including any
                  hidden-from-summary keys.
                </li>
              </ul>
              <p className="text-sm text-on-surface-variant">
                Net result: you should never see an approval card that
                says only &quot;Approve job creation?&quot; without
                context. If you do, file a bug — that&apos;s a regression.
              </p>
            </SubSection>
          </Section>

          <Section id="notifications" icon="notifications" title="Notifications">
            <p>
              <Link href="/notifications" className="link">/notifications</Link>{" "}
              is the platform alert feed. Job completions, failed
              runs, approval resolutions, configuration changes —
              anything that fires a system-level event lands here. The
              filter bar lets you scope by tab (all / unread / mentions
              / approvals) and search by free-text. Mark-read is
              optimistic and persists across sessions.
            </p>
            <p>
              Event sources currently wired:
            </p>
            <ul className="list-disc pl-5 space-y-1.5 text-sm">
              <li>
                <Term>Jobs</Term> — runs that complete, fail, or are
                disabled.
              </li>
              <li>
                <Term>Approvals</Term> — pending, granted, denied.
              </li>
              <li>
                <Term>System</Term> — settings changes, secret rotations,
                MCP_TOKEN refresh.
              </li>
            </ul>
          </Section>

          <Section id="profile" icon="person" title="Your Profile">
            <p>
              <Link href="/profile" className="link">/profile</Link> is the
              operator&apos;s account-settings page. Click the
              &quot;Operator&quot; tile at the bottom of the sidebar to
              get there. Two sections:
            </p>
            <SubSection icon="badge" title="Account">
              <p>
                Read-only display of your username and role. The
                username comes from <Code>UI_USER</Code> in the
                runtime config and isn&apos;t editable in the UI — to
                change it, update the env var in your{" "}
                <Code>.env</Code> and restart the guardian-agent
                container.
              </p>
            </SubSection>
            <SubSection icon="lock_reset" title="Change password">
              <p>
                Rotate your UI password from this page. The form
                requires your current password as a second factor:
                a stolen session cookie alone can&apos;t lock you
                out, because rotation also needs the password you
                already know.
              </p>
              <p>
                See{" "}
                <Link href="#authentication" className="link">
                  Authentication
                </Link>{" "}
                for the full flow — storage layout, hash algorithm,
                session-revocation behavior on success, security
                notification on the bell badge, and observability
                audit rows.
              </p>
            </SubSection>
          </Section>

          <Section id="api-keys" icon="vpn_key" title="API Keys">
            <p>
              <Link href="/api-keys" className="link">/api-keys</Link> mints
              and revokes operator-issued bearer tokens for programmatic
              access to the agent&apos;s <Code>/api/v1/*</Code> surface.
              Useful for SIEM pollers reading the audit log, CI scripts
              triggering scheduled jobs, cross-host integrations exposing
              automation hooks back at the agent. Keys take the shape{" "}
              <Code>guardian_ak_&lt;id&gt;_&lt;secret&gt;</Code>; the
              backend stores only <Code>sha256(&lt;secret&gt;)</Code> so
              the plaintext is shown <em>once</em> at create time and
              never recoverable after that.
            </p>
            <p>
              The page wires to the <Code>/api/v1/api_keys</Code>
              backend. The model uses <Term>advisory scopes</Term> —
              a flat list of capability strings the auth layer
              compares against the route&apos;s required scope:
            </p>
            <ul className="list-disc pl-5 space-y-1.5 text-sm">
              <li><Code>audit:read</Code> — GET <Code>/api/v1/audit*</Code></li>
              <li><Code>settings:read</Code> / <Code>settings:write</Code></li>
              <li><Code>approvals:resolve</Code></li>
              <li><Code>tools:call</Code> — JSON-RPC tool dispatch</li>
              <li><Code>*</Code> — superset / admin-equivalent</li>
            </ul>
            <p>
              Fresh installs read &quot;0 active, 0 revoked&quot;.
              Listing, minting, and revocation all require the
              bundle-internal <Code>MCP_TOKEN</Code> (proxied for you
              by the agent), so a key with one narrow scope can never
              mint a wider one.
            </p>
            <Callout tone="warn">
              Keys are shown <em>once</em>. Lose the value, rotate — the
              platform never stores plaintext. Treat keys with the same
              care as MCP_TOKEN; with the <Code>*</Code> scope they grant
              agent-equivalent access to the platform.
            </Callout>
          </Section>

          {/* ============================================================
                              OBSERVABILITY
              ============================================================ */}

          <Section
            id="obs-pipeline"
            icon="account_tree"
            title="Pipeline Health"
          >
            <p>
              <Link href="/observability/pipeline" className="link">
                /observability/pipeline
              </Link>{" "}
              is a live React Flow graph of every Guardian subsystem: the
              browser, the agent, the MCP, the six storage subsystems
              (audit, memory, secrets, settings, sessions, jobs), and the
              connector instances. Box borders flip green/amber/red based on
              live health probes; edges pulse cyan when traffic flowed in
              the last 60 seconds.
            </p>
            <p>Status sources:</p>
            <ul className="list-disc pl-5 space-y-1.5 text-sm">
              <li>
                <Term>Probes</Term> — the agent&apos;s{" "}
                <Code>/api/agent/health</Code> endpoint hits each
                service&apos;s health URL server-side (MCP{" "}
                <Code>/ping/</Code>, agent self-check, per-connector
                probes) and returns HTTP code +
                latency. Refresh interval: 5s.
              </li>
              <li>
                <Term>Storage rollup</Term> — the six SQLite stores live
                inside the MCP process, so they inherit MCP&apos;s
                status. If MCP is up, the stores are reachable; if
                MCP&apos;s probe fails, the stores can&apos;t be probed
                independently.
              </li>
              <li>
                <Term>Edge pulses</Term> — the audit log feed gives
                action-by-action history. Edges pulse if matching events
                appeared in the last 60s (e.g., a tool_call to{" "}
                <Code>tool:xsoar.*</Code> pulses the mcp→xsoar edge).
              </li>
            </ul>
            <p>
              Below the graph: a <Term>Component Status</Term> table with
              HTTP code + latency per probe (so you can see exact response
              times), and a <Term>Recent Traffic</Term> feed of the last
              audit events.
            </p>
          </Section>

          <Section
            id="obs-xsoar"
            icon="security"
            title="XSOAR Operational Metrics"
          >
            <p>
              <Link href="/observability/xsoar" className="link">
                /observability/xsoar
              </Link>{" "}
              answers <em>&ldquo;how busy is my SOC right now?&rdquo;</em> at a
              glance, reading live from your connected XSOAR instance(s). It is
              read-only — it never acts on the tenant. Three panels:
            </p>
            <ul className="list-disc pl-5 space-y-1.5 text-sm">
              <li>
                <Term>Open incidents by severity</Term> — a count tile per
                severity (Critical / High / Medium / Low) plus the total of
                open cases, so you see the shape of the queue immediately.
              </li>
              <li>
                <Term>SLA breaches</Term> — the open incidents at or nearing
                their SLA deadline, most-overdue first, each with how long it
                is overdue (or how long until it&apos;s due). This is the
                &ldquo;what should I work next?&rdquo; list.
              </li>
              <li>
                <Term>Integration health</Term> — how many of the tenant&apos;s
                integration instances are unhealthy, and which ones errored, so
                a broken feed surfaces here before it silently stops creating
                incidents.
              </li>
            </ul>
            <p>
              If you run multiple XSOAR instances (e.g. one per MSSP tenant),
              each gets its own block. The page degrades gracefully: a slow or
              failing metric shows a per-panel note instead of blanking the
              whole page, and with no XSOAR connector configured it points you
              to the Connectors page. Hit <Term>Refresh</Term> to re-pull.
            </p>
          </Section>

          <Section
            id="obs-metrics"
            icon="monitoring"
            title="Metrics & Traces"
          >
            <p>
              <Link href="/observability/metrics" className="link">
                /observability/metrics
              </Link>{" "}
              renders the Prometheus text feed from the MCP — counter,
              gauge, and histogram series for tool calls, request
              latency, and store operations. No external Prometheus or
              Grafana required; the page parses and graphs the text
              directly. Common series:
            </p>
            <ul className="list-disc pl-5 space-y-1.5 text-sm">
              <li>
                <Code>tool_call_total{"{tool=\"...\"}"}</Code> — counter
                per tool, per status.
              </li>
              <li>
                <Code>tool_call_duration_seconds_bucket</Code> — histogram
                of tool latency.
              </li>
              <li>
                <Code>agent_chat_turn_duration_seconds</Code> — end-to-end
                chat-turn timing.
              </li>
              <li>
                <Code>store_op_total{"{store=\"...\",op=\"...\"}"}</Code> —
                read/write counts per store.
              </li>
            </ul>
            <p>
              <Link href="/observability/traces" className="link">
                /observability/traces
              </Link>{" "}
              shows OpenTelemetry spans for end-to-end requests. Each
              chat-turn spans the agent → MCP → tool → connector → LLM
              path; clicking a span tree lets you find latency spikes
              precisely. Spans are stored alongside the audit log and
              survive container restarts.
            </p>
          </Section>

          <Section id="obs-logs" icon="terminal" title="Logs & Events">
            <p>
              <Link href="/observability/logs" className="link">
                /observability/logs
              </Link>{" "}
              is the structured-event firehose with a Lucene-light query
              syntax. <Link href="/observability/events" className="link">
                /observability/events
              </Link>{" "}
              is the same data rendered for compliance / who-did-what use
              cases (one row per event with actor, action, target,
              timestamp, source IP).
            </p>

            <SubSection icon="search" title="Lucene-light cheat sheet">
              <p>
                The query bar accepts <Code>key:value</Code> pairs,{" "}
                <Code>key:prefix*</Code> wildcards, and free-text. Six
                supported keys:
              </p>
              <Pre>{`actor:user:operator         // who triggered the event
action:tool_call            // what the event was
target:tool:xsoar.*         // wildcard prefix match
severity:error              // error / warn / info / debug
session:s_4k21m             // chat session id
job:weekly-coverage         // job name`}</Pre>
              <p>Common composed queries:</p>
              <Pre>{`actor:user:operator action:tool_call target:tool:xsoar.*
   // operator-triggered xsoar tool calls

severity:error action:tool_call
   // failed tool calls (good first stop when chat broke)

job:weekly-* action:job_run_complete
   // run completions for any "weekly-*" job

session:s_4k21m
   // every event from one chat session — replay an interaction`}</Pre>
            </SubSection>

            <SubSection icon="speed" title="Live tail vs paginated">
              <p>
                The <Term>Logs</Term> page tails the same stream over SSE
                (server-sent events) — new events stream in at the top
                without a page refresh. The <Term>Events</Term> page is
                paginated (20 rows per page, jump-to-time) so it&apos;s
                better for incident review and audit reads.
              </p>
            </SubSection>
          </Section>

          {/* Cost rollup operator UX. */}
          <Section id="cost-ux" icon="payments" title="Cost Rollup">
            <p>
              Every chat turn writes a <Code>chat_turn_cost</Code> audit
              row with input tokens, output tokens, cached tokens, and a
              dollar estimate (model&apos;s public per-token rate × token
              counts).{" "}
              <Link href="/observability/cost" className="link">
                /observability/cost
              </Link>{" "}
              rolls those rows up into a dashboard, and{" "}
              <Code>/cost</Code> in any chat shows the just-finished
              turn&apos;s breakdown inline.
            </p>

            <SubSection icon="terminal" title="The /cost slash command">
              <p>
                Type <Code>/cost</Code> right after a turn to render an
                inline cost card: input / output / cached token counts,
                the model&apos;s rate, the resulting dollar estimate, and
                the cumulative session total. <Code>/cost session</Code>{" "}
                shows just the session total; <Code>/cost turn</Code>{" "}
                forces just the last turn.
              </p>
            </SubSection>

            <SubSection icon="dashboard" title="The cost page">
              <p>
                Three primary views, each pickable from the page header:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Window picker</Term> — 1d / 7d / 30d / custom
                  date range. The chart updates immediately; subtotals
                  appear as cards above the chart.
                </li>
                <li>
                  <Term>By model</Term> — stacked bar showing per-model
                  spend in the chosen window. Useful for catching when a
                  switch to a more expensive model is ballooning costs.
                </li>
                <li>
                  <Term>By session</Term> — table of the top-N priciest
                  sessions, click-through to the session transcript so
                  you can see what was being asked.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="discount" title="Cache savings">
              <p>
                When Vertex prompt caching is on, cached input tokens
                bill at ~25% of the standard rate.
                The page shows two figures side by side:{" "}
                <Term>actual spend</Term> (what you paid) and{" "}
                <Term>without-cache spend</Term> (what you would have
                paid if every cached token had billed at full rate). The
                delta is your cumulative cache ROI — typically 30-60%
                savings on long sessions with stable system prompts.
              </p>
            </SubSection>

            <Callout tone="warn">
              Dollar estimates use public per-token list pricing baked
              into <Code>lib/model-pricing.ts</Code>. They&apos;re a{" "}
              <em>useful approximation</em>, not a billing source of
              truth — your actual GCP invoice may differ due to
              negotiated discounts, free-tier credits, or rate-card
              updates that haven&apos;t propagated to the table.
            </Callout>
          </Section>

          <Section id="telemetry-ux" icon="insights" title="Telemetry">
            <p>
              Telemetry is opt-in, privacy-first usage counting — and it
              ships <Term>off</Term>.{" "}
              <Link href="/observability/telemetry" className="link">
                /observability/telemetry
              </Link>{" "}
              shows the current posture, lets you flip it on or off, and
              lists per-event counts.
            </p>
            <ul className="list-disc pl-5 space-y-1.5 text-sm">
              <li>
                <Term>Declared events only</Term> — only the event names
                listed in the bundle manifest are ever recorded. Arbitrary
                callers can&apos;t slip new event names through.
              </li>
              <li>
                <Term>Counts, not content</Term> — the page reports how many
                times each declared event fired. Event payloads are never
                shown here, and recording a counter writes a{" "}
                <Code>telemetry_recorded</Code> audit row (the event name
                and count only).
              </li>
              <li>
                <Term>Auditable posture</Term> — turning telemetry on or off
                writes a <Code>telemetry_toggled</Code> audit row, so the
                privacy posture itself has a trail.
              </li>
            </ul>
          </Section>

          <Section
            id="obs-activity"
            icon="history_toggle_off"
            title="Live Activity"
          >
            <p>
              <Link href="/activity" className="link">/activity</Link> is a
              streaming feed of recent platform events — same data backing
              the pipeline graph&apos;s edge pulses, but rendered as a
              chronological list with action / target / actor columns.
              Useful when you&apos;re debugging &quot;why is this not
              happening&quot; in real time and don&apos;t want to write
              the query yet.
            </p>
            <p>
              Filter capabilities mirror the Logs page (Lucene-light
              syntax) but the page auto-refreshes every 2 seconds and
              caps at the latest 200 events to keep memory bounded.
            </p>
          </Section>

          {/* ============================================================
                                 SETTINGS
              ============================================================ */}

          <Section id="settings-services" icon="tune" title="Services">
            <p>
              <Link href="/settings" className="link">/settings</Link> shows
              every internal service with config and runtime status —
              ports, health endpoints, language/runtime, mounted volumes,
              and environment-variable overrides. It&apos;s the canonical
              service inventory; the{" "}
              <Link href="/observability/pipeline" className="link">
                pipeline
              </Link>{" "}
              page is the visual rendition of the same underlying data.
            </p>
            <p>
              The page derives status from the same{" "}
              <Code>/api/agent/health</Code> probes as the pipeline graph
              — so if an entry shows degraded here, the matching node
              flips amber on the graph too. They&apos;re two views of one
              source.
            </p>
          </Section>

          <Section
            id="settings-personality"
            icon="psychology_alt"
            title="Personality"
          >
            <p>
              <Link href="/settings/personality" className="link">
                /settings/personality
              </Link>{" "}
              is where the agent&apos;s voice and behavior live.
              Click <Term>Operator</Term> at the bottom of the
              sidebar, then <Term>Personality</Term> in the settings
              tab strip. The page is split into two panels:{" "}
              <Term>Persona</Term> (free-form system-prompt content)
              and <Term>Tuning</Term> (typed behavior knobs).
            </p>

            <SubSection icon="record_voice_over" title="Persona panel — who the agent is">
              <p>
                Three free-form fields shape every system prompt the
                agent ever sends:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Name</Term> — what the agent calls itself
                  when it introduces. Examples:{" "}
                  <em>&ldquo;SOC analyst assistant&rdquo;</em>,{" "}
                  <em>&ldquo;Incident responder&rdquo;</em>,{" "}
                  <em>&ldquo;Detection engineer&rdquo;</em>. Appears
                  in the chat header chip.
                </li>
                <li>
                  <Term>Tone</Term> — voice instructions:{" "}
                  <em>concise, factual</em> vs{" "}
                  <em>verbose, narrative</em> vs{" "}
                  <em>tactical, command-only</em>. Threaded into
                  the system-prompt persona block.
                </li>
                <li>
                  <Term>Instructions</Term> — system-prompt-style
                  guidance the operator wants the agent to follow
                  every turn. Things like{" "}
                  <em>&ldquo;Always cite the source when reporting
                  case findings&rdquo;</em> or{" "}
                  <em>&ldquo;Before closing a case, name the close
                  reason in plain English&rdquo;</em>.
                </li>
              </ul>
              <p className="text-sm">
                Persona content prepends a <Code>## PERSONA</Code>{" "}
                block to the system prompt for every chat turn. The
                TAIL of the system prompt (skills inventory + tool
                catalog) stays cacheable for Vertex prompt caching;
                only the small persona block varies. So you can iterate
                on the persona without exploding cache costs.
              </p>
            </SubSection>

            <SubSection icon="tune" title="Tuning panel — behavior knobs">
              <p>
                Four sliders / toggles that modulate chat-route and
                memory-store behavior without redeploying:
              </p>
              <ul className="list-disc pl-5 space-y-2 text-sm">
                <li>
                  <Term>Vertex prompt caching</Term> — when ON,
                  Guardian uses Vertex&apos;s{" "}
                  <Code>cachedContents</Code> API to cache the
                  system-prompt TAIL across turns. Saves 30-60% on
                  input tokens after the first turn. Default ON if
                  the <Code>GUARDIAN_VERTEX_CACHE=1</Code> env var is
                  set at boot; OFF otherwise. Toggle here to turn it
                  off per-workspace without redeploying.
                </li>
                <li>
                  <Term>Auto-compaction threshold</Term> — when
                  loading session history at the start of a turn,
                  Guardian token-budget-walks oldest-to-newest until
                  the cap fits. If the walk drops ≥ N prior messages,
                  auto-compaction kicks in and summarizes the dropped
                  portion via Gemini. Default 5; chatty workflows
                  can dial down to 2-3 to compact early; one-shot
                  workflows can dial up to suppress.
                </li>
                <li>
                  <Term>Memory MMR λ</Term> — Maximal Marginal
                  Relevance weight in the memory-store ranking
                  pipeline. Higher λ favors relevance over diversity
                  (returns tighter matches); lower λ favors diversity
                  (returns a spread of related-but-different memories).
                  Default 0.7. Lower it if memory results feel
                  repetitive.
                </li>
                <li>
                  <Term>Memory temporal decay λ</Term> — exponential
                  decay applied to memory-row recency in ranking.
                  Higher λ favors fresh memories aggressively; lower
                  λ treats old + new equally. Default 0.05 (half-life
                  ~14 days). Raise it for fast-moving incident
                  response contexts; lower it for long-running
                  knowledge bases.
                </li>
              </ul>
              <p className="text-sm">
                Slider drags auto-save after a short debounce — no
                explicit Save button. The auto-save fires a tier-2
                approval card the first time per session; subsequent
                drags in the same session use the previously-granted
                approval.
              </p>
            </SubSection>

            <SubSection icon="history" title="History + reset">
              <p>
                Every save snapshots the prior blob into{" "}
                <Code>personality_history</Code>. The page&apos;s{" "}
                <Term>History</Term> drawer shows the last N
                snapshots with diff highlights — click a row to
                preview the prior state, or click{" "}
                <Term>Restore</Term> to write it back (itself a
                tier-2 approval-gated write).
              </p>
              <p>
                <Term>Reset to default</Term> at the bottom of the
                page is a tier-3 destructive action — it requires
                an approval card AND types the literal word{" "}
                <Code>RESET</Code> into a confirmation field. The
                snapshot happens BEFORE the reset, so you can always
                restore from history afterwards.
              </p>
            </SubSection>

            <SubSection icon="smart_toy" title="Asking the agent to update the persona">
              <p>
                The chat agent has tools to read and update the
                personality blob directly. Examples:
              </p>
              <ul className="list-disc pl-5 space-y-1 text-sm">
                <li>
                  &ldquo;Set the agent name to &lsquo;Detection
                  engineer&rsquo; and the tone to &lsquo;tactical,
                  command-only&rsquo;.&rdquo; → calls{" "}
                  <Code>personality_patch</Code>, surfaces an approval
                  card with the diff.
                </li>
                <li>
                  &ldquo;What instructions are configured?&rdquo; →
                  calls <Code>personality_get</Code> (tier-1, no
                  approval).
                </li>
                <li>
                  &ldquo;Reset the personality to default.&rdquo; →
                  calls <Code>personality_reset</Code> (tier-3
                  destructive), surfaces a stronger approval card.
                </li>
              </ul>
              <p className="text-sm">
                Each call writes an audit row (<Code>personality_set</Code>,{" "}
                <Code>personality_reset</Code>, etc.) — browse them
                in <Link href="/observability/events" className="link">
                /observability/events
                </Link>{" "}
                with the <em>Personality</em> filter chip.
              </p>
            </SubSection>
          </Section>

          <Section id="backup-restore" icon="save" title="Backup & Restore">
            <p>
              Guardian packages every operator-owned piece of state
              into a single portable zip:{" "}
              <Link href="/settings/backup-restore" className="link">
                /settings/backup-restore
              </Link>{" "}
              is the one-stop surface. The same zip downloads from one
              deployment and restores onto another, even when the
              destination uses a different{" "}
              <Code>GUARDIAN_SECRET_KEK</Code>. Use it to migrate
              between hosts, snapshot before risky changes, or
              capture known-good state for compliance.
            </p>

            <SubSection icon="download" title="Backup — what travels">
              <p>
                Click <Term>Download</Term> on{" "}
                <Link href="/settings/backup-restore" className="link">
                  /settings/backup-restore
                </Link>{" "}
                and your browser saves{" "}
                <Code>guardian-backup-&lt;ISO-stamp&gt;.zip</Code>.
                The zip carries one JSON or directory per platform
                surface:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Personality</Term> — single-row blob (persona
                  fields + tuning knobs)
                </li>
                <li>
                  <Term>Instances + secrets</Term> — every connector
                  instance with config + cleartext secrets (so the
                  destination can re-encrypt under its own KEK)
                </li>
                <li>
                  <Term>Jobs</Term> — runtime-source jobs only;
                  manifest jobs reseed from{" "}
                  <Code>manifest.yaml</Code> at boot
                </li>
                <li>
                  <Term>Memory</Term> — all memory entries, without
                  embedding BLOBs (those re-embed at first search
                  on the destination)
                </li>
                <li>
                  <Term>Skills</Term> — every operator skill MD file,
                  preserving the category subdirectory structure
                </li>
                <li>
                  <Term>Knowledge</Term> — bundle doc references (the
                  KB itself reseeds from the destination&apos;s image)
                </li>
              </ul>
              <p className="text-warning text-sm">
                <span className="material-symbols-outlined text-[14px] align-text-bottom mr-1">
                  warning
                </span>
                <strong>The zip contains plaintext secrets.</strong>{" "}
                That&apos;s how the destination re-encrypts under its
                own KEK on restore — but it means the zip is
                operator-sensitive. Don&apos;t commit to version
                control; don&apos;t share over unencrypted channels;
                store at-rest encrypted if you keep snapshots.
              </p>
            </SubSection>

            <SubSection icon="preview" title="Dry-run preview">
              <p>
                Before committing a restore, click the file picker on{" "}
                <Link href="/settings/backup-restore" className="link">
                  /settings/backup-restore
                </Link>{" "}
                → <Term>Preview restore plan</Term>. The server
                parses the zip&apos;s <Code>manifest.json</Code>,
                counts entries per section, and renders a per-section
                summary card:
              </p>
              <Pre>{`Restore preview — guardian-backup-2026-05-25T14-22-09Z.zip

  Personality           1 row (will overwrite existing)
  Instances             4 instances + 11 secrets
  Skills                5 files (3 collisions; default = skip)
  Memory              152 entries (no collisions; embeddings re-built)
  Knowledge             — (no-op; image-baked)
  Jobs                  6 runtime jobs (last in restore order)

  ☐ Overwrite existing entries (force)`}</Pre>
              <p className="text-sm">
                The dry-run is purely read-only — nothing is written
                on the destination until you click{" "}
                <Term>Apply restore</Term>.
              </p>
            </SubSection>

            <SubSection icon="play_arrow" title="Restore — dependency-ordered apply">
              <p>
                Apply commits each section in dependency order so
                cross-section references never fail-closed:
              </p>
              <ol className="list-decimal pl-5 space-y-1 text-sm">
                <li>
                  <Term>Personality</Term> first (no dependencies;
                  always overwritten)
                </li>
                <li>
                  <Term>Instances + secrets</Term> next (connectors
                  must exist before jobs reference them)
                </li>
                <li>
                  <Term>Skills</Term> + <Term>Memory</Term> +{" "}
                  <Term>Knowledge</Term>
                </li>
                <li>
                  <Term>Jobs</Term> last — runtime jobs that
                  reference connectors don&apos;t fire on a missing
                  instance because instances landed in step 2.
                </li>
              </ol>
            </SubSection>

            <SubSection icon="merge_type" title="Collisions + force-overwrite">
              <p>
                Default semantics on every section are{" "}
                <Term>upsert-or-skip</Term>: an incoming row whose
                name/id collides with an existing one preserves the
                existing entry and reports the incoming one in the{" "}
                <Code>skipped</Code> summary count. Tick{" "}
                <Term>Overwrite existing entries (force)</Term> on the
                Restore plan to overwrite. <Term>Personality is
                always overwritten</Term> regardless — it&apos;s a
                single-row blob, there&apos;s no merge semantics.
              </p>
            </SubSection>

            <SubSection icon="warning" title="Caveats">
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Term>Memory embeddings</Term> aren&apos;t exported
                  (they&apos;re dim-bound to the embedding model). The
                  destination re-embeds entries on next semantic
                  search; the first search may be slightly slower
                  while the queue warms up.
                </li>
                <li>
                  <Term>Knowledge bundles</Term> are image-baked. The
                  zip carries doc content for reference but restore is
                  a no-op — the destination&apos;s KB is determined by
                  its container image.
                </li>
                <li>
                  <Term>Manifest jobs</Term> reseed from{" "}
                  <Code>manifest.yaml</Code> at boot regardless of
                  restore. Only runtime-source jobs round-trip.
                </li>
                <li>
                  <Term>API keys + audit log</Term> are NOT exported
                  on purpose. API keys are scoped to a specific
                  deploy; audit logs are tamper-evident per-host
                  records.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="api" title="API surface">
              <Pre>{`GET    /api/agent/backup                  -- download zip (cookie-gated)
POST   /api/agent/restore?dry_run=true    -- parse + preview only
POST   /api/agent/restore                 -- apply (with ?force=1 to overwrite)`}</Pre>
              <p className="text-sm text-on-surface-variant">
                The agent has no MCP tool surface for backup/restore
                — the cleartext-secrets envelope keeps these
                operator-only per the credential boundary.
                Scripted backup workflows use the REST endpoints
                with an{" "}
                <Link href="#api-keys" className="link">
                  API key
                </Link>{" "}
                in the bearer header.
              </p>
            </SubSection>
          </Section>

          <Section id="settings-precedence" icon="layers" title="Where Settings Live">
            <p>
              Guardian has multiple surfaces where you can set or change
              operator credentials and connector config. This section
              is the cheat sheet for which surface to use when, what
              survives an upgrade, and where the data actually lives.
              The full architectural picture is in{" "}
              <Link href="/help/architecture#secret-store" className="link">
                Architecture → Secret Store
              </Link>
              {" "}where the SecretStore Flow diagram traces every read
              and write path.
            </p>

            <Callout tone="info">
              <Term>One-line summary.</Term> The first-run setup form
              runs ONCE at install. Every change after that goes
              through the dedicated UI for what you&apos;re editing —
              {" "}<Link href="/profile" className="link">/profile</Link>{" "}for
              your UI password,{" "}
              <Link href="/providers" className="link">/providers</Link>{" "}
              for Vertex / Gemini service-account JSON,{" "}
              <Link href="/connectors" className="link">/connectors</Link>{" "}
              for per-connector instance creds. No setup re-runs,
              no merge logic, no surprise replacements.
            </Callout>

            <SubSection icon="rocket_launch" title="Scenario 1 — First-time install">
              <p>
                AuthGate detects no setup-completed flag at{" "}
                <Code>/app/runtime/.setup_complete</Code> → renders the
                setup form. You fill everything (UI password, Vertex
                SA JSON, connector configs — XSOAR) and
                submit.
              </p>
              <p>
                The agent then delegates each piece of data to its
                canonical store:
              </p>
              <ul className="list-disc pl-6 space-y-1">
                <li>UI password → <Code>POST /api/v1/ui/auth/password</Code> → SecretStore <Code>/ui/auth/&lt;user&gt;/password_hash</Code> (PBKDF2)</li>
                <li>Vertex creds → <Code>POST /api/v1/setup</Code> → ProviderStore <Code>primary-vertex</Code> instance (config + secrets)</li>
                <li>Connector configs → same setup endpoint → InstanceStore one row per connector</li>
                <li>TLS material → <Code>/tls/cert.pem</Code> + <Code>/tls/key.pem</Code> on the shared volume</li>
                <li>Setup-completed flag → <Code>/app/runtime/.setup_complete</Code> (presence-only marker)</li>
              </ul>
              <p>
                <Code>setup.json</Code> and <Code>.env.generated</Code>{" "}
                are NOT written. Operator-typed values live exclusively
                in the stores listed above. See{" "}
                <Link href="/help/architecture#setup-wiring" className="link">/help/architecture#setup-wiring</Link>{" "}
                for the canonical specification.
              </p>
            </SubSection>

            <SubSection icon="upload" title="Scenario 2 — Upgrade preserves everything">
              <p>
                Upgrading the stack via{" "}
                <Code>docker compose pull + up</Code> swaps in new
                images without touching persistent volumes. The
                bind-mounted <Code>./.guardian-agent</Code> path holds
                the setup-completed flag; the named volume{" "}
                <Code>guardian_mcp_data</Code> holds the SecretStore +
                InstanceStore + ProviderStore + audit log. Both
                survive container recreation.
              </p>
              <p>
                After upgrade, AuthGate calls{" "}
                <Code>isSetupRequired()</Code> and renders the
                LoginScreen. The setup form is unreachable
                post-install: typing <Code>/setup</Code> directly
                redirects to <Code>/</Code>, and{" "}
                <Code>POST /api/setup</Code> returns 409. Your
                existing credentials, connector instances, provider
                config, password hash, audit history — all preserved.
              </p>
            </SubSection>

            <SubSection icon="cable" title="Scenario 3a — Change connector creds via /connectors">
              <p>
                Want to rotate the XSOAR API key, change the XSOAR
                server URL, or update the key id? Use{" "}
                <Link href="/connectors" className="link">/connectors</Link>.
                Each connector has an instance (created at first-run
                from the bundle&apos;s <Code>bindsInstances</Code>{" "}
                template) and you can edit its config + secrets in
                place. Writes go through the MCP&apos;s instance API
                directly to the InstanceStore + SecretStore — no setup
                re-run, no agent restart. Tool calls (
                <Code>xsoar_*</Code>) read from
                InstanceStore on every
                invocation, so changes take effect at the next call.
              </p>
              <p className="text-sm text-on-surface-variant/85">
                Every xsoar tool routes through a single
                chokepoint helper that calls{" "}
                <Code>store.list_for(...)</Code> and{" "}
                <Code>instance.merged_config(secret_store)</Code> on every
                invocation, ensuring the InstanceStore is the single
                source of truth. See{" "}
                <Link
                  href="/help/architecture#connector-state"
                  className="link"
                >
                  Connector State Machine
                </Link>{" "}
                for the architectural detail.
              </p>
            </SubSection>

            <SubSection icon="psychology" title="Scenario 3b — Change Vertex creds via /providers">
              <p>
                Replace the Vertex service-account JSON, update the
                project ID, switch regions — all from{" "}
                <Link href="/providers" className="link">/providers</Link>.
                The page populates from the ProviderStore on load:
                Project ID and Region show in cleartext, the JSON shows
                as masked bullets. Change any subset — Test Connection
                and Save Changes activate when at least one field
                differs from the loaded value.
              </p>
              <p>
                Save calls <Code>PUT /api/v1/providers/{"{id}"}</Code>{" "}
                directly on the MCP. Untouched secret slots round-trip
                as the redaction sentinel and are preserved server-side.
                <Code>setup.json</Code> and <Code>.env.generated</Code>{" "}
                are NEVER written by this path. The cache for
                chat-handler vertex-cred resolution is invalidated
                in the same response, so the next chat dispatch sees
                your update with no propagation delay.
              </p>
              <p>
                If the operator hasn&apos;t configured Vertex yet
                (clean install, no <Code>primary-vertex</Code> instance
                in the ProviderStore), saving for the first time
                creates the instance via{" "}
                <Code>POST /api/v1/providers</Code>. All three fields
                (project, region, JSON) are required for the create
                path; partial creates aren&apos;t allowed because the
                MCP&apos;s manifest binding wouldn&apos;t materialise.
              </p>
            </SubSection>

            <SubSection icon="lock_reset" title="Scenario 3c — Change UI password via /profile">
              <p>
                Password changes go through the dedicated{" "}
                <Link href="/profile" className="link">/profile</Link>{" "}
                page. The hash lives in the SecretStore under{" "}
                <Code>/ui/auth/&lt;username&gt;/password_hash</Code>{" "}
                — see{" "}
                <Link href="#authentication" className="link">
                  Authentication
                </Link>{" "}
                for the full storage spec, session-revocation
                semantics, and audit-row references.
              </p>
            </SubSection>

            <SubSection icon="save" title="Scenario 3e — Backup &amp; restore the whole deployment">
              <p>
                Guardian packages every operator-owned piece of state
                into a single portable zip. See{" "}
                <Link href="#backup-restore" className="link">
                  Backup &amp; Restore
                </Link>{" "}
                for the full walkthrough — what travels in the zip,
                dry-run preview, dependency-ordered apply, collision
                semantics, and the REST API surface.
              </p>
            </SubSection>

            <SubSection icon="terminal" title="Env overlay (advanced — read-only shadow)">
              <p>
                <Code>EnvSecretStore</Code> is a read-time shadow: when
                a SecretStore consumer calls <Code>read(path)</Code>,
                the overlay first checks env vars matching the path
                pattern. If matched, the env value wins for THAT read;
                the file-backed store is never touched. Useful for IaC
                / CI flows that want to pin a credential per deployment
                without mutating the encrypted store. Set the env var
                via your <Code>.env</Code> or a compose override.
              </p>
            </SubSection>
          </Section>

          {/* ============================================================
                              TROUBLESHOOTING
              ============================================================ */}

          <Section id="troubleshoot" icon="support" title="Where to Look When…">
            <p>
              Common symptoms and the first place to look. The full
              troubleshooting tree lives across{" "}
              <Link href="/observability" className="link">
                /observability
              </Link>{" "}
              — these are the highest-yield starting points.
            </p>

            <Decision title="A job didn't fire">
              <p>
                Open <Link href="/jobs" className="link">/jobs</Link>, find
                the row. Filter by &quot;Failed&quot; or &quot;Never
                run.&quot; Click the card → the &quot;Last error&quot;
                banner tells you why; the run history table shows trigger
                source and duration. For prompt actions that return empty,
                expand the row — the model&apos;s reply is rendered
                inline; an empty reply means Gemini hit MAX_TOKENS or
                returned only function calls.
              </p>
            </Decision>

            <Decision title="A chat session looks empty after reload">
              <p>
                Right-side telemetry panel rehydrates from the messages
                table on session reload. If it&apos;s empty there, the
                session probably had no tool calls — the panel only
                restores tool round-trips, not the model&apos;s text
                deltas (those aren&apos;t persisted to keep storage
                tractable).
              </p>
            </Decision>

            <Decision title="An approval is stuck">
              <p>
                Open <Link href="/approvals" className="link">/approvals</Link>.
                Pending tab shows live requests; click Approve or Deny.
                Resolved tab shows history. Stuck requests time out after
                5 minutes server-side (the chat just unblocks with an
                error); if a card is older than that, it was already
                resolved — refresh.
              </p>
            </Decision>

            <Decision title="A connector call returns 'invalid bearer token'">
              <p>
                The <Code>MCP_TOKEN</Code> rotated. Local{" "}
                <Code>.env.vm</Code> may be stale; the container always
                reads the live one from{" "}
                <Code>/app/runtime/setup.json</Code> (or its env). When
                in doubt, exec into the container and check{" "}
                <Code>env | grep MCP_TOKEN</Code>. Setup-form values for
                MCP_TOKEN are persisted but ignored on the wire.
              </p>
            </Decision>

            <Decision title="A connector shows 'Not Installed' in the marketplace">
              <p>
                Visit{" "}
                <Link href="/connectors" className="link">
                  /connectors
                </Link>{" "}
                → Instances tab. If the connector has no instance there,
                the credentials weren&apos;t bound at first-run setup.
                Create an instance directly from /connectors → Create
                Instance — the form uses the same configSchema +
                secretSlots the bundle exposes, so it asks for the
                same fields setup would have. The marketplace status
                derives from instance presence — once an instance
                exists, the badge flips to{" "}
                <Term>Installed</Term> on the next refresh.
              </p>
            </Decision>

            <Decision title="A node on the pipeline graph shows red but the service is up">
              <p>
                Early versions of the pipeline page probed
                container-internal hostnames (e.g.,{" "}
                <Code>http://guardian-connector-xsoar-primary:9000</Code>)
                directly from the browser —
                which can&apos;t reach those names. The current version
                routes all probes through{" "}
                <Code>/api/agent/health</Code> (server-side) so this is
                solved. If it&apos;s still red, hit the Component Status
                table on that page — the HTTP code + latency tell you
                whether the probe completed and what came back.
              </p>
            </Decision>

            <Decision title="The agent says 'I can't run that'">
              <p>
                Either the matching skill is disabled (check{" "}
                <Link href="/skills" className="link">/skills</Link>, look
                for the toggle in the off state), or the agent doesn&apos;t
                think it has a relevant tool — check the skill&apos;s{" "}
                detail panel for the listed tools and confirm those exist
                in the right connector via the{" "}
                <Link href="/connectors" className="link">
                  Connectors
                </Link>{" "}
                tool inventory.
              </p>
            </Decision>
          </Section>

          {/* ============================================================
                              REFERENCES
              ============================================================ */}

          <Section
            id="ref-architecture"
            icon="schema"
            title="Architecture Guide"
          >
            <p>
              Companion to this user guide, focused on{" "}
              <em>how Guardian is built</em> rather than how to use it.
              Covers the service stack, boot lifecycle, the
              chat-route pipeline, every subsystem (memory, knowledge,
              skills, hooks, tasks, plan mode, subagents, plugins,
              jobs, notifications, approvals, models, providers,
              secret store), the three external connectors (XSOAR /
              Cortex Docs / Web Browser),
              audit-row schemas, REST endpoint wire
              formats, and the design decisions that shaped each
              substrate.
            </p>
            <p>
              Read this when you&apos;re extending the platform — adding
              a hook event, wiring a new audit action, building a
              plugin, or just trying to understand <em>why</em> something
              was built the way it was.
            </p>
            <Link
              href="/help/architecture"
              className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline mt-2"
            >
              <span className="material-symbols-outlined text-base">
                arrow_forward
              </span>
              Open the Architecture Guide
            </Link>
          </Section>

          <Section id="ref-journeys" icon="tour" title="User Journeys">
            <p>
              Hands-on, step-by-step walkthroughs for common operator
              tasks — onboarding a new connector, investigating an XSOAR
              case end-to-end, documenting and closing a case,
              installing a Slack policy hook, monitoring tasks,
              spawning scoped subagents. Each journey lists the
              prompts to paste, the tools that fire, and the expected
              output. Filter by category or difficulty (starter,
              intermediate, advanced).
            </p>
            <Link
              href="/help/journeys"
              className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline mt-2"
            >
              <span className="material-symbols-outlined text-base">
                arrow_forward
              </span>
              Browse user journeys
            </Link>
          </Section>

          <Section id="ref-api" icon="api" title="REST API">
            <p>
              Wire-format reference for every <Code>/api/v1/*</Code>{" "}
              endpoint — request schema, response shape, auth requirements,
              cURL examples. Click an endpoint card for the detail view
              with a try-it-out form; the icon buttons in the header view
              or download the OpenAPI 3.0 JSON spec. Endpoint internals
              (which audit rows fire, which tier gates them) are
              cross-referenced from{" "}
              <Link
                href="/help/architecture#rest-api"
                className="link"
              >
                Architecture &rarr; REST API
              </Link>
              .
            </p>
            <Link
              href="/help/api"
              className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline mt-2"
            >
              <span className="material-symbols-outlined text-base">
                arrow_forward
              </span>
              Browse REST API
            </Link>
          </Section>
        </div>
      </div>

      <style jsx>{`
        .link {
          color: var(--m3-primary, hsl(var(--primary)));
          text-decoration: none;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
            "Liberation Mono", "Courier New", monospace;
          font-size: 0.95em;
        }
        .link:hover {
          text-decoration: underline;
        }
      `}</style>
    </div>
  );
}

// ── Section primitives ─────────────────────────────────────────────

function Section({
  id,
  icon,
  title,
  children,
}: {
  id: string;
  icon: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-8 space-y-4">
      <div className="flex items-center gap-3 pb-2 border-b border-outline-variant/30">
        <span className="material-symbols-outlined text-2xl text-primary">
          {icon}
        </span>
        <h2 className="font-headline text-2xl font-bold tracking-tight text-on-surface">
          {title}
        </h2>
      </div>
      <div className="space-y-3 text-sm leading-relaxed text-on-surface-variant">
        {children}
      </div>
    </section>
  );
}

function SubSection({
  id,
  icon,
  title,
  children,
}: {
  id?: string;
  icon: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div id={id} className="space-y-2 pt-2">
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-base text-primary/80">
          {icon}
        </span>
        <h3 className="font-headline text-sm font-bold tracking-tight text-on-surface uppercase">
          {title}
        </h3>
      </div>
      <div className="space-y-2 pl-7 text-sm leading-relaxed text-on-surface-variant">
        {children}
      </div>
    </div>
  );
}

function Decision({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-xl p-4 space-y-2"
      style={glassStyle}
    >
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-base text-tertiary">
          troubleshoot
        </span>
        <h3 className="font-bold text-sm text-on-surface">{title}</h3>
      </div>
      <div className="text-sm text-on-surface-variant leading-relaxed">
        {children}
      </div>
    </div>
  );
}

function Term({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-semibold text-on-surface">
      {children}
    </span>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="font-mono text-[0.85em] px-1.5 py-0.5 rounded bg-surface-container-low text-on-surface border border-outline-variant/30">
      {children}
    </code>
  );
}

function Pre({ children }: { children: string }) {
  return (
    <pre
      className="text-[12px] leading-relaxed font-mono p-4 rounded-xl overflow-x-auto text-on-surface-variant"
      style={glassStyle}
    >
      {children}
    </pre>
  );
}

function Callout({
  tone,
  children,
}: {
  tone: "info" | "warn";
  children: React.ReactNode;
}) {
  const toneClass =
    tone === "warn"
      ? "border-l-4 border-l-tertiary bg-tertiary/5"
      : "border-l-4 border-l-primary bg-primary/5";
  const icon = tone === "warn" ? "warning" : "info";
  return (
    <div
      className={`rounded-r-xl pl-4 pr-5 py-3 flex gap-3 text-sm ${toneClass}`}
    >
      <span
        className={`material-symbols-outlined text-base shrink-0 ${
          tone === "warn" ? "text-tertiary" : "text-primary"
        }`}
      >
        {icon}
      </span>
      <div className="text-on-surface leading-relaxed">{children}</div>
    </div>
  );
}

