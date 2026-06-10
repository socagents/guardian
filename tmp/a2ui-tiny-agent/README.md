# Tiny A2UI Agent Demo

This is a no-dependency demo of the A2UI pattern:

1. `manifest.json` declares the agent UI contract.
2. `catalogs/base-agent-ui.v0.1.json` declares trusted renderable components and events.
3. `surfaces/home.jsonl` streams A2UI-style messages:
   - `createSurface`
   - `updateDataModel`
   - `updateComponents`
4. `renderer/renderer.js` validates component names, maps them to trusted browser renderers, binds JSON data paths, and emits named events.
5. `server.mjs` serves the files and handles `/agent/a2ui/events`.

No A2UI package is required for this sample. A2UI is used here as a protocol shape and architectural pattern. In a production platform you can adopt Google's schemas/renderers where they fit, but you still define your own catalog and trusted renderer mappings for your components.

Run:

```bash
node validate.mjs
node server.mjs
```

Open:

```text
http://127.0.0.1:4177
```
