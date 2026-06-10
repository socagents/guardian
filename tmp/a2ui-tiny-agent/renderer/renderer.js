var app = document.querySelector("#app");

var state = {
  manifest: null,
  catalog: null,
  surface: null,
  components: new Map(),
  data: {},
  rootId: null
};

function getPath(obj, pointer) {
  return pointer
    .replace(/^\//, "")
    .split("/")
    .filter(Boolean)
    .reduce(function (value, key) {
      return value == null ? undefined : value[key];
    }, obj);
}

function setPath(obj, pointer, nextValue) {
  var parts = pointer.replace(/^\//, "").split("/").filter(Boolean);
  var last = parts.pop();
  var parent = parts.reduce(function (value, key) {
    if (value[key] == null) value[key] = {};
    return value[key];
  }, obj);
  parent[last] = nextValue;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function validateComponent(component) {
  var definition = state.catalog.components[component.component];
  if (!definition) throw new Error(`Unknown component "${component.component}"`);
  for (var prop of definition.required || []) {
    if (component[prop] === undefined) {
      throw new Error(`${component.id} is missing required prop "${prop}"`);
    }
  }
}

async function loadJson(path) {
  var response = await fetch(path);
  if (!response.ok) throw new Error(`Failed to load ${path}`);
  return response.json();
}

async function loadJsonl(path) {
  var response = await fetch(path);
  if (!response.ok) throw new Error(`Failed to load ${path}`);
  var text = await response.text();
  return text.trim().split("\n").map(function (line) {
    return JSON.parse(line);
  });
}

async function emitEvent(event, payload) {
  var response = await fetch(state.manifest.ui.events.endpoint, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ event, payload })
  });

  if (!response.ok) throw new Error(`Event failed: ${event}`);
  var update = await response.json();
  applyMessage(update);
  render();
}

function applyDataUpdate(update) {
  var data = update.data || {};
  if (update.mode === "replace") {
    state.data = JSON.parse(JSON.stringify(data));
    return;
  }

  if (Array.isArray(data.appendMessages)) {
    state.data.messages = [...(state.data.messages || []), ...data.appendMessages];
  }
  if (Array.isArray(data.appendActivity)) {
    state.data.toolActivity = [...data.appendActivity, ...(state.data.toolActivity || [])].slice(0, 8);
  }
  if (data.latestResult) state.data.latestResult = data.latestResult;
  if (data.composer) state.data.composer = data.composer;
  if (data.activeSessionId) state.data.activeSessionId = data.activeSessionId;
}

function applyMessage(message) {
  if (message.createSurface) {
    state.surface = message.createSurface;
  }
  if (message.updateDataModel) {
    applyDataUpdate(message.updateDataModel);
  }
  if (message.updateComponents) {
    for (var component of message.updateComponents.components) {
      validateComponent(component);
      state.components.set(component.id, component);
    }
  }
}

function renderChild(id) {
  var component = state.components.get(id);
  if (!component) return `<div class="error">Missing component: ${escapeHtml(id)}</div>`;
  return renderComponent(component);
}

function renderPanel(component) {
  return `
    <section class="panel">
      <div class="panel-heading">
        <h2>${escapeHtml(component.title)}</h2>
        ${component.description ? `<p>${escapeHtml(component.description)}</p>` : ""}
      </div>
      ${renderChild(component.child)}
    </section>
  `;
}

function renderStack(component) {
  return `<div class="stack ${component.gap || "md"}">${component.children.map(renderChild).join("")}</div>`;
}

function renderAgentShell(component) {
  var status = getPath(state.data, component.statusPath) || "unknown";
  return `
    <div class="shell">
      <aside class="sidebar">
        <div class="brand">
          <div class="mark">A2</div>
          <div>
            <h1>${escapeHtml(component.title)}</h1>
            <p>${escapeHtml(component.subtitle || "")}</p>
          </div>
        </div>
        ${component.sidebar ? renderChild(component.sidebar) : ""}
      </aside>
      <section class="workspace">
        <header class="topbar">
          <div>
            <span class="eyebrow">A2UI pipeline demo</span>
            <h1>${escapeHtml(component.title)}</h1>
          </div>
          <span class="status"><span></span>${escapeHtml(status)}</span>
        </header>
        <div class="grid">
          <div>${renderChild(component.main)}</div>
          <div>${component.aside ? renderChild(component.aside) : ""}</div>
        </div>
      </section>
    </div>
  `;
}

function renderSessionList(component) {
  var sessions = getPath(state.data, component.itemsPath) || [];
  var active = getPath(state.data, component.activePath);
  return `
    <div class="session-list">
      ${sessions.map((session) => `
        <button class="session ${session.id === active ? "active" : ""}" data-event="${component.selectEvent}" data-session-id="${escapeHtml(session.id)}">
          <strong>${escapeHtml(session.title)}</strong>
          <span>${escapeHtml(session.updatedAt)}</span>
        </button>
      `).join("")}
    </div>
  `;
}

function renderChatSurface(component) {
  return `
    <div class="chat-surface">
      ${renderChild(component.messages)}
      ${renderChild(component.composer)}
    </div>
  `;
}

function renderMessageList(component) {
  var messages = getPath(state.data, component.itemsPath) || [];
  return `
    <div class="messages">
      ${messages.map((message) => `
        <article class="message ${escapeHtml(message.role)}">
          <span>${escapeHtml(message.role)}</span>
          <p>${escapeHtml(message.text)}</p>
        </article>
      `).join("")}
    </div>
  `;
}

function renderPromptComposer(component) {
  var value = getPath(state.data, component.valuePath) || "";
  return `
    <form class="composer" data-submit-event="${component.submitEvent}" data-value-path="${component.valuePath}">
      <textarea name="prompt" placeholder="${escapeHtml(component.placeholder || "")}">${escapeHtml(value)}</textarea>
      <button type="submit">${escapeHtml(component.submitLabel || "Send")}</button>
    </form>
  `;
}

function renderWorkflowLauncher(component) {
  var workflows = getPath(state.data, component.itemsPath) || [];
  return `
    <div class="workflows">
      ${workflows.map((workflow) => `
        <button class="workflow" data-event="${component.runEvent}" data-workflow-id="${escapeHtml(workflow.id)}">
          <strong>${escapeHtml(workflow.title)}</strong>
          <span>${escapeHtml(workflow.description)}</span>
        </button>
      `).join("")}
    </div>
  `;
}

function renderToolActivity(component) {
  var activity = getPath(state.data, component.itemsPath) || [];
  return `
    <ol class="activity">
      ${activity.map((item) => `<li><span>${escapeHtml(item.kind)}</span>${escapeHtml(item.label)}</li>`).join("")}
    </ol>
  `;
}

function renderResultViewer(component) {
  var result = getPath(state.data, component.resultPath) || {};
  return `
    <div class="result">
      <strong>${escapeHtml(result.title || "No result yet")}</strong>
      <p>${escapeHtml(result.body || "")}</p>
    </div>
  `;
}

function renderComponent(component) {
  var renderers = {
    AgentShell: renderAgentShell,
    Panel: renderPanel,
    Stack: renderStack,
    SessionList: renderSessionList,
    ChatSurface: renderChatSurface,
    MessageList: renderMessageList,
    PromptComposer: renderPromptComposer,
    WorkflowLauncher: renderWorkflowLauncher,
    ToolActivity: renderToolActivity,
    ResultViewer: renderResultViewer
  };
  return renderers[component.component]?.(component) || `<div class="error">No renderer for ${escapeHtml(component.component)}</div>`;
}

function wireEvents() {
  app.querySelectorAll("[data-event='agent.workflow.start']").forEach(function (button) {
    button.addEventListener("click", () => {
      emitEvent("agent.workflow.start", { workflowId: button.dataset.workflowId });
    });
  });

  app.querySelectorAll("[data-event='agent.session.select']").forEach(function (button) {
    button.addEventListener("click", () => {
      emitEvent("agent.session.select", { sessionId: button.dataset.sessionId });
    });
  });

  app.querySelectorAll("form[data-submit-event]").forEach(function (form) {
    var textarea = form.querySelector("textarea");
    textarea.addEventListener("input", () => setPath(state.data, form.dataset.valuePath, textarea.value));
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      var text = textarea.value.trim();
      if (text) emitEvent(form.dataset.submitEvent, { text });
    });
  });
}

function render() {
  app.innerHTML = renderChild(state.rootId);
  wireEvents();
}

async function boot() {
  try {
    state.manifest = await loadJson("../manifest.json");
    var catalogPath = `../${state.manifest.ui.catalogs[0].path}`;
    var surface = state.manifest.ui.surfaces[0];
    state.rootId = surface.root;
    state.catalog = await loadJson(catalogPath);
    var messages = await loadJsonl(`../${surface.path}`);
    messages.forEach(applyMessage);
    render();
  } catch (error) {
    app.innerHTML = `<pre class="fatal">${escapeHtml(error.stack || error.message)}</pre>`;
  }
}

boot();
