# Changelog

## 0.1.0 - 2026-09-07

- Added Windows machine discovery with known-folder and registry resolution.
- Added MicroStation, STAAD.Pro, PLAXIS 2D Input, and PLAXIS 2D Output modules.
- Added GitHub Copilot and VS Code configuration writers.
- Added Read, Guided write, and Full capability tiers.
- Added eight ordered preflight stages with distinct exit codes.
- Added explicit PLAXIS port-owner and collision detection.
- Added runtime-discovered client target writers.
- Added llama.cpp provider discovery, provider guidance, catalogue budgets,
  Full-tier refusal, and optional preflight stage 9.
- Added smart detection, verified-only automatic emission, check mode, and
  generated-entry uninstall.
- Added automatic harness and skill delivery for detected clients.
- Recorded the absent-provider result without claiming a local model chain.
- Recorded the verified baseline:
  - MicroStation 2026.1 build 26.00.01.65, 25 tools.
  - STAAD.Pro 2026 version 26.0.0.340.
  - PLAXIS 2D 2023.2.1.1079 with a locally patched, upstream-uncertified
    `plaxis-mcp` 0.3.5 runtime profile.
  - GitHub Copilot app 1.0.83-5.
- Corrected PLAXIS compatibility: the 2023.2 proof used an uncertified local
  runtime-profile patch, while stock 0.3.5 accepts exact upstream ABIs and
  declares `current-312` for the 2024.2+ generation.
- Recorded PLAXIS 2D 2025.1.3.5 as known incompatible with pinned
  `plaxis-mcp` 0.3.5 after stock discovery and isolated V3 runtime tests.
