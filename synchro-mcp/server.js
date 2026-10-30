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
const os = require("os");
const path = require("path");

const SDK_ROOT =
  process.env.SYNCHRO_APP_ROOT ||
  "C:\\Program Files\\Bentley\\SYNCHRO\\4D Pro\\synchro-imodel-bridge-win32-x64\\resources\\app\\node_modules\\synchrojs\\src\\index.js";

const DEFAULT_CSV = path.join(os.tmpdir(), "bentley_mcp", "synchro_dump.csv");

const DUMP_TEMPLATE = [
  "// SYNCHRO 4D Pro schedule dump for synchro-mcp (v0).",
  "// Run: Project Controls > SYNCHRO Script > Add (paste) > Run.",
  "// Method names mirror the verified CSharp_* exports of SynchroAPI.dll",
  "// (2026-10-30). If the editor's autocomplete shows PascalCase variants",
  "// (GetAllTasks vs getAllTasks), accept the suggestion - the shape holds.",
  "using System;",
  "using System.Globalization;",
  "using System.IO;",
  "using System.Text;",
  "",
  "var project = Synchro.Actives.Project;",
  "var sb = new StringBuilder();",
  "Func<object, string> S = v => v == null ? \"\" : Convert.ToString(v, CultureInfo.InvariantCulture);",
  "Func<string, string> Q = s => \"\\\"\" + (s ?? \"\").Replace(\"\\\"\", \"\\\"\\\"\") + \"\\\"\";",
  "var tasks = project.getAllTasks();",
  "for (int i = 0; i < tasks.size(); i++) {",
  "    var t = tasks.at(i);",
  "    sb.AppendLine(string.Join(\",\",",
  "        \"TASK\", S(t.getID()), Q(t.getName()), Q(S(t.getStatus())), S(t.getType()),",
  "        Q(S(t.getDuration())), Q(S(t.getPlannedStartTime())),",
  "        Q(S(t.getActualStartTime())), Q(S(t.getActualFinishTime()))));",
  "}",
  "for (int i = 0; i < tasks.size(); i++) {",
  "    var t = tasks.at(i);",
  "    var links = t.getUpstreamLinks();",
  "    for (int j = 0; j < links.size(); j++) {",
  "        var l = links.at(j);",
  "        sb.AppendLine(string.Join(\",\", \"LINK\", S(t.getID()),",
  "            S(l.getUpstreamTaskID()), S(l.getType()), Q(S(l.getDelay()))));",
  "    }",
  "}",
  'File.WriteAllText(@"__CSV_PATH__", sb.ToString(), Encoding.UTF8);',
  "",
].join("\r\n");

function parseCsvLine(line) {
  const fields = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"') {
        if (line[i + 1] === '"') { cur += '"'; i++; } else { quoted = false; }
      } else cur += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { fields.push(cur); cur = ""; }
    else cur += ch;
  }
  fields.push(cur);
  return fields;
}

function collectCsv(csvPath) {
  let stat;
  try { stat = fs.statSync(csvPath); } catch { return { ready: false, csv_path: csvPath, hint: "no dump yet - run action prepare, execute the script in SYNCHRO, then collect" }; }
  let rows;
  try { rows = fs.readFileSync(csvPath, "utf8").split(/\r?\n/).filter((l) => l.trim()); }
  catch (e) { return { ready: false, csv_path: csvPath, hint: `unreadable: ${e.message}` }; }
  const tasks = [];
  const links = [];
  const problems = [];
  rows.forEach((line, n) => {
    const f = parseCsvLine(line);
    if (f[0] === "TASK" && f.length >= 9) {
      tasks.push({
        id: f[1], name: f[2], status: f[3], type: f[4],
        duration: f[5], planned_start: f[6],
        actual_start: f[7], actual_finish: f[8],
      });
    } else if (f[0] === "LINK" && f.length >= 5) {
      links.push({ task_id: f[1], upstream_id: f[2], type: f[3], delay: f[4] });
    } else {
      problems.push(`line ${n + 1}: unrecognized row`);
    }
  });
  return {
    ready: true, csv_path: csvPath, generated: stat.mtime.toISOString(),
    task_count: tasks.length, link_count: links.length,
    tasks, links, problems,
  };
}

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
  {
    name: "synchro_read",
    description:
      "Read live schedule state from the open SYNCHRO project via a CSV dump. " +
      "action=prepare writes a C# dump script (verified SynchroAPI member names) for the user to " +
      "paste into Project Controls > SYNCHRO Script and Run. action=collect parses the resulting " +
      "CSV and returns {tasks:[{id,name,status,type,duration,planned_start,actual_start,actual_finish}], " +
      "links:[{task_id,upstream_id,type,delay}]}. Re-run collect after each in-app dump.",
    inputSchema: {
      type: "object",
      properties: {
        action: { type: "string", enum: ["prepare", "collect"] },
        csv_path: {
          type: "string",
          description: "Absolute .csv path (default: temp dir bentley_mcp/synchro_dump.csv)",
        },
        script_path: {
          type: "string",
          description: "Absolute .cs path for prepare (default: csv path + .cs)",
        },
      },
      required: ["action"],
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
  if (name === "synchro_read") {
    const action = args.action;
    const csv = path.isAbsolute(String(args.csv_path || ""))
      ? String(args.csv_path)
      : (args.csv_path ? null : DEFAULT_CSV);
    if (csv === null) return toolResult({ error: "csv_path must be absolute" }, true);
    if (action === "collect") {
      if (!csv.toLowerCase().endsWith(".csv")) return toolResult({ error: "csv_path must end .csv" }, true);
      return toolResult(collectCsv(csv));
    }
    if (action !== "prepare") return toolResult({ error: 'action must be "prepare" or "collect"' }, true);
    if (!csv.toLowerCase().endsWith(".csv")) return toolResult({ error: "csv_path must end .csv" }, true);
    const scriptPath = args.script_path
      ? String(args.script_path)
      : csv + ".cs";
    if (!path.isAbsolute(scriptPath) || !scriptPath.toLowerCase().endsWith(".cs")) {
      return toolResult({ error: "script_path must be an absolute .cs path" }, true);
    }
    if (!/[A-Za-z0-9_\\:\-. ]+/.test(csv) || csv.includes("..")) {
      return toolResult({ error: "csv_path contains unsupported characters" }, true);
    }
    try {
      fs.mkdirSync(path.dirname(scriptPath), { recursive: true });
      fs.writeFileSync(scriptPath, DUMP_TEMPLATE.replace("__CSV_PATH__", csv), "utf8");
    } catch (e) {
      return toolResult({ error: `write failed: ${e.message}` }, true);
    }
    return toolResult({
      script: scriptPath,
      csv_will_appear_at: csv,
      how_to_run:
        "In SYNCHRO: Project Controls > SYNCHRO Script > right-click > Add, paste the file contents, Run. Then call synchro_read action=collect.",
      note: "Member names verified against SynchroAPI.dll CSharp_* exports; if the editor suggests PascalCase variants, accept them.",
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
