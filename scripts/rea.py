#!/usr/bin/env python3
"""Muse-side wrapper for REA (rea-agents, pinned) — the Muse edition of the
Hermes REA plugin. Drives REA's one-shot CLI over npx, with a safety gate:
hard-gated command categories (capture/observe scenario runners, ADB
mutators, extractors, importers, evidence export) are refused unless
--allow-effects is passed (the agent passes it only after the user approves
in chat). Read-only analysis commands run directly; any provider effects REA
declares for them are printed as a transparency note.

Usage:
  rea.py doctor                     REA environment health check
  rea.py commands [--filter text]   list REA CLI commands
  rea.py caps [--effects]           capability/effect summary (cached)
  rea.py run <rea-command> [args] [--allow-effects]
                                    run one REA command; full output is saved
                                    under ~/workspace/rea-evidence/ and a
                                    summary head is printed
"""
import json, os, subprocess, sys, time
from pathlib import Path

REA_VERSION = "6.4.0"
PKG = f"rea-agents@{REA_VERSION}"
CACHE = Path(os.path.expanduser("~/.cache/muse-rea"))
EVIDENCE_DIR = Path(os.environ.get("REA_EVIDENCE_DIR",
                                   os.path.expanduser("~/workspace/rea-evidence")))
TIMEOUT = int(os.environ.get("REA_TIMEOUT", "900"))

# Hard-gated command categories (semantic, mirroring the Hermes REA skill):
# these run or drive the target program, mutate a connected device, or write
# to caller-chosen paths. `rea capabilities` effects are NOT used as the gate:
# they describe REA's own provider internals (e.g. inspect_artifact declares
# launches_process because its providers are subprocesses) and would block
# nearly all read-only analysis. Capabilities are used for availability and
# for a transparency note only.
HARD_PREFIXES = ("capture-", "observe-", "extract-", "import-", "annotate-")
HARD_EXACT = {"install-adb-package", "uninstall-adb-package", "push-adb-file",
              "start-adb-app", "start-adb-activity", "stop-adb-app",
              "evidence-export", "collect-adb-bugreport"}
EFFECT_KEYS = ("launches_process", "may_write_filesystem", "may_access_network",
               "may_show_ui", "changes_permissions", "requires_root", "mutates_artifact")

def is_hard(command):
    if command in HARD_EXACT or command.startswith(HARD_PREFIXES):
        return True
    if "-adb-" in command and not command.startswith("inspect-adb"):
        return True
    return False

def npx_base():
    return ["npx", "-y", PKG]

def run_rea(args, timeout=TIMEOUT):
    p = subprocess.run(npx_base() + args, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr

def load_caps(max_age=86400):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / "capabilities.json"
    if f.exists() and time.time() - f.stat().st_mtime < max_age:
        try: return json.loads(f.read_text())
        except Exception: pass
    rc, out, err = run_rea(["capabilities", "--format", "json"], timeout=180)
    if rc != 0:
        raise SystemExit(f"rea capabilities failed (rc={rc}): {err[:300]}")
    data = json.loads(out)
    f.write_text(json.dumps(data))
    return data

def caps_index():
    data = load_caps()
    idx = {}
    for c in data.get("capabilities", []):
        idx[c.get("operation")] = c
    return idx

def classify(command):
    """Returns (tier, available, reason, effect_notes).
    tier: 'hard' (needs user approval) or 'soft' (read-only analysis)."""
    op = command.replace("-", "_")
    c = caps_index().get(op)
    available = c.get("available") if c else None
    reason = c.get("reason") if c else None
    notes = []
    if c:
        eff = c.get("effects", {}) or {}
        notes = [k for k in EFFECT_KEYS if eff.get(k)]
    return ("hard" if is_hard(command) else "soft"), available, reason, notes

def split_result(out):
    """REA streams {"rea_progress": ...} JSON lines before the final result."""
    progress, rest = [], []
    for line in out.splitlines():
        s = line.strip()
        if s.startswith('{"rea_progress"'):
            progress.append(s)
        else:
            rest.append(line)
    return progress, "\n".join(rest).strip()

def cmd_doctor():
    rc, out, err = run_rea(["doctor"], timeout=180)
    print(out or err)
    return 0

def cmd_commands(flt=None):
    rc, out, err = run_rea(["--help"], timeout=120)
    lines = []
    for line in out.splitlines():
        s = line.strip()
        if s and not s.startswith(("rea@", "Usage", "Commands")) and "  " in line:
            parts = s.split(None, 1)
            if parts and all(ch.islower() or ch.isdigit() or ch == "-" for ch in parts[0]):
                if flt and flt not in s: continue
                lines.append(s)
    print("\n".join(lines))
    print(f"\n({len(lines)} commands)")
    return 0

def cmd_caps(only_effects=False):
    idx = caps_index()
    rows = []
    for op, c in sorted(idx.items()):
        eff = c.get("effects", {}) or {}
        hit = [k for k in EFFECT_KEYS if eff.get(k)]
        if only_effects and not hit: continue
        rows.append(f"{op:42s} available={c.get('available')} effects={','.join(hit) or '-'}")
    print("\n".join(rows))
    print(f"\n({len(rows)} operations)")
    return 0

def cmd_run(argv):
    allow = "--allow-effects" in argv
    argv = [a for a in argv if a != "--allow-effects"]
    if not argv:
        print("usage: rea.py run <rea-command> [args]", file=sys.stderr); return 2
    command, rest = argv[0], argv[1:]
    tier, available, reason, notes = classify(command)
    if available is False:
        print(f"REA reports '{command}' unavailable on this host: {reason}")
        print("Do not work around this by installing engines without the user's decision.")
        return 3
    if tier == "hard" and not allow:
        print(f"BLOCKED by safety gate: '{command}' runs/drives a target, mutates a")
        print("device, or writes to a caller-chosen path (hard-gated category).")
        print("Name the exact command, target and effects to the user and get explicit")
        print("approval first; then re-run with --allow-effects.")
        return 4
    if notes:
        print(f"[gate] '{command}' declared provider effects: {', '.join(notes)} "
              f"(REA internals; proceeding as read-only analysis)")
    args = list(rest)
    if "--format" not in args:
        args += ["--format", "json"]
    try:
        rc, out, err = run_rea([command] + args)
    except subprocess.TimeoutExpired:
        print(f"rea {command} timed out after {TIMEOUT}s"); return 5
    progress, body = split_result(out)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = EVIDENCE_DIR / f"{stamp}-{command}.out"
    path.write_text(out + ("\n--- STDERR ---\n" + err if err else ""))
    print(f"[rea {command}] rc={rc} progress_events={len(progress)} full_output={path}")
    if body:
        print(body[:3500])
        if len(body) > 3500:
            print(f"\n... [{len(body) - 3500} more chars in {path}; page it with "
                  f"--filter-output / --token-limit / --token-offset]")
    elif err:
        print(err[:1500])
    return rc

def main():
    if len(sys.argv) < 2:
        print(__doc__); return 0
    sub = sys.argv[1]
    if sub == "doctor": return cmd_doctor()
    if sub == "commands":
        flt = sys.argv[sys.argv.index("--filter") + 1] if "--filter" in sys.argv else None
        return cmd_commands(flt)
    if sub == "caps": return cmd_caps("--effects" in sys.argv)
    if sub == "run": return cmd_run(sys.argv[2:])
    print(f"unknown subcommand: {sub}", file=sys.stderr); return 2

if __name__ == "__main__":
    sys.exit(main())
