# Cleanup Inventory

Recorded before deletion on 2026-09-07.

| Path | Purpose | Referenced by | Decision |
|---|---|---|---|
| `docs/development/cleanup-inventory.md` | Pre-deletion file inventory and disposition record | Task 1 cleanup record | keep |
| `docs/development/presweep-findings.md` | Sensitive-content scan findings and actions | Public release review | keep |
| `.gitignore` | Publication exclusions for generated, secret, and machine-specific files | Git | keep |
| `machine.example.json` | Sanitized schema example replacing live machine output | README and resolver documentation | keep |
| `CHANGELOG.md` | Release history and verified 0.1.0 baseline | Publication readers | keep |
| `CONTRIBUTING.md` | Module and target contribution contract | Contributors | keep |
| `CREDITS.md` | Upstream attribution and verified licence record | README | keep |
| `LICENSE` | MIT terms for this repository | Package users | keep |
| `SECURITY.md` | Private vulnerability reporting policy | Public repository security tab | keep |
| `docs/development/SECURITY-REVIEW.md` | Security findings and triage record | Release checklist | keep |
| `PUSH-CHECKLIST.md` | Public-release exit tests and repository settings | Release owner | keep |
| `docs/harness.md` | Dated operating contract and evidence map | Agents and operators | keep |
| `docs/CLIENTS.md` | Client target shapes and verification status | README and deployment | keep |
| `docs/LOCAL-MODELS.md` | llama.cpp provider requirements and limits | README and provider CLI | keep |
| `core/provider.py` | Provider discovery, emission, and preflight dispatch | CLI and preflight | keep |
| `core/provider_api.py` | Provider writer context contract | Provider plugins | keep |
| `core/budget.py` | Tool catalogue count and token estimate | CLI budget command | keep |
| `providers/llamacpp/provider.yaml` | llama.cpp provider descriptor | Runtime provider discovery | keep |
| `providers/llamacpp/writer.py` | llama.cpp outputs and stage 9 checks | Provider dispatcher | keep |
| `tests/test_provider.py` | Provider emission, budget, and stage 9 tests | Baseline replay | keep |
| `scripts/replay-baseline.ps1` | Reusable amended-contract replay | Stage 4 validation | keep |
| `core/context.py` | Detected-client harness and skill delivery | CLI emit-context command | keep |
| `docs/skill.md` | Shared operational procedure emitted with the harness | Context delivery | keep |
| `tests/test_context.py` | Context deduplication and preservation tests | Baseline replay | keep |
| `docs/CONCEPTS.md` | Model, provider, client, server, and host definitions | README and local-model docs | keep |
| `core/detect.py` | Application, client, provider, and writability detection | CLI detect and emit auto | keep |
| `core/uninstall.py` | Header-scoped generated-entry removal | deploy-uninstall.bat | keep |
| `tests/test_deploy.py` | Auto-selection, merge, and uninstall tests | Baseline replay | keep |
| `deploy.bat` | Operator-driven detect, context, emit, and preflight launcher | Deployment | keep |
| `deploy-uninstall.bat` | Header-scoped generated configuration removal | Deployment rollback | keep |
| `core/emit/writer_api.py` | Target-neutral writer context and shared rendering primitives | Discovered target writers | keep |
| `targets/copilot-cli/writer.py` | Drop-in Copilot CLI target writer | Runtime target discovery | keep |
| `targets/vscode-copilot/writer.py` | Drop-in VS Code target writer | Runtime target discovery | keep |
| `targets/codex/target.yaml` | Codex TOML target descriptor | Runtime target discovery | keep |
| `targets/codex/writer.py` | Codex TOML target writer | Runtime target discovery | keep |
| `targets/claude-code/target.yaml` | Claude Code JSON target descriptor | Runtime target discovery | keep |
| `targets/claude-code/writer.py` | Claude Code JSON target writer | Runtime target discovery | keep |
| `targets/claude-desktop/target.yaml` | Claude Desktop JSON target descriptor | Runtime target discovery | keep |
| `targets/claude-desktop/writer.py` | Claude Desktop JSON target writer | Runtime target discovery | keep |
| `targets/cline/target.yaml` | Cline extension and CLI target descriptor | Runtime target discovery | keep |
| `targets/cline/writer.py` | Cline JSON target writer with empty autoApprove | Runtime target discovery | keep |
| `targets/kilocode/target.yaml` | Kilo Code current MCP target descriptor | Runtime target discovery | keep |
| `targets/kilocode/writer.py` | Kilo Code mcp-object target writer | Runtime target discovery | keep |
| `targets/cursor/target.yaml` | Cursor JSON target descriptor | Runtime target discovery | keep |
| `targets/cursor/writer.py` | Cursor JSON target writer | Runtime target discovery | keep |
| `targets/opencode/target.yaml` | OpenCode verified-shape target descriptor | Runtime target discovery | keep |
| `targets/opencode/writer.py` | OpenCode mcp-object target writer | Runtime target discovery | keep |
| `targets/continue/target.yaml` | Continue YAML and JSON-fallback target descriptor | Runtime target discovery | keep |
| `targets/continue/writer.py` | Continue multi-artifact target writer | Runtime target discovery | keep |
| `.venv/.gitignore` | Generated local Python environment | uv run | delete |
| `.venv/.lock` | Generated local Python environment | uv run | delete |
| `.venv/CACHEDIR.TAG` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/__editable__.bentley_mcp_adapter-0.1.0.pth` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/__editable___bentley_mcp_adapter_0_1_0_finder.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/__pycache__/__editable___bentley_mcp_adapter_0_1_0_finder.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/__pycache__/_virtualenv.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/_virtualenv.pth` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/_virtualenv.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/_yaml/__init__.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/bentley_mcp_adapter-0.1.0.dist-info/direct_url.json` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/bentley_mcp_adapter-0.1.0.dist-info/entry_points.txt` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/bentley_mcp_adapter-0.1.0.dist-info/INSTALLER` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/bentley_mcp_adapter-0.1.0.dist-info/METADATA` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/bentley_mcp_adapter-0.1.0.dist-info/RECORD` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/bentley_mcp_adapter-0.1.0.dist-info/REQUESTED` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/bentley_mcp_adapter-0.1.0.dist-info/top_level.txt` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/bentley_mcp_adapter-0.1.0.dist-info/uv_build.json` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/bentley_mcp_adapter-0.1.0.dist-info/uv_cache.json` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/bentley_mcp_adapter-0.1.0.dist-info/WHEEL` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/pyyaml-6.0.3.dist-info/INSTALLER` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/pyyaml-6.0.3.dist-info/licenses/LICENSE` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/pyyaml-6.0.3.dist-info/METADATA` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/pyyaml-6.0.3.dist-info/RECORD` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/pyyaml-6.0.3.dist-info/REQUESTED` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/pyyaml-6.0.3.dist-info/top_level.txt` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/pyyaml-6.0.3.dist-info/WHEEL` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__init__.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/__init__.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/composer.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/constructor.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/cyaml.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/dumper.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/emitter.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/error.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/events.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/loader.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/nodes.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/parser.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/reader.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/representer.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/resolver.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/scanner.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/serializer.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/__pycache__/tokens.cpython-313.pyc` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/_yaml.cp313-win_amd64.pyd` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/composer.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/constructor.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/cyaml.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/dumper.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/emitter.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/error.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/events.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/loader.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/nodes.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/parser.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/reader.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/representer.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/resolver.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/scanner.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/serializer.py` | Generated local Python environment | uv run | delete |
| `.venv/Lib/site-packages/yaml/tokens.py` | Generated local Python environment | uv run | delete |
| `.venv/pyvenv.cfg` | Generated local Python environment | uv run | delete |
| `.venv/Scripts/activate` | Generated local Python environment | uv run | delete |
| `.venv/Scripts/activate.bat` | Generated local Python environment | uv run | delete |
| `.venv/Scripts/activate.csh` | Generated local Python environment | uv run | delete |
| `.venv/Scripts/activate.fish` | Generated local Python environment | uv run | delete |
| `.venv/Scripts/activate.nu` | Generated local Python environment | uv run | delete |
| `.venv/Scripts/activate.ps1` | Generated local Python environment | uv run | delete |
| `.venv/Scripts/activate.xsh` | Generated local Python environment | uv run | delete |
| `.venv/Scripts/activate_this.py` | Generated local Python environment | uv run | delete |
| `.venv/Scripts/bentley-adapter.exe` | Generated local Python environment | uv run | delete |
| `.venv/Scripts/deactivate.bat` | Generated local Python environment | uv run | delete |
| `.venv/Scripts/pydoc.bat` | Generated local Python environment | uv run | delete |
| `.venv/Scripts/python.exe` | Generated local Python environment | uv run | delete |
| `.venv/Scripts/pythonw.exe` | Generated local Python environment | uv run | delete |
| `baseline.txt` | Behavior-preservation contract for cleanup | Task 1 exit test | keep |
| `core/__init__.py` | Adapter runtime source | bentley-adapter entry point and tests | keep |
| `core/__main__.py` | Adapter runtime source | bentley-adapter entry point and tests | keep |
| `core/__pycache__/__init__.cpython-313.pyc` | Generated Python bytecode cache | Python interpreter | delete |
| `core/__pycache__/cli.cpython-313.pyc` | Generated Python bytecode cache | Python interpreter | delete |
| `core/__pycache__/common.cpython-313.pyc` | Generated Python bytecode cache | Python interpreter | delete |
| `core/cli.py` | Adapter runtime source | bentley-adapter entry point and tests | keep |
| `core/common.py` | Adapter runtime source | bentley-adapter entry point and tests | keep |
| `core/emit/__init__.py` | Adapter runtime source | bentley-adapter entry point and tests | keep |
| `core/emit/__pycache__/__init__.cpython-313.pyc` | Generated Python bytecode cache | Python interpreter | delete |
| `core/emit/__pycache__/emitter.cpython-313.pyc` | Generated Python bytecode cache | Python interpreter | delete |
| `core/emit/emitter.py` | Adapter runtime source | bentley-adapter entry point and tests | keep |
| `core/preflight/__init__.py` | Adapter runtime source | bentley-adapter entry point and tests | keep |
| `core/preflight/__pycache__/__init__.cpython-313.pyc` | Generated Python bytecode cache | Python interpreter | delete |
| `core/preflight/__pycache__/checks.cpython-313.pyc` | Generated Python bytecode cache | Python interpreter | delete |
| `core/preflight/__pycache__/mcp_client.cpython-313.pyc` | Generated Python bytecode cache | Python interpreter | delete |
| `core/preflight/checks.py` | Adapter runtime source | bentley-adapter entry point and tests | keep |
| `core/preflight/mcp_client.py` | Adapter runtime source | bentley-adapter entry point and tests | keep |
| `core/resolve/__init__.py` | Adapter runtime source | bentley-adapter entry point and tests | keep |
| `core/resolve/__pycache__/__init__.cpython-313.pyc` | Generated Python bytecode cache | Python interpreter | delete |
| `core/resolve/__pycache__/resolver.cpython-313.pyc` | Generated Python bytecode cache | Python interpreter | delete |
| `core/resolve/resolver.py` | Adapter runtime source | bentley-adapter entry point and tests | keep |
| `core/tiers/__init__.py` | Adapter runtime source | bentley-adapter entry point and tests | keep |
| `core/tiers/__pycache__/__init__.cpython-313.pyc` | Generated Python bytecode cache | Python interpreter | delete |
| `core/tiers/__pycache__/policy.cpython-313.pyc` | Generated Python bytecode cache | Python interpreter | delete |
| `core/tiers/policy.py` | Adapter runtime source | bentley-adapter entry point and tests | keep |
| `dist/.gitignore` | Generated distribution artefact | uv build and wheel validation | delete |
| `dist/bentley_mcp_adapter-0.1.0-py3-none-any.whl` | Generated distribution artefact | uv build and wheel validation | delete |
| `docs/INSTALL.md` | Operator documentation | README and handover | keep |
| `docs/MACHINE-VARIANCE.md` | Operator documentation | README and handover | keep |
| `docs/PORTS.md` | Operator documentation | README and handover | keep |
| `docs/TROUBLESHOOTING.md` | Operator documentation | README and handover | keep |
| `HANDOVER.md` | Verification status and known limits | Operators and publication docs | keep |
| `machine.json` | Live machine discovery output | resolve, emit, preflight | delete |
| `modules/microstation/module.yaml` | Drop-in application descriptor | core.common and package data | keep |
| `modules/plaxis2d-input/module.yaml` | Drop-in application descriptor | core.common and package data | keep |
| `modules/plaxis2d-output/module.yaml` | Drop-in application descriptor | core.common and package data | keep |
| `modules/staadpro/module.yaml` | Drop-in application descriptor | core.common and package data | keep |
| `profiles/site.example.yaml` | Operator site-profile template | README and emitter | keep |
| `pyproject.toml` | Python package and entry-point definition | Build backend and installers | keep |
| `README.md` | Repository entry documentation | Operators and contributors | keep |
| `targets/copilot-cli/target.yaml` | Drop-in client descriptor | core.emit and package data | keep |
| `targets/vscode-copilot/target.yaml` | Drop-in client descriptor | core.emit and package data | keep |
| `tests/__pycache__/test_adapter.cpython-313.pyc` | Generated Python bytecode cache | Python interpreter | delete |
| `tests/test_adapter.py` | Fault and policy test suite | baseline and contributors | keep |
| `uv.lock` | Pinned adapter dependency resolution | uv | keep |
