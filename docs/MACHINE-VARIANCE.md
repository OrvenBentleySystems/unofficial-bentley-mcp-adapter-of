# Machine Variance

Every deployment begins with `resolve`. It writes `machine.json`, and every
downstream component reads that file. No emitter or preflight module performs
its own installation discovery.

| Variance | Resolution |
|---|---|
| Username with dots, spaces, or non-ASCII | Resolve User Profile and Local AppData through Windows known-folder APIs. Never interpolate a username. Quote emitted paths. |
| Redirected or OneDrive-synced profile folders | Record real known-folder paths and sync roots. Warn when the working directory is under a sync root. |
| Non-C: install drive | Enumerate registry uninstall records and PLAXIS discovery output. Do not hardcode Program Files. |
| Several installed versions | Enumerate all matching records. The operator selects one in the site profile and records it. |
| PLAXIS 2D and 3D installed | Apply the standing port map before connection. Treat this as the normal case. |
| Python absent from PATH, or several Pythons | Record absolute interpreter paths. Keep the PLAXIS worker interpreter bound to its generated profile. |
| Node.js absent | Report it before MicroStation configuration. Do not substitute an unverified runtime. |
| `uv` or `uvx` absent | Install it during deployment or use the OpenSTAAD `.mcpb` path. Do not download at adapter runtime. |
| Unsigned binaries blocked | Use the signed `plaxis-mcp` Windows package. |
| Locked-down LocalAppData or roaming profiles | Use the supported explicit profile directory and record it in the site profile. |
| Paths longer than 260 characters | Enable Windows long paths or use a shallow working directory such as `C:\mcp-work`. |
| Non-admin user | Install the MicroStation MCP MSI with elevation before running the adapter as a normal user. |
| Antivirus or EDR blocks stdio children | Record the product event and approved exception. Do not disable endpoint protection. |

## `machine.json` fields

- `host`: Windows and Python versions, account, admin state, long-path state.
- `known_folders`: Windows-resolved User Profile and Local AppData.
- `working_directory`: resolved path, detected sync roots, sync containment.
- `executables`: absolute paths for Node.js, `uv`, `uvx`, and Python 3.13.
- `installations`: all matching registry records for each supported product.
- `microstation`: MCP bundle, cached tool inventory, and bridge log.
- `plaxis.profiles`: generated Input and Output profile locations.

`machine.json` contains paths and machine metadata. It is ignored by Git and
must not be committed. `machine.example.json` documents the public schema.
