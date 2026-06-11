export type AgentWorkflow = {
  id: string;
  title: string;
  prompt: string;
  requiredTools: string[];
  outputs: string[];
};

export const agentContract = {
  apiVersion: 'guardian.agentic/v1alpha1',
  kind: 'AgentRuntimeContract',
  metadata: {
    id: 'guardian-soc-agent',
    name: 'Guardian Agent',
    version: '0.1.0',
    description:
      'AI incident-response agent for Cortex XSIAM/XDR: case investigation, XQL query authoring, asset context, and web research over MCP tools.',
  },
  capabilities: [
    'xsiam-case-investigation',
    'xql-query-authoring',
    'asset-context-lookup',
    'web-research',
    'standalone-bundle-import',
  ],
  interfaces: {
    ui: {
      route: '/',
      mountPath: '/agents/guardian-soc-agent',
    },
    manifest: {
      method: 'GET',
      path: '/api/agent/manifest',
    },
    health: {
      method: 'GET',
      path: '/api/agent/health',
    },
    workflows: {
      method: 'GET',
      path: '/api/agent/workflows',
    },
    mcp: {
      env: 'MCP_URL',
      auth: 'MCP_TOKEN',
      // v1.2: ONE embedded MCP. Tool-providing connectors (xsiam,
      // cortex-xdr, web, cortex-docs, cortex-content) live in the
      // bundle and are loaded by this MCP; their per-instance configs
      // come from the connector-instances surface, not from
      // per-connector MCP URLs.
      connectorInstances: [
        { id: 'embedded-mcp', urlEnv: 'MCP_URL', tokenEnv: 'MCP_TOKEN', required: true },
      ],
    },
  },
  lifecycle: {
    standalone: {
      start: 'scripts/agent_lifecycle.sh start',
      stop: 'scripts/agent_lifecycle.sh stop',
      restart: 'scripts/agent_lifecycle.sh restart',
      status: 'scripts/agent_lifecycle.sh status',
      health: 'scripts/agent_lifecycle.sh health',
      export: 'scripts/agent_lifecycle.sh export',
    },
    bundle: {
      exportScript: 'scripts/export_agent_bundle.sh',
      importScript: 'scripts/import_agent_bundle.sh',
      signature: 'optional-hmac-sha256',
      secretBinding: 'provider-references',
    },
  },
} as const;

export const agentWorkflows: AgentWorkflow[] = [
  {
    id: 'monitor-cases',
    title: 'Monitor open cases',
    prompt:
      'List the open Cortex XSOAR cases from the last 24 hours, ordered by severity, and flag the ones that need investigation first.',
    requiredTools: ['xsoar_list_incidents'],
    outputs: ['open_cases', 'triage_order', 'recommended_first_case'],
  },
  {
    id: 'investigate-case',
    title: 'Investigate a case end-to-end',
    prompt:
      'Pick the highest-severity open XSOAR case, fetch its full record and war-room narrative, enrich the related indicators, summarize what happened with the key evidence, and recommend next steps.',
    requiredTools: ['xsoar_get_incident', 'xsoar_get_war_room', 'xsoar_search_indicators'],
    outputs: ['case_summary', 'evidence_timeline', 'recommended_next_steps'],
  },
  {
    id: 'document-and-resolve',
    title: 'Document findings and update the case',
    prompt:
      'Write the investigation summary as a war-room note on the case, set the appropriate severity and owner, and close the case with a reason and closing notes if the investigation is complete.',
    requiredTools: ['xsoar_add_note', 'xsoar_update_incident', 'xsoar_close_incident'],
    outputs: ['war_room_note', 'updated_fields', 'closure_disposition'],
  },
  {
    id: 'web-research',
    title: 'Research a CVE or IOC on the web',
    prompt:
      'Open the vendor advisory for the given CVE, extract the readable text, and summarize impact and remediation guidance with source links.',
    requiredTools: ['guardian_web_navigate', 'guardian_web_get_text', 'guardian_web_extract_links'],
    outputs: ['advisory_summary', 'remediation_steps', 'source_links'],
  },
];
