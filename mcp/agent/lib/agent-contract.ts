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
    id: 'investigate-cases',
    title: 'Investigate cases',
    prompt:
      'List the most recent XSIAM cases with their issues, pick the highest-severity open case, and summarize what happened with the key evidence.',
    requiredTools: ['xsiam_get_cases', 'xsiam_get_issues'],
    outputs: ['case_summary', 'key_issues', 'recommended_next_steps'],
  },
  {
    id: 'author-xql-query',
    title: 'Author an XQL query',
    prompt:
      'Author an XQL query that answers the investigation question. Pull similar examples from the xql-examples knowledge base as a pattern prior, then run the query against the tenant and report the results.',
    requiredTools: ['xsiam_find_xql_examples_rag', 'xsiam_get_xql_examples', 'xsiam_run_xql_query'],
    outputs: ['xql_query', 'query_results', 'citations'],
  },
  {
    id: 'asset-context',
    title: 'Pull asset context',
    prompt:
      'Fetch the inventory entry for the asset involved in the current case and report its owner, exposure, and related findings.',
    requiredTools: ['xsiam_get_assets', 'xsiam_get_asset_by_id'],
    outputs: ['asset_profile', 'exposure_summary'],
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
