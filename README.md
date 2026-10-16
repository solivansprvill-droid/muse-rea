# muse-rea — REA for Muse

A [Muse](https://muse.ai) skill that brings **REA (Reverse Engineer
Anything)** to Meta's Muse personal agent: inspect native executables and
libraries, .NET assemblies, Electron and JavaScript applications, Android
packages, firmware images, and packet/browser captures, and get structured
Evidence back (decompiled code, call graphs, application graphs, captures)
for the agent to explain or build from.

This is the Muse counterpart of Nous Research's official
[Hermes Agent REA plugin](https://hermes-agent.nousresearch.com/docs/plugins/rea):
same upstream, same pinned version (`rea-agents@6.4.0`), driven through
REA's one-shot CLI instead of its MCP server, with a wrapper that adds a
safety gate sized for a personal agent.

> Unofficial adaptation. Not affiliated with or endorsed by Nous Research
> or Meta. REA itself is the work of [morluto](https://github.com/morluto/rea)
> and is MIT-licensed (see Attribution).

## Requirements

- Node.js 22.19+, 24.11+ or 26+ with `npx` on PATH (REA does not support
  Node 23 or 25). The first run downloads the pinned package into npm's
  cache.
- Nothing else for static JavaScript/Electron/ASAR analysis, archive and
  package inventory, Go/Rust binary metadata, PE resources, .NET metadata
  and saved HAR captures.
- Bring your own engine for the rest, exactly as upstream requires: Ghidra
  plus a JDK for native decompilation, the JADX headless MCP JAR for
  Android code, apktool / Binwalk / Unblob / TShark for their formats. REA
  never installs these, and this skill instructs the agent not to either —
  it reports what is missing and lets the user decide.

## Install

Clone this repository as a Muse custom skill:

```bash
git clone https://github.com/solivansprvill-droid/muse-rea \
  ~/workspace/custom-skills/rea
```

Muse picks the skill up from `SKILL.md`; no other registration is needed.

## Usage

Through the wrapper (what the agent runs):

```bash
python3 scripts/rea.py doctor                       # engine availability
python3 scripts/rea.py commands --filter android    # ~170 REA commands
python3 scripts/rea.py caps --effects               # capability/effect map
python3 scripts/rea.py run inspect-artifact <path>
python3 scripts/rea.py run analyze-javascript-application <app-dir>
```

The wrapper appends `--format json`, prints a summary head, and saves the
full Evidence output under `~/workspace/rea-evidence/` (override with the
`REA_EVIDENCE_DIR` environment variable). Large outputs can be paged with
REA's own `--filter-output`, `--token-limit` and `--token-offset` flags,
which the wrapper passes through.

## Safety gate

Read-only static analysis runs directly. Hard-gated command categories are
refused by the wrapper until the agent passes `--allow-effects`, which the
skill allows only after the user approves the exact command and target in
chat:

- `capture-*` / `observe-*` scenario runners — they execute or drive the
  target program;
- ADB mutators (`install-adb-package`, `push-adb-file`, `start-adb-app`, ...)
  — they change a connected Android device;
- `extract-*`, `import-*`, `annotate-*` and `evidence-export` — they write
  to caller-chosen paths.

Decompiler output is treated as pseudocode, not original source; the skill
requires conclusions to cite their `evidence_id`.

## Scope verified on the reference VM (Ubuntu 24.04, Node 24.20)

Working: `inspect-artifact` on an ELF binary (structured Evidence),
`analyze-javascript-application` on a sample Electron app, safety-gate
refusals for `capture-process` and `install-adb-package`. Unavailable
without engines, by design: Ghidra-backed native decompilation and JADX
APK inspection return clear `capability_unavailable` errors.

## Attribution

REA is made by [morluto](https://github.com/morluto) and released under the
MIT License — https://github.com/morluto/rea. This repository contains no
REA code; it downloads the pinned official npm package (`rea-agents@6.4.0`)
at runtime via `npx`. The workflow and safety model follow the design of
the Hermes Agent REA plugin (Nous Research), re-implemented here for Muse.

## License

MIT — see [LICENSE](LICENSE).
