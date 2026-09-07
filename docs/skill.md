# Bentley MCP operating procedure

Use this procedure with `harness.md`. The harness governs behavior if the two
documents conflict.

1. Run `bentley-adapter resolve`.
2. Complete the version record in the site profile.
3. Start each intended application with a disposable model or project open.
4. Run `bentley-adapter preflight`.
5. Stop on any failed stage. Do not reinterpret a port or model failure as a
   credential problem.
6. Read current state before mutation.
7. State the intended change and read-back.
8. Make one logical change.
9. Read back the affected fields.
10. Record the tool call and result.

Never auto-approve arbitrary code, key-in, project file, or calculation tools.
Never place credentials in prompts, config files, logs, or command arguments.
No result is an engineering conclusion until reviewed by a qualified engineer.

