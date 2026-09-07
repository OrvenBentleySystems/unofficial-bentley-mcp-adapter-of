# PLAXIS Port Allocation

## Standing allocation

| Application | Role | Port |
|---|---|---:|
| PLAXIS 2D | Input | 10000 |
| PLAXIS 2D | Output | 10001 |
| PLAXIS 3D | Input | 10002 |
| PLAXIS 3D | Output | 10003 |
| Reserved | Future or second install | 10004 to 10009 |

PLAXIS 2D keeps its product defaults. PLAXIS 3D moves because both Input
applications otherwise claim port 10000.

## Rules

1. **The application owns the port.** Set it in PLAXIS under Expert,
   Configure remote scripting server. The MCP process follows the application.
2. **Never use a `PLAXIS_*` environment variable to change an endpoint.**
   `plaxis-mcp serve` rejects endpoint environment overrides by design.
3. **Regenerate profiles after every port change.** Run `plaxis-mcp setup`, or
   use the approved profile-directory workflow. A stale profile can make a port
   collision look like a bad password.
4. **Preflight proves ownership before authentication.** It enumerates all
   listening process IDs for the configured port. More than one owner produces
   `PORT_COLLISION`. A wrong single owner produces
   `PORT_IDENTITY_MISMATCH`. Neither is reported as a credential failure.
5. **Keep generated password strength.** Passwords remain in Windows Credential
   Manager. They do not belong in configuration, command lines, logs,
   screenshots, or chat.
6. **Support one 2D and one 3D installation per machine.** Multiple
   installations of the same generation remain unverified until profile
   binding is proven separately.

Record this map in the site profile and version record. The same ownership rule
applies to any future port-based Bentley component. OpenSTAAD HTTP mode is not
part of Stages 0 to 3; if used later, it stays on loopback and requires an
explicit bearer token.

