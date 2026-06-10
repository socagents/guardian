import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = dirname(fileURLToPath(import.meta.url));

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function getPath(obj, pointer) {
  return pointer
    .replace(/^\//, "")
    .split("/")
    .filter(Boolean)
    .reduce((value, key) => value?.[key], obj);
}

const manifest = JSON.parse(await readFile(join(root, "manifest.json"), "utf8"));
const catalog = JSON.parse(await readFile(join(root, manifest.ui.catalogs[0].path), "utf8"));
const surfaceText = await readFile(join(root, manifest.ui.surfaces[0].path), "utf8");
const messages = surfaceText.trim().split("\n").map((line) => JSON.parse(line));

assert(manifest.ui.protocol === "a2ui", "Manifest protocol must be a2ui");
assert(messages[0].createSurface, "Surface must start with createSurface");

const dataMessage = messages.find((message) => message.updateDataModel);
const componentMessage = messages.find((message) => message.updateComponents);
assert(dataMessage, "Surface must include updateDataModel");
assert(componentMessage, "Surface must include updateComponents");

const data = dataMessage.updateDataModel.data;
const components = componentMessage.updateComponents.components;
const ids = new Set();

for (const component of components) {
  assert(!ids.has(component.id), `Duplicate component id: ${component.id}`);
  ids.add(component.id);
  const definition = catalog.components[component.component];
  assert(definition, `Unknown component: ${component.component}`);

  for (const required of definition.required || []) {
    assert(component[required] !== undefined, `${component.id} is missing required prop: ${required}`);
  }

  for (const [prop, propDefinition] of Object.entries(definition.props || {})) {
    const value = component[prop];
    if (value === undefined) continue;

    if (propDefinition.type === "componentId") {
      assert(components.some((candidate) => candidate.id === value), `${component.id}.${prop} points to missing component: ${value}`);
    }

    if (propDefinition.type === "componentIdList") {
      for (const child of value) {
        assert(components.some((candidate) => candidate.id === child), `${component.id}.${prop} points to missing component: ${child}`);
      }
    }

    if (propDefinition.type === "eventName") {
      assert(catalog.events[value], `${component.id}.${prop} uses unknown event: ${value}`);
    }

    if (prop.endsWith("Path")) {
      assert(getPath(data, value) !== undefined, `${component.id}.${prop} points to missing data path: ${value}`);
    }
  }
}

assert(ids.has(manifest.ui.surfaces[0].root), "Manifest root component must exist in surface");
console.log(`Validated ${components.length} components, ${Object.keys(catalog.events).length} events, and ${messages.length} A2UI messages.`);
