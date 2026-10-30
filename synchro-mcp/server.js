"use strict";
/*
 * synchro-mcp v0 — agent access to Bentley SYNCHRO 4D Pro.
 *
 * Two proven doors, one MCP server:
 *  1. synchro_script  - emit SYNCHRO Script phrase files (documented grammar,
 *     extracted from the product's own help). User adds + runs them in the app
 *     (Preview -> Run, undoable): bulk read/condition/set operations on the
 *     live project: tasks, resources, assignments, links, user fields, 3D.
 *  2. synchro_status  - report the bundled headless SDK (synchrojs native
 *     addon) load state and version. The addon can build .sp files without
 *     the GUI; schedule-visible authoring lives in the script channel.
 *
 * Zero npm dependencies. Plain Node >= 18 (tested on v24).
 */

const fs = require("fs");
const path = require("path");

const SDK_ROOT =
  process.env.SYNCHRO_APP_ROOT ||
  "C:\\Program Files\\Bentley\\SYNCHRO\\4D Pro\\synchro-imodel-bridge-win32-x64\\resources\\app\\node_modules\\synchrojs\\src\\index.js";

const GRAMMAR = [
  "Phrase format: <OBJECT>[(condition)] <COMMAND> - one operation per line.",
  "Objects: TASK, RESOURCE, 3D, ASSIGNMENT, PARENT, LINK, TO_LINK, LINKED_TO_TASK, LINKED_FROM_TASK;",
  "  chains: TASK.RESOURCE, RESOURCE.TASK, TASK.TASK, TASK.SUCCESSOR, TASK.PREDECESSOR, TASK.ASSIGNMENT, 3D.TASK ...",
  "Conditions: (NAME == \"X\"), (!=, <, >, <=, >=, <>), AND/OR/NOT, states STARTED FINISHED LEAF HAS_PARENT.",
  "Commands: SET <property> = <value>, SUM/COUNT over PROPERTY(\"name\"), user fields via PROPERTY(\"...\").",
  "Comments: // line  /* block */. See docs/SYNCHRO-MCP.md for the full grammar reference.",
].join(" ");

function loadSdk() {
  try {
    const synchro = require(SDK_ROOT);
    let version = null;
    try { version = synchro.SynchroVersion ? synchro.SynchroVersion() : null; } catch { /* optional */ }
    return { ok: true, version, error: null };
  } catch (e) {
    return { ok: false, version: null, error: String(e.message || e).slice(0, 200) };
  }
}

function validateScript(lines) {
  if (!Array.isArray(lines) || lines.length < 1 || lines.length > 500) {
    return "lines must be an array of 1..500 phrase strings";
  }
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (typeof line !== "string" || line.length === 0 || line.length > 1000) {
      return `lines[${i}] must be a string of 1..1000 characters`;
    }
    // eslint-disable-next-line no-control-regex
    if (/[\x00-\x08\x0b-\x1f]/.test(line)) return `lines[${i}] contains control characters`;
  }
  return null;
}

function toolResult(payload, isError = false) {
  return { content: [{ type: "text", text: JSON.stringify(payload, null, 2) }], isError };
}

const TOOLS = [
  {
    name: "synchro_status",
    description:
      "Report SYNCHRO install + bundled headless SDK state (synchrojs native addon loadable from plain Node). Read-only.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
  },
  {
    name: "synchro_script",
    description:
      `Write a SYNCHRO Script phrase file for bulk operations on the OPEN project. ${GRAMMAR} ` +
      `The user loads it in the app (Project Controls > SYNCHRO Script > right-click > Add External Script), ` +
      `presses Preview, then Run; every change is undoable in the app.`,
    inputSchema: {
      type: "object",
      properties: {
        lines: {
          type: "array",
          minItems: 1,
          maxItems: 500,
          items: { type: "string", minLength: 1, maxLength: 1000 },
          description: "One phrase per entry, e.g. 'TASK(NAME == \"Excavation\") SET START = 01.11.2026'",
        },
        out_path: {
          type: "string",
          pattern: "\\.txt$",
          description: "Absolute .txt path to write (UTF-8)",
        },
      },
      required: ["lines", "out_path"],
      additionalProperties: false,
    },
  },
];

function callTool(name, args) {
  if (name === "synchro_status") {
    const sdk = loadSdk();
    return toolResult({
      sdk,
      script_channel: "synchro_script writes phrase files; user runs them in-app (Preview, Run, undoable)",
    });
  }
  if (name === "synchro_script") {
    const err = validateScript(args.lines);
    if (err) return toolResult({ error: err }, true);
    const out = String(args.out_path || "");
    if (!path.isAbsolute(out) || !out.toLowerCase().endsWith(".txt")) {
      return toolResult({ error: "out_path must be an absolute .txt path" }, true);
    }
    try {
      fs.mkdirSync(path.dirname(out), { recursive: true });
      fs.writeFileSync(out, args.lines.join("\r\n") + "\r\n", "utf8");
    } catch (e) {
      return toolResult({ error: `write failed: ${e.message}` }, true);
    }
    return toolResult({
      written: out,
      phrases: args.lines.length,
      how_to_run:
        "In SYNCHRO: Project Controls ribbon > SYNCHRO Script > right-click list > Add External Script > select file > Preview > Run. Undo via View ribbon.",
    });
  }
  return toolResult({ error: `unknown tool ${name}` }, true);
}

/* --- newline-delimited JSON-RPC (MCP stdio) --- */

function send(msg) {
  process.stdout.write(JSON.stringify(msg) + "\n");
}

let buffer = "";
process.stdin.on("data", (chunk) => {
  buffer += chunk.toString("utf8");
  let idx;
  while ((idx = buffer.indexOf("\n")) >= 0) {
    const line = buffer.slice(0, idx).trim();
    buffer = buffer.slice(idx + 1);
    if (!line) continue;
    let msg;
    try { msg = JSON.parse(line); } catch { continue; }
    handle(msg);
  }
});

function handle(msg) {
  const { id, method, params } = msg;
  if (method === "initialize") {
    send({
      jsonrpc: "2.0",
      id,
      result: {
        protocolVersion: (params && params.protocolVersion) || "2025-06-18",
        capabilities: { tools: {} },
        serverInfo: { name: "synchro-mcp", version: "0.1.0" },
      },
    });
  } else if (method === "notifications/initialized" || method === "notifications/cancelled") {
    /* notification, no reply */
  } else if (method === "ping") {
    send({ jsonrpc: "2.0", id, result: {} });
  } else if (method === "tools/list") {
    send({ jsonrpc: "2.0", id, result: { tools: TOOLS } });
  } else if (method === "tools/call") {
    const result = callTool(params.name, params.arguments || {});
    send({ jsonrpc: "2.0", id, result });
  } else if (id !== undefined) {
    send({ jsonrpc: "2.0", id, error: { code: -32601, message: `unsupported method: ${method}` } });
  }
}
