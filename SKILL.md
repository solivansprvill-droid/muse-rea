# REA — Reverse Engineering for Muse (Muse edition of the Hermes REA plugin)

Use REA (morluto/rea, MIT; pinned `rea-agents@6.4.0` on npm) to reverse
engineer programs the user points at: native executables and libraries, .NET
assemblies, Electron/JavaScript applications, Android packages, firmware
images, packet and browser captures. REA returns structured Evidence
(decompiled code, call graphs, application graphs, captures); Muse explains
it or builds from it. It adapts the same pinned upstream as Nous Research's Hermes Agent
REA plugin, driven through REA's CLI instead of its MCP server.

## How to run

Always go through the wrapper, never call `npx rea-agents` directly:

```
python3 scripts/rea.py doctor
python3 scripts/rea.py commands --filter android
python3 scripts/rea.py caps --effects
python3 scripts/rea.py run inspect-artifact <path>
python3 scripts/rea.py run analyze-javascript-application <dir>
```

- First REA task in a session: run `doctor` once and state plainly which
  engines are available before promising analysis depth.
- The wrapper appends `--format json`, enforces the safety gate below, and
  saves full output to `~/workspace/rea-evidence/` (it prints the path).
  Evidence can be large: summarise first, then page into detail with REA's
  own `--filter-output <keys>`, `--token-limit` and `--token-offset` flags
  passed through `run`.

## Target routing (starting points; `commands` lists all ~170)

- Any file, unknown type → `inspect-artifact` (format, hashes, inventory,
  suggested next probes). Safe on everything.
- Native ELF/PE metadata and layout → `inspect-binary-layout`; function-level
  work → `function`, `decompile` (needs a native engine, see status below).
- JavaScript / Electron / web bundles → `analyze-javascript-application`,
  `analyze-web-bundle`, `decompile` for JS parts. No engine needed.
- Android APK → `inspect-android-package`, `inspect-android-class`,
  `inspect-android-method`, `decode-android-resources` (needs JADX/apktool,
  see status below).
- Firmware → `inspect-artifact` first; `extract-firmware` is effectful
  (writes files) and needs Binwalk/Unblob.
- Saved captures (HAR, process, browser) → the `compare-*` / `inspect-*`
  families; live captures are effectful (see gate).

## Safety gate (hard rules)

- Read-only static analysis: proceed without asking. (REA's `capabilities`
  effect flags describe its own provider subprocesses, not target execution;
  the wrapper prints them as a note but does not gate on them.)
- Hard-gated categories — the wrapper refuses these without
  `--allow-effects`: all `capture-*` / `observe-*` scenario runners (they
  execute or drive the target), all ADB mutators (`install-adb-package`,
  `push-adb-file`, `start-adb-app`, ...), `extract-*`, `import-*`,
  `annotate-*`, and `evidence-export` (writes/overwrites the path given).
  Before using `--allow-effects`: name the exact command, the exact target
  (command line, app, device, output path) and what it will do, and get the
  user's explicit approval in chat.
- Never execute an untrusted target outside REA's capture commands, and
  never with standing approval: approval is per command and per target.
- Missing engines are reported, never installed by the agent: REA's own rule
  is "bring your own engine" (Ghidra+JDK, JADX headless MCP JAR, apktool,
  Binwalk/Unblob, TShark...). State what's missing and what it would unlock;
  installing is the user's decision.
- Treat decompiler output as pseudocode, not original source. Cross-check
  consequential claims against assembly/references, label inferred names
  and types, and report missing symbols and analysis warnings. Cite the
  `evidence_id` behind any conclusion.

## Verified environment status (2026-10-16, the reference VM)

- Node v24.20.0 with npx — meets REA's requirement (22.19+ / 24.11+ / 26).
- Works with no external engine: artifact inventory, ELF/PE metadata and
  layout, Go/Rust binary metadata, PE resources, .NET metadata, static
  JavaScript/Electron/ASAR analysis, archive inventory, saved HAR captures.
  Smoke-tested: `inspect-artifact /usr/bin/ls` (structured Evidence) and
  `analyze-javascript-application` on a sample Electron app.
- Not installed: Ghidra (native decompilation depth), the JADX headless MCP
  JAR (`REA_JADX_MCP_JAR`; APK inspection stops with a clear
  capability_unavailable error), apktool, Binwalk/Unblob, Hopper/IDA
  (macOS/commercial). JDK 17 exists under ~/workspace/toolchain if a future
  Ghidra install is approved.
