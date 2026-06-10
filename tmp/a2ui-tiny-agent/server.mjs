import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL(".", import.meta.url));
const port = Number(process.env.PORT || 4177);

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".jsonl": "application/jsonl; charset=utf-8",
  ".md": "text/markdown; charset=utf-8"
};

let eventCounter = 0;

function jsonResponse(res, status, body) {
  res.writeHead(status, { "content-type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(body));
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 1_000_000) {
        reject(new Error("Request body too large"));
        req.destroy();
      }
    });
    req.on("end", () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (error) {
        reject(error);
      }
    });
  });
}

function eventToDataUpdate(input) {
  eventCounter += 1;
  const timestamp = new Date().toLocaleTimeString();

  if (input.event === "agent.message.send") {
    const text = String(input.payload?.text || "").trim();
    return {
      appendMessages: [
        { role: "user", text },
        { role: "assistant", text: `Demo response ${eventCounter}: I received "${text}".` }
      ],
      appendActivity: [
        { kind: "event", label: `${timestamp} handled agent.message.send` },
        { kind: "tool", label: "mock_agent_reply completed" }
      ],
      latestResult: {
        title: "Message handled",
        body: "The renderer emitted an event, the backend accepted it, and the client merged the returned data update."
      },
      composer: { value: "" }
    };
  }

  if (input.event === "agent.workflow.start") {
    const workflowId = String(input.payload?.workflowId || "");
    return {
      appendMessages: [
        { role: "assistant", text: `Started workflow: ${workflowId}.` }
      ],
      appendActivity: [
        { kind: "workflow", label: `${timestamp} started ${workflowId}` },
        { kind: "tool", label: "mock_workflow_runner completed" }
      ],
      latestResult: {
        title: "Workflow started",
        body: `The ${workflowId} workflow returned a mocked result from the event bridge.`
      }
    };
  }

  if (input.event === "agent.session.select") {
    return {
      activeSessionId: String(input.payload?.sessionId || "s1"),
      appendActivity: [
        { kind: "session", label: `${timestamp} switched session` }
      ],
      latestResult: {
        title: "Session selected",
        body: "A session selection event updated the data model."
      }
    };
  }

  return {
    appendActivity: [
      { kind: "warning", label: `${timestamp} unknown event: ${input.event}` }
    ],
    latestResult: {
      title: "Unknown event",
      body: "The event bridge did not recognize this event."
    }
  };
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url || "/", `http://${req.headers.host}`);

    if (req.method === "POST" && url.pathname === "/agent/a2ui/events") {
      const input = await readJsonBody(req);
      return jsonResponse(res, 200, {
        version: "v0.9",
        updateDataModel: {
          surfaceId: "home",
          mode: "merge",
          data: eventToDataUpdate(input)
        }
      });
    }

    let pathname = url.pathname === "/" ? "/renderer/index.html" : url.pathname;
    const requested = normalize(pathname).replace(/^(\.\.[/\\])+/, "");
    const filePath = join(root, requested);
    if (!filePath.startsWith(root)) {
      return jsonResponse(res, 403, { error: "Forbidden" });
    }

    const content = await readFile(filePath);
    const contentType = mimeTypes[extname(filePath)] || "application/octet-stream";
    res.writeHead(200, { "content-type": contentType });
    res.end(content);
  } catch (error) {
    if (error.code === "ENOENT") {
      return jsonResponse(res, 404, { error: "Not found" });
    }
    return jsonResponse(res, 500, { error: error.message });
  }
});

server.listen(port, "127.0.0.1", () => {
  console.log(`Tiny A2UI demo: http://127.0.0.1:${port}`);
});
