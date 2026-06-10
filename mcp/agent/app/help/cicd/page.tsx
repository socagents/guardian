"use client";

/**
 * Phantom CI/CD Guide — /help/cicd
 *
 * Operator-facing reference for how Phantom is built, released, and
 * upgraded. Distilled from docs/CICD.md (the engineering source of
 * truth — 1000+ lines of dense reference) into a diagram-driven
 * format readable in under 10 minutes.
 *
 * Scope (5 diagrams + section prose):
 *   1. The two installers — dev vs customer, what they share + differ
 *   2. Build pipeline — path-filtered per-service workflows + cascade
 *   3. Three change scenarios — decision tree for classifying releases
 *   4. release.yml lifecycle — tag-push to GitHub release publish
 *   5. Customer upgrade flow — download to running containers
 *
 * Conventions inherited from /help/architecture:
 *   - TOC sidebar with scroll-spy via IntersectionObserver
 *   - Glass-card section layout
 *   - Inline-SVG diagrams using DIAGRAM_THEME_CSS for theme support
 *
 * URL-only navigation — DELIBERATELY not in the sidebar.
 *
 * Why no sidebar entry (operator decision):
 *   /help/cicd is reference-grade content the operator looks up by
 *   name when they need it. Adding another sidebar nav entry crowds
 *   the agent's primary navigation. The URL is stable + linkable from
 *   chat (operator pastes "see /help/cicd"); a bookmark serves the
 *   primary discovery use case.
 *
 * Note re: CLAUDE.md rule 6a — that rule requires every new app/<page>
 * to add a sidebar entry in the same PR. v0.5.78 (issue #49) is an
 * explicit exception scoped by operator preference. components/sidebar.
 * tsx is intentionally NOT changed.
 *
 * v0.7.1 update: while the page deliberately stays OUT of the main
 * sidebar nav, it IS now linked from /help index's Specialty
 * references grid (alongside User Journeys + REST API Reference).
 * Operators landing on /help discover it via that card. Bookmark
 * + chat-link remain the canonical discovery paths.
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { CicdTwoInstallers } from "@/components/diagrams/cicd-two-installers";
import { CicdBuildPipeline } from "@/components/diagrams/cicd-build-pipeline";
import { CicdChangeScenarios } from "@/components/diagrams/cicd-change-scenarios";
import { CicdReleaseLifecycle } from "@/components/diagrams/cicd-release-lifecycle";
import { CicdCustomerUpgrade } from "@/components/diagrams/cicd-customer-upgrade";
import { CicdSmokeDiscipline } from "@/components/diagrams/cicd-smoke-discipline";

// ─── Layout primitives ────────────────────────────────────────────

const glassStyle = {
  background: "var(--glass-bg-strong)",
  backdropFilter: "blur(12px)",
  border: "0.5px solid var(--glass-border)",
} as const;

interface SectionDef {
  id: string;
  label: string;
  group: string;
  icon: string;
}

const SECTIONS: SectionDef[] = [
  { id: "intro", label: "Introduction", group: "Overview", icon: "info" },
  { id: "two-installers", label: "The Two Installers", group: "Foundation", icon: "deployed_code" },
  { id: "change-scenarios", label: "Three Change Scenarios", group: "Foundation", icon: "fork_right" },
  { id: "build-pipeline", label: "Build Pipeline", group: "Build & Release", icon: "construction" },
  { id: "release-lifecycle", label: "release.yml Lifecycle", group: "Build & Release", icon: "publish" },
  // v0.5.79 (issue #50): smoke-testing discipline section — the
  // operator-observable side of CI/CD. Placed between Release
  // Lifecycle and Customer Upgrade so the reading order is
  // "how do we build it → how does the release ceremony work →
  // how do we gate the release → what does the customer see."
  { id: "smoke-testing", label: "Smoke Testing Discipline", group: "Build & Release", icon: "verified" },
  { id: "customer-upgrade", label: "Customer Upgrade Flow", group: "Customer Operations", icon: "system_update_alt" },
  { id: "reference", label: "Reference & Commands", group: "Reference", icon: "menu_book" },
];

const GROUP_ORDER = ["Overview", "Foundation", "Build & Release", "Customer Operations", "Reference"] as const;

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="font-mono text-xs px-1.5 py-0.5 rounded bg-surface-container-low text-on-surface">
      {children}
    </code>
  );
}

function Pre({ children }: { children: React.ReactNode }) {
  return (
    <pre className="font-mono text-xs bg-surface-container-low text-on-surface p-4 rounded-lg overflow-x-auto my-3 border border-outline-variant/15">
      {children}
    </pre>
  );
}

function Section({ id, icon, title, children }: { id: string; icon: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="rounded-xl p-7 mb-6 scroll-mt-6" style={glassStyle}>
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-lg bg-primary-container/20 flex items-center justify-center">
          <span className="material-symbols-outlined text-primary text-xl">{icon}</span>
        </div>
        <h2 className="text-2xl font-headline font-bold text-on-surface tracking-tight">{title}</h2>
      </div>
      <div className="space-y-3 text-sm text-on-surface leading-relaxed">{children}</div>
    </section>
  );
}

function SubSection({ icon, title, children }: { icon: string; title: string; children: React.ReactNode }) {
  return (
    <div className="mt-5">
      <h3 className="text-base font-semibold text-on-surface flex items-center gap-2 mb-2">
        <span className="material-symbols-outlined text-base text-on-surface-variant">{icon}</span>
        {title}
      </h3>
      <div className="space-y-2 text-sm text-on-surface leading-relaxed">{children}</div>
    </div>
  );
}

export default function CicdGuide() {
  // v0.5.78 (issue #49): /help/cicd is NOT registered in
  // components/sidebar.tsx, deliberately. See file-top doc-comment
  // for the full reasoning. CLAUDE.md rule 6a has an explicit
  // exception for this route documented in the same release.
  // v0.7.1: now also linked from /help index Specialty references
  // grid — discoverable via /help landing, not just bookmark/URL.

  const [active, setActive] = useState<string>(SECTIONS[0]?.id ?? "");
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const visible = new Map<string, number>();
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            visible.set(e.target.id, e.intersectionRatio);
          } else {
            visible.delete(e.target.id);
          }
        }
        if (visible.size > 0) {
          let bestId = "";
          let bestRatio = -1;
          for (const [id, r] of visible) {
            if (r > bestRatio) {
              bestRatio = r;
              bestId = id;
            }
          }
          if (bestId) setActive(bestId);
        }
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: [0, 0.25, 0.5] },
    );
    for (const s of SECTIONS) {
      const el = document.getElementById(s.id);
      if (el) obs.observe(el);
    }
    return () => obs.disconnect();
  }, []);

  const grouped = GROUP_ORDER.map((group) => ({
    group,
    sections: SECTIONS.filter((s) => s.group === group),
  }));

  return (
    <div className="h-screen overflow-hidden flex">
      {/* TOC sidebar — scroll-spy + section nav. Mirrors the pattern
          /help/architecture and /help/user use, scoped down to the
          5 sections this page has. */}
      <aside
        className="w-72 shrink-0 overflow-y-auto custom-scrollbar p-5 border-r border-outline-variant/20"
        style={glassStyle}
        aria-label="CI/CD guide section navigation"
      >
        <div className="mb-4">
          <Link
            href="/help"
            className="text-sm text-on-surface-variant/80 hover:text-on-surface flex items-center gap-1.5 transition-colors"
          >
            <span className="material-symbols-outlined text-base">arrow_back</span>
            Help index
          </Link>
        </div>

        <h1 className="text-lg font-headline font-bold text-on-surface mb-1 tracking-tight">CI/CD Guide</h1>
        <p className="text-xs text-on-surface-variant mb-5 leading-relaxed">
          How Phantom is built, released, and upgraded. Five diagrams.
        </p>

        <nav className="space-y-5">
          {grouped.map(({ group, sections }) => (
            <div key={group}>
              <div className="text-[10px] uppercase tracking-widest text-on-surface-variant/60 font-label mb-2 px-2">
                {group}
              </div>
              <ul className="space-y-0.5">
                {sections.map((s) => {
                  const isActive = active === s.id;
                  return (
                    <li key={s.id}>
                      <a
                        href={`#${s.id}`}
                        className={`flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-all ${
                          isActive
                            ? "bg-primary/15 text-primary"
                            : "text-on-surface-variant hover:bg-white/5 hover:text-on-surface"
                        }`}
                      >
                        <span
                          className={`material-symbols-outlined text-base ${
                            isActive ? "text-primary" : "text-on-surface-variant/60"
                          }`}
                        >
                          {s.icon}
                        </span>
                        <span className="flex-1">{s.label}</span>
                      </a>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="mt-6 pt-5 border-t border-outline-variant/15">
          <p className="text-[11px] text-on-surface-variant/60 leading-relaxed">
            Engineering source of truth:{" "}
            <a
              href="https://github.com/kite-production/phantom/blob/main/docs/CICD.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary/80 hover:text-primary underline-offset-2 hover:underline"
            >
              docs/CICD.md
            </a>
            . This page condenses it for operators.
          </p>
        </div>
      </aside>

      {/* Main content */}
      <div ref={containerRef} className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="max-w-5xl mx-auto p-8">
          <Section id="intro" icon="info" title="Introduction">
            <p>
              Phantom ships as a Docker Compose stack of 5 containers plus per-instance
              connector containers. The CI/CD pipeline produces two distinct artifacts:
              a <strong>dev installer</strong> (rebuilt on every push to main) and a{" "}
              <strong>customer installer</strong> (built on each <Code>vX.Y.Z</Code> release tag).
              They share the install ceremony, compose template, and on-disk layout — only the
              image digests baked at build time differ.
            </p>
            <p>
              This guide explains five things in order, each with a diagram:
            </p>
            <ol className="list-decimal pl-5 space-y-1.5 mt-2">
              <li>
                The two installers — dev vs customer, what they share + diverge on.
              </li>
              <li>
                How to classify a change into one of the three release scenarios.
              </li>
              <li>
                The path-filtered build pipeline that produces dev images.
              </li>
              <li>
                The <Code>release.yml</Code> lifecycle that produces customer releases.
              </li>
              <li>
                What happens on the customer host during an upgrade.
              </li>
            </ol>
            <p className="text-on-surface-variant mt-3">
              For full reference material — workflow YAML internals, failure-mode catalog,
              PAT generation recipes, rollback procedure — read{" "}
              <a
                href="https://github.com/kite-production/phantom/blob/main/docs/CICD.md"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline-offset-2 hover:underline"
              >
                docs/CICD.md
              </a>{" "}
              in the repo.
            </p>
          </Section>

          <Section id="two-installers" icon="deployed_code" title="The Two Installers">
            <p>
              Phantom builds two installer binaries from the same source tree but on
              different cadences. Both produce a self-extracting executable that, when run,
              materializes the same compose stack at <Code>/opt/phantom</Code>.
            </p>
            <p>
              The diagram below highlights the symmetry: every step of the install
              ceremony is identical. The only thing the dev pipeline and the release
              pipeline diverge on is{" "}
              <em>which image digests get pinned in the manifest</em>.
            </p>

            <div className="my-5">
              <CicdTwoInstallers />
            </div>

            <SubSection icon="memory" title="Why this design matters">
              <p>
                Symmetry between dev and customer paths means &quot;smoke-test the dev install&quot;
                is functionally equivalent to &quot;smoke-test the customer install.&quot; The customer
                installer has zero knowledge of dev — no flags, no branches, no toggles.
                A failure mode in the dev install ceremony WILL surface in the customer flow
                identically. This is the load-bearing &quot;local mirrors customer&quot; design
                principle from CLAUDE.md.
              </p>
            </SubSection>

            <SubSection icon="folder_zip" title="What's inside an installer">
              <p>Both installers are self-extracting archives containing:</p>
              <ul className="list-disc pl-5 space-y-1 text-sm">
                <li>
                  <Code>install.tar.gz</Code> — compose template, helper scripts, default
                  config files.
                </li>
                <li>
                  <Code>release-manifest-vX.Y.Z.env</Code> — one{" "}
                  <Code>DIGEST_PHANTOM_*</Code> line per image. Becomes{" "}
                  <Code>/opt/phantom/.env</Code> at install time.
                </li>
                <li>
                  <Code>manifest.sha256</Code> — integrity check.
                </li>
              </ul>
            </SubSection>
          </Section>

          <Section id="change-scenarios" icon="fork_right" title="Three Change Scenarios">
            <p>
              Every non-trivial change classifies into one of three scenarios. The
              scenario sets the version bump rule, the customer&apos;s required action,
              and the fate of named volumes during the upgrade.
            </p>
            <p>
              Mis-classifying a change is a real source of upgrade pain — if a code +
              installer change ships as Scenario 1 (re-run existing installer), customers
              get the new image digests but the OLD compose template, which may reference
              env vars or volumes the new images expect.
            </p>

            <div className="my-5">
              <CicdChangeScenarios />
            </div>

            <SubSection icon="check_circle" title="Scenario 1 — code-only">
              <p>
                Most patch releases land here. Customer&apos;s <Code>/opt/phantom/phantom-installer</Code>{" "}
                still works — re-running it updates the digest pins in{" "}
                <Code>.env</Code> and <Code>docker compose pull && up -d</Code> recreates
                only the changed containers. Volumes preserved automatically because the
                compose template didn&apos;t change.
              </p>
            </SubSection>

            <SubSection icon="info" title="Scenario 2 — code + installer change">
              <p>
                Installer template changed (new env var, new service in compose, new
                volume mount). Customer must download a NEW installer from the release
                page. Default flag <Code>WIPE_VOLUMES=false</Code> preserves existing
                named volumes — operator&apos;s data survives the upgrade.
              </p>
            </SubSection>

            <SubSection icon="warning" title="Scenario 3 — BC-incompatible storage">
              <p>
                Storage schema change that can&apos;t be auto-migrated (e.g. KEK rotation,
                breaking DB schema delta). Customer downloads new installer and runs
                with <Code>WIPE_VOLUMES=true</Code>. Crucially: <strong>no auto-backup is
                performed</strong>. Operator must take a manual backup before running.
                Released only for genuine breaking changes the codebase can&apos;t paper over.
              </p>
            </SubSection>
          </Section>

          <Section id="build-pipeline" icon="construction" title="Build Pipeline">
            <p>
              A push to <Code>main</Code> triggers up to four per-service workflows in
              parallel. Each is gated by a <Code>paths:</Code> filter on the source paths
              it owns — a push that only touches <Code>mcp/agent/**</Code> fires only{" "}
              <Code>build-agent.yml</Code>; <Code>xlog/**</Code>,{" "}
              <Code>third_party/caldera/**</Code>, and{" "}
              <Code>bundles/spark/connectors/**</Code> stay untouched and retain their
              previous <Code>:dev</Code> digests.
            </p>

            <div className="my-5">
              <CicdBuildPipeline />
            </div>

            <SubSection icon="bolt" title="Workflow_run cascade">
              <p>
                Once any per-service workflow finishes,{" "}
                <Code>build-dev-installer.yml</Code> fires via{" "}
                <Code>workflow_run</Code>. It re-resolves <Code>:dev</Code> tags into
                content digests, writes the manifest, and republishes the{" "}
                <Code>dev-latest</Code> GitHub prerelease (the operator&apos;s dev install
                source).
              </p>
            </SubSection>

            <SubSection icon="warning" title="Updater + Browser don't rebuild on dev">
              <p>
                <Code>phantom-updater</Code> and <Code>phantom-browser</Code> only rebuild
                on customer release tags. The dev installer pulls these digests from the
                latest customer release manifest (a &quot;STABLE-ADVANCED&quot; carve-out).
                A fix in <Code>updater/src/main.py</Code> is in <Code>main</Code> after a
                push but doesn&apos;t reach operator installs until a <Code>vX.Y.Z</Code>{" "}
                tag fires.
              </p>
              <p>
                This is the most important property to remember: not every fix in{" "}
                <Code>main</Code> reaches your install via the dev cycle.
              </p>
            </SubSection>

            <SubSection icon="link_off" title="The untouched-services invariant">
              <p>
                For services whose source didn&apos;t change between releases (e.g. xlog
                during an agent-only release), <Code>release.yml</Code>&apos;s retag-from-prev
                path produces a <em>bit-identical</em> image. <Code>docker compose up -d</Code>{" "}
                recognizes the same digest and leaves the container running.{" "}
                <Code>caldera</Code> and <Code>xlog</Code> in-memory state survives across
                releases that don&apos;t touch their code.
              </p>
            </SubSection>
          </Section>

          <Section id="release-lifecycle" icon="publish" title="release.yml Lifecycle">
            <p>
              When the operator pushes a version tag (
              <Code>git tag vX.Y.Z && git push origin vX.Y.Z</Code>),{" "}
              <Code>.github/workflows/release.yml</Code> runs the full release pipeline.
              Five phases below; the diagram traces them in order.
            </p>

            <div className="my-5">
              <CicdReleaseLifecycle />
            </div>

            <SubSection icon="difference" title="1. Detect changed services">
              <p>
                Diffs HEAD against the previous tag for each service&apos;s owned paths.
                Output: a <Code>CHANGED_PHANTOM_*</Code> env var per service indicating
                whether to build or retag.
              </p>
            </SubSection>

            <SubSection icon="build" title="2. Build OR retag">
              <p>
                Changed services run the full <Code>docker buildx</Code> path and push
                under the new <Code>vX.Y.Z</Code> tag. Unchanged services skip the build
                and run <Code>docker pull :vPREV → docker tag :vX.Y.Z → docker push</Code>.
                The retagged image is bit-identical to the previous release — same digest,
                same byte content. This is what makes the &quot;untouched services preserve
                in-memory state&quot; invariant work end-to-end.
              </p>
            </SubSection>

            <SubSection icon="description" title="3. Manifest assembly">
              <p>
                Writes <Code>release-manifest-vX.Y.Z.env</Code> with one digest pin per
                service:
              </p>
              <Pre>{`DIGEST_PHANTOM_AGENT=sha256:abc...
DIGEST_PHANTOM_XLOG=sha256:def...
DIGEST_PHANTOM_CALDERA=sha256:ghi...
DIGEST_PHANTOM_UPDATER=sha256:jkl...
DIGEST_PHANTOM_BROWSER=sha256:mno...
DIGEST_PHANTOM_CONNECTOR_CORTEX_DOCS=sha256:pqr...
...`}</Pre>
            </SubSection>

            <SubSection icon="lock_open" title="4. GHCR per-version access">
              <p>
                GHCR enforces pull access <strong>per image VERSION</strong>, not per
                package alone. A package version becomes org-readable when associated with
                a GitHub Release. <Code>gh release create vX.Y.Z</Code> is the step that
                flips the new image versions from private (only org admins can pull) to
                org-readable (customer PATs with <Code>read:packages</Code> can pull). If
                this step fails partway, customers see <Code>denied</Code> errors when
                they try to download the new images.
              </p>
            </SubSection>

            <SubSection icon="cloud_upload" title="5. Publish GitHub release">
              <p>
                Attaches the four release assets and creates the{" "}
                <Code>Phantom vX.Y.Z</Code> release page customers browse to.
              </p>
            </SubSection>
          </Section>

          <Section id="smoke-testing" icon="verified" title="Smoke Testing Discipline">
            <p>
              CI/CD doesn&apos;t end at <Code>release.yml</Code>. A release reaches the
              operator only after passing through two layers of smoke verification: an
              agent-side automated probe + the operator&apos;s hands-on validation. The
              GitHub issue&apos;s <Code>status:*</Code> labels track each release&apos;s position
              in the lifecycle.
            </p>
            <p>
              The diagram below shows three things: the label-state machine (top row),
              the agent-side probe rules that gate the <Code>in-progress</Code> →{" "}
              <Code>ready-for-testing</Code> transition (middle band), and the bullet-
              state classification + postmortem loop (bottom).
            </p>

            <div className="my-5">
              <CicdSmokeDiscipline />
            </div>

            <SubSection icon="route" title="The label-state machine">
              <p>
                Every release issue moves through five status labels in order. The agent
                flips three of them (<Code>in-progress</Code>, <Code>ready-for-testing</Code>,{" "}
                <Code>released</Code>); the operator flips two (
                <Code>testing-complete</Code>, <Code>release-approved</Code>). The split
                is deliberate — the agent never assumes operator approval on its own; the
                operator never has to manage the routine labels (in-progress / ready-for-
                testing / released) by hand.
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <Code>status:in-progress</Code> — agent flips on the first commit that
                  references the issue (<Code>Refs #N</Code> in the commit footer).
                </li>
                <li>
                  <Code>status:ready-for-testing</Code> — agent flips after running the
                  agent-side end-to-end probes (see rules below) and confirming they
                  pass.
                </li>
                <li>
                  <Code>status:testing-complete</Code> — operator flips after their
                  hands-on validation on phantom-vm passes.
                </li>
                <li>
                  <Code>status:release-approved</Code> — operator flips via chat approval
                  phrase. Metadata-only flag (Option A in CLAUDE.md); doesn&apos;t bypass
                  the chat-approval requirement.
                </li>
                <li>
                  <Code>status:released</Code> — agent flips after{" "}
                  <Code>release.yml</Code> succeeds for the tag. Issue auto-closes.
                </li>
              </ul>
            </SubSection>

            <SubSection icon="rule" title="The seven rules of agent-side smoke (v0.5.75+ / v0.5.80+)">
              <p>
                Before flipping <Code>status:ready-for-testing</Code>, the agent runs the
                seven rules from the CLAUDE.md{" "}
                <a
                  href="https://github.com/kite-production/phantom/blob/main/CLAUDE.md#agent-side-headless-smoke-mandatory-before-statusready-for-testing--v0575-reckoning"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline-offset-2 hover:underline"
                >
                  Agent-side headless smoke addendum
                </a>
                . Rules 1-6 landed in v0.5.75; Rule 7 in v0.5.80 (postmortem for
                the operator catching the same bug in sibling connectors after a
                single-connector fix).
              </p>
              <ol className="list-decimal pl-5 space-y-1.5 text-sm">
                <li>
                  <strong>Execute, don&apos;t trace.</strong> Run the smoke bullet via
                  tunnel + curl/Playwright, not &ldquo;I read the code and it looks right.&rdquo; The
                  operator&apos;s hands-on is the SECOND validation, not the first.
                </li>
                <li>
                  <strong>State verification.</strong> Pair every &ldquo;X happens&rdquo; bullet with
                  &ldquo;GET shows X persisted in the expected shape.&rdquo; Submit-clicked isn&apos;t
                  enough — verify the persisted state.
                </li>
                <li>
                  <strong>End-to-end probe for connector-system changes.</strong> Any
                  change touching connectors / instances / updater requires resolving an
                  instance, hitting <Code>/api/v1/instances/&lt;id&gt;/test</Code>, AND
                  exercising <Code>tools/call</Code>. Confirm a non-error response (or a
                  clean expected error).
                </li>
                <li>
                  <strong>Dev-cycle gaps LEAD the matrix.</strong> If a fix touches{" "}
                  <Code>updater/src/main.py</Code> or <Code>phantom-browser/</Code>, the
                  smoke matrix opens with that fact in bold. Never buried in prose.
                </li>
                <li>
                  <strong>Inline state classification.</strong> Each bullet annotated
                  with one of three states. See the table below.
                </li>
                <li>
                  <strong>Postmortem-driven growth.</strong> Operator catches a bug in{" "}
                  <Code>dev-built</Code> code? Next release ships a CLAUDE.md addendum
                  naming the specific smoke gap. The discipline grows from real misses.
                </li>
                <li>
                  <strong>Bug-family audit (v0.5.80+).</strong> When fixing a bug in a
                  connector-system file, audit sibling connectors for the same bug
                  pattern in the same release. <Code>grep</Code> the pattern across{" "}
                  <Code>bundles/spark/connectors/*/src/</Code>; fix every hit OR document
                  why the remaining hits are left alone. The blast radius of a
                  connector-system bug is rarely one connector — usually a code pattern
                  that was copy-evolved across the family. Caught after the v0.5.77
                  cortex-xdr <Code>usecase.instance_store</Code> fix missed identical
                  bugs in caldera, xsiam, and cortex-content.
                </li>
              </ol>
            </SubSection>

            <SubSection icon="check_circle" title="Bullet state classification">
              <p>
                Smoke matrices in chat get inline state-tags per bullet. The operator
                sees which bullets the agent has already confirmed work + which still
                need their hands-on:
              </p>
              <table className="w-full text-xs my-3 border-collapse">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--glass-border)" }}>
                    <th className="text-left py-2 px-2 font-label uppercase tracking-wider text-on-surface-variant">State</th>
                    <th className="text-left py-2 px-2 font-label uppercase tracking-wider text-on-surface-variant">Meaning</th>
                    <th className="text-left py-2 px-2 font-label uppercase tracking-wider text-on-surface-variant">Example</th>
                  </tr>
                </thead>
                <tbody>
                  <tr style={{ borderBottom: "0.5px solid var(--glass-border)" }}>
                    <td className="py-2 px-2 align-top"><span className="text-green-400 font-bold">✓ agent-verified</span></td>
                    <td className="py-2 px-2 align-top">Agent ran the bullet through the tunnel; expected result happened.</td>
                    <td className="py-2 px-2 align-top">GET /api/v1/instances/&lt;id&gt; returns secrets.api_key=&quot;***&quot;.</td>
                  </tr>
                  <tr style={{ borderBottom: "0.5px solid var(--glass-border)" }}>
                    <td className="py-2 px-2 align-top"><span className="text-yellow-400 font-bold">⨯ agent-verified-blocked</span></td>
                    <td className="py-2 px-2 align-top">Agent tried but a known gap prevented full verification.</td>
                    <td className="py-2 px-2 align-top">updater/main.py fix only ships at customer release tag.</td>
                  </tr>
                  <tr>
                    <td className="py-2 px-2 align-top"><span className="text-on-surface-variant font-bold">? agent-skipped</span></td>
                    <td className="py-2 px-2 align-top">Agent didn&apos;t run; operator hands-on is the primary verification.</td>
                    <td className="py-2 px-2 align-top">UI theme toggle behavior, click-path through forms.</td>
                  </tr>
                </tbody>
              </table>
            </SubSection>

            <SubSection icon="autorenew" title="The postmortem loop (rule 6)">
              <p>
                The discipline is not static. When the operator catches a bug in code
                already at <Code>status:dev-built</Code> (i.e. the agent&apos;s smoke missed
                it), the next release ships a CLAUDE.md or docs/CICD.md addendum naming
                the specific gap. The rule set grows from real misses, not from abstract
                principles.
              </p>
              <p>Concrete examples of the loop working:</p>
              <ul className="list-disc pl-5 space-y-1.5 text-sm">
                <li>
                  <strong>v0.5.75</strong> itself was the postmortem for the
                  v0.5.67/70/73/74 + #48 five-in-a-row stretch — five basic bugs the
                  operator caught at hands-on because the agent&apos;s smoke had been API-
                  shape checks only (tsc/lint/build), never tunnel-based execution.
                </li>
                <li>
                  <strong>v0.5.76</strong> was the FIRST release where the new
                  discipline caught a bug pre-ship — function-prefix vs connector-id
                  mismatch surfaced on rule 3&apos;s end-to-end probe.
                </li>
                <li>
                  <strong>v0.5.77</strong> was the SECOND bug caught by the same probe
                  cycle 30 minutes later — connector code imported{" "}
                  <Code>usecase.instance_store</Code> which doesn&apos;t exist in the
                  container.
                </li>
              </ul>
              <p>
                Both bugs had been latent since v0.5.61 — six months in code that was
                never end-to-end functional. The discipline is converting invisible bugs
                into visible ones at the right moment.
              </p>
            </SubSection>
          </Section>

          <Section id="customer-upgrade" icon="system_update_alt" title="Customer Upgrade Flow">
            <p>
              On upgrade day, the customer&apos;s sequence is short. The diagram shows the
              four steps + the per-scenario outcomes for volumes and container state.
            </p>

            <div className="my-5">
              <CicdCustomerUpgrade />
            </div>

            <SubSection icon="key" title="Image-digest pinning is the load-bearing trick">
              <p>
                <Code>docker compose up -d</Code> reads each service&apos;s image digest from{" "}
                <Code>/opt/phantom/.env</Code>. If a service&apos;s digest matches what&apos;s
                already running, compose leaves the container alone — no recreate, no
                state loss. Only services whose digest changed get pulled + recreated.
              </p>
              <p>
                This is why the &quot;untouched services preserve state&quot; invariant works
                during an upgrade and why <Code>caldera</Code>&apos;s in-flight implant
                tracking + <Code>xlog</Code>&apos;s active workers survive a release that
                only touches <Code>phantom-agent</Code>.
              </p>
            </SubSection>

            <SubSection icon="settings_backup_restore" title="Backups (operator-side, manual)">
              <p>
                Phantom doesn&apos;t auto-backup before an upgrade. For Scenario 1 and 2 you
                don&apos;t need to — volumes are preserved automatically. For Scenario 3, the
                installer documentation explicitly tells the operator to back up named
                volumes BEFORE running with <Code>WIPE_VOLUMES=true</Code>. Recipe:
              </p>
              <Pre>{`# Back up every named volume to a tarball, BEFORE you run the installer.
for v in $(docker volume ls -q | grep '^phantom_'); do
  docker run --rm \\
    -v "$v":/data:ro \\
    -v "$PWD/backups":/backup \\
    busybox tar czf "/backup/$v-$(date +%Y%m%d).tar.gz" -C /data .
done`}</Pre>
            </SubSection>
          </Section>

          <Section id="reference" icon="menu_book" title="Reference & Commands">
            <SubSection icon="play_arrow" title="Common operator commands">
              <Pre>{`# Re-run dev installer (Scenario 1 after a push to main)
sudo /home/$USER/phantom-installer-dev

# Run customer installer (Scenario 2 + 3)
sudo ./phantom-installer

# Force Scenario 3 wipe (USE WITH BACKUP)
sudo WIPE_VOLUMES=true ./phantom-installer

# Status of running stack
docker compose -f /opt/phantom/docker-compose.yml ps

# View phantom-updater logs (for customer-instance start/stop events)
docker logs --tail 100 phantom_updater`}</Pre>
            </SubSection>

            <SubSection icon="extension" title="Adding a new connector — checklist">
              <p>
                A new bundle connector requires <strong>nine</strong> load-bearing edits, not
                just the obvious <Code>bundles/spark/connectors/&lt;id&gt;/</Code> directory.
                Missing any one produces a partial state (visible but uninstallable, or
                installable but container never spawns, etc.). Full table in{" "}
                <a
                  href="https://github.com/kite-production/phantom/blob/main/docs/CICD.md#adding-a-new-connector--checklist-avoid-silent-install-time-failures"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline-offset-2 hover:underline"
                >
                  docs/CICD.md § Adding a new connector
                </a>
                .
              </p>
            </SubSection>

            <SubSection icon="bug_report" title="Failure-mode catalog">
              <p>
                When a workflow fails or an install fails in a way that doesn&apos;t
                immediately reveal its cause, check{" "}
                <a
                  href="https://github.com/kite-production/phantom/blob/main/docs/CICD.md#cicd-failure-modes--recovery-playbook"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline-offset-2 hover:underline"
                >
                  docs/CICD.md § CI/CD failure modes
                </a>{" "}
                first. The catalog covers ~11 patterns we&apos;ve hit (chronic GHCR
                docker-login timeout, Cloud NAT throttling, workflow_run cascade
                serialization producing misleading <Code>UNCHANGED</Code> diagnostics, etc.).
                Each entry: symptom → cause → remediation → prevention.
              </p>
            </SubSection>

            <SubSection icon="vpn_key" title="PAT recipes">
              <p>
                Customer PAT needs only <Code>read:packages</Code>. Operator PAT (for
                pushing to GHCR + cutting releases) needs <Code>read:packages + write:packages + repo</Code>.
                Step-by-step recipes for both classic + fine-grained tokens are in{" "}
                <a
                  href="https://github.com/kite-production/phantom/blob/main/docs/CICD.md#pat-recipes"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline-offset-2 hover:underline"
                >
                  docs/CICD.md § PAT recipes
                </a>
                .
              </p>
            </SubSection>

            <SubSection icon="undo" title="Rollback procedure">
              <p>
                Customer-side rollback for Scenario 1 + 2: re-run the prior installer
                (still on disk at <Code>/opt/phantom/phantom-installer</Code> if not
                overwritten). For Scenario 3: restore from backup. Full procedure +
                operator-side yank (pulling a broken release from GHCR) in{" "}
                <a
                  href="https://github.com/kite-production/phantom/blob/main/docs/CICD.md#rollback-procedure"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline-offset-2 hover:underline"
                >
                  docs/CICD.md § Rollback procedure
                </a>
                .
              </p>
            </SubSection>
          </Section>

          {/* Bottom spacer so the last section can scroll to the active band */}
          <div style={{ height: "40vh" }} />
        </div>
      </div>
    </div>
  );
}
