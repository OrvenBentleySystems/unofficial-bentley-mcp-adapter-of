# Push checklist

Review date: 2026-09-07.

## Task 1: sensitive content

- [x] Full tree scanned, including hidden and ignored files.
- [x] Live `machine.json` and generated client configs removed from the
  publication tree.
- [x] No operator name, machine name, user-profile path, client project name,
  credential value, internal URL, email, screenshot, log, or transcript
  remains in publishable files.
- [x] No password appeared in the repository. No rotation is required from
  repository contents.
- [x] No `.git` directory exists. The first commit is clean by construction;
  there was no history to inspect or rewrite.

## Task 2: purpose and cleanup

- [x] Every file has a purpose recorded in
  `docs/development/cleanup-inventory.md`.
- [x] Generated environments, wheels, caches, metadata, and live machine state
  are excluded.
- [x] `baseline.txt` remains at root because it is the active contract.
- [x] `HANDOVER.md` remains at root because it carries release limits.
- [x] Development findings and cleanup inventory are under
  `docs/development/`.

## Task 3: security

- [x] `pip-audit`: PyYAML 6.0.3, no known vulnerabilities.
- [x] `bandit`: high-severity findings fixed; remaining findings are triaged in
  `docs/development/SECURITY-REVIEW.md`.
- [x] YAML parsing uses `yaml.safe_load`.
- [x] Provider host and alias injection blocked.
- [x] Output roots bounded; reparse points rejected; random exclusive temp
  files used.
- [x] Uninstall restricted to declared target paths and matching source
  metadata.
- [x] `SECURITY.md` provides a private reporting route.

After push, enable:

- [ ] Dependabot alerts
- [ ] Dependabot security updates
- [ ] Secret scanning with push protection
- [ ] CodeQL default setup
- [ ] GitHub private vulnerability reporting

## Task 4: accuracy

- [x] Verified client status is separated from shape-only status.
- [x] Local llama.cpp chain is labelled unverified at each capability claim.
- [x] PLAXIS 2023.2 local-patch verification is distinguished from stock
  upstream support; 2024.2+ remains unverified until runtime attestation and
  live probes pass.
- [x] README disclaimer states unofficial personal project, no vendor support,
  proprietary MicroStation early access, unresolved entitlement, and required
  engineering review.
- [x] Attribution URLs and licences rechecked.

## Task 5: repository hygiene

- [x] Standard Python and project-specific ignores are present.
- [x] Root MIT licence matches package metadata.
- [x] README stays below 200 lines and preserves required section order.
- [x] No privileged fork workflow exists. No CI workflow is shipped.

Recommended repository topics:

`mcp`, `model-context-protocol`, `bentley`, `microstation`, `staad-pro`,
`plaxis`, `aec`, `structural-engineering`, `geotechnical`

## Task 6: final replay

- [x] Cloud preflight: 8/8.
- [x] Baseline tests: 14/14.
- [x] Full suite: 45 tests, with one platform-dependent symlink test skipped
  when Windows did not permit symlink creation.
- [x] Copilot CLI and VS Code reference configs byte-identical.
- [x] All 24 original wheel entries intact; 29 additive entries.
- [x] Console entry point unchanged.
- [x] Wheel installed.
- [x] Clean-copy deployment check changed no existing source file.

## Release decision

Clear to publish as an unverified local-model release. Do not claim that a
llama.cpp engineering chain works until `llama-server` is installed on the
operator machine with `--jinja`, stage 9 passes, and a Read-tier MicroStation
and STAAD.Pro chain completes without a cloud call.
