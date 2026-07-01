#!/usr/bin/env python3
"""
validate.py — submission validator for ANet packs.

Runs the pack submission checklist (see any pack's README) as automated checks so
CI can gate PRs. Pure stdlib + PyYAML; it NEVER imports/executes pack code — ExTools
are checked statically (source scan + byte-compile), so validating an untrusted pack
is safe.

Usage:
    python validate.py <path>...            # validate one or more packs
    python validate.py --scan <root>        # find & validate every pack under <root>
    python validate.py --scan . --changed   # only packs touched vs origin/main (CI)

A "pack" is any directory containing an `anet.config.yaml`.

Exit code: 0 if every pack passes (no ERRORs); 1 if any pack has an ERROR.
Warnings never fail the build — they're advisory.
"""
from __future__ import annotations

import argparse
import hashlib
import py_compile
import re
import subprocess
import sys
import zipfile
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required — `pip install pyyaml`", file=sys.stderr)
    sys.exit(2)

# ── Policy ────────────────────────────────────────────────────────────────────

PROVIDERS = {
    "openrouter", "google", "openai", "anthropic",
    "vertex_google", "vertex_anthropic", "vertex_claude", "claude",  # incl. legacy aliases
}
MEMORY_BACKENDS = {"recmem", "mem0"}
README_SECTIONS = ("## Models", "## Requirements")

# Absolute / machine-specific paths that break portability.
ABS_PATH_RE = re.compile(r"[A-Za-z]:[\\/]|^/(?:home|Users|mnt|opt|usr|var|root|tmp)/", re.I)

# Likely-committed secrets (scanned in YAML text).
SECRET_RES = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),                       # OpenAI/Anthropic-style
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),                      # GitHub token
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),              # Slack
    re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),           # Telegram bot token
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), # JWT
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9/+_-]{16,}"),
]

# Built-in tools a pack may attach without registering (kept in sync loosely; unknown
# names are WARN, not ERROR, since the core evolves independently of this script).
BUILTIN_TOOLS = {
    "file_tool", "edit_tool", "shell_tool", "code_execution", "grep_tool", "glob_tool",
    "lsp_tool", "diagnose_tool", "conflict_tool", "process_tool", "web_search",
    "web_fetch", "download_file", "open_app", "checker", "todo_tool", "memory_tool",
    "spawn_tool", "ask_user", "compare_screenshot",
}


class Report:
    def __init__(self, pack: Path):
        self.pack = pack
        self.errors: list[str] = []
        self.warns: list[str] = []

    def err(self, msg: str):  self.errors.append(msg)
    def warn(self, msg: str): self.warns.append(msg)

    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        head = f"[{'PASS' if self.ok() else 'FAIL'}] {self.pack}"
        lines = [head]
        for e in self.errors:
            lines.append(f"   ERROR  {e}")
        for w in self.warns:
            lines.append(f"   warn   {w}")
        if self.ok() and not self.warns:
            lines.append("   all checks passed")
        return "\n".join(lines)


# ── Loading helpers ─────────────────────────────────────────────────────────────

def _load_yaml(path: Path, rep: Report, label: str):
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        rep.err(f"{label}: invalid YAML — {exc}")
        return None


def _iter_strings(obj):
    """Yield every string leaf in a nested dict/list."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_strings(v)


# ── Individual checks ─────────────────────────────────────────────────────────

def check_configs(pack: Path, rep: Report) -> tuple[dict, dict]:
    anet_path = pack / "anet.config.yaml"
    exanet_path = pack / "exanet.config.yaml"
    if not anet_path.exists():
        rep.err("missing anet.config.yaml (not a pack?)")
        return {}, {}
    anet = _load_yaml(anet_path, rep, "anet.config.yaml") or {}
    exanet = _load_yaml(exanet_path, rep, "exanet.config.yaml") if exanet_path.exists() else {}
    exanet = exanet or {}

    # memory backend + context
    mem = anet.get("memory") or {}
    backend = mem.get("backend")
    if backend is not None and backend not in MEMORY_BACKENDS:
        rep.err(f"memory.backend '{backend}' invalid (expected one of {sorted(MEMORY_BACKENDS)})")
    if not anet.get("context"):
        rep.warn("no `context` block — the short-term rolling window will use code defaults")

    # agents: model + provider + valid provider
    for name, cfg in (anet.get("agents") or {}).items():
        if not isinstance(cfg, dict):
            rep.err(f"agent '{name}': config must be a mapping")
            continue
        if not cfg.get("model"):
            rep.err(f"agent '{name}': missing `model`")
        prov = cfg.get("provider")
        if not prov:
            rep.err(f"agent '{name}': missing `provider`")
        elif prov not in PROVIDERS:
            rep.err(f"agent '{name}': provider '{prov}' not in {sorted(PROVIDERS)}")

    mgr = anet.get("manager") or {}
    if mgr:
        if not mgr.get("model"):
            rep.err("manager: missing `model`")
        if mgr.get("provider") and mgr["provider"] not in PROVIDERS:
            rep.err(f"manager: provider '{mgr['provider']}' not in {sorted(PROVIDERS)}")

    return anet, exanet


def check_secrets(pack: Path, rep: Report):
    # committed .env files must not carry real values
    for env in pack.rglob(".env"):
        if "__pycache__" in env.parts:
            continue
        for i, line in enumerate(env.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            _, _, val = line.partition("=")
            if val.strip().strip("'\""):
                rep.err(f"{env.relative_to(pack)}:{i} — committed .env with a real value "
                        f"(commit an empty .env or a .env.example with placeholders)")
    # secret-looking strings anywhere in the YAML configs
    for cfg in ("anet.config.yaml", "exanet.config.yaml"):
        p = pack / cfg
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for rx in SECRET_RES:
            m = rx.search(text)
            if m:
                rep.err(f"{cfg}: looks like a hard-coded secret near '{m.group(0)[:12]}...'")
                break


def check_mcps(pack: Path, rep: Report, anet: dict, exanet: dict):
    mcp_dir = pack / "mcps"
    present = {d.name for d in mcp_dir.iterdir()
              if d.is_dir() and d.name != "__pycache__"} if mcp_dir.exists() else set()

    # each mcp config: valid, has `command`, no absolute paths
    for name in present:
        cfg_path = mcp_dir / name / "config.yaml"
        if not cfg_path.exists():
            rep.warn(f"mcps/{name}/ has no config.yaml")
            continue
        cfg = _load_yaml(cfg_path, rep, f"mcps/{name}/config.yaml")
        if cfg is None:
            continue
        if not cfg.get("command"):
            rep.err(f"mcps/{name}/config.yaml: missing `command`")
        for s in _iter_strings(cfg):
            if ABS_PATH_RE.search(s):
                rep.err(f"mcps/{name}/config.yaml: machine-specific absolute path '{s}' "
                        f"(use a relative path / global binary / documented install)")
                break

    # every mcp referenced by an agent must exist
    referenced = set()
    for cfg in (anet.get("agents") or {}).values():
        if isinstance(cfg, dict):
            referenced |= set(cfg.get("mcp") or [])
    for a in (exanet.get("agents") or []):
        if isinstance(a, dict):
            referenced |= set(a.get("mcp") or [])
    for name in referenced - present:
        rep.err(f"agent references MCP '{name}' but mcps/{name}/ does not exist")


def check_extools(pack: Path, rep: Report, exanet: dict):
    for tool in (exanet.get("tools") or []):
        if not isinstance(tool, dict):
            continue
        name = tool.get("name", "?")
        rel = tool.get("path") or f"ExTools/{name}"
        tdir = pack / rel
        init = tdir / "__init__.py"
        if not init.exists():
            rep.err(f"tool '{name}': {rel}/__init__.py not found")
            continue
        src = init.read_text(encoding="utf-8", errors="ignore")
        if not re.search(r"\b(async\s+def|def)\s+run\b", src):
            rep.err(f"tool '{name}': {rel}/__init__.py does not define `run(...)`")
        if not re.search(r"\bSCHEMA\b", src):
            rep.err(f"tool '{name}': {rel}/__init__.py does not define `SCHEMA`")
        try:
            py_compile.compile(str(init), doraise=True)
        except py_compile.PyCompileError as exc:
            rep.warn(f"tool '{name}': __init__.py does not byte-compile — {exc.msg.splitlines()[-1]}")


def check_exagents(pack: Path, rep: Report, exanet: dict):
    registered_tools = {t.get("name") for t in (exanet.get("tools") or []) if isinstance(t, dict)}
    for a in (exanet.get("agents") or []):
        if not isinstance(a, dict):
            continue
        name = a.get("name", "?")
        pf = a.get("prompt_file")
        if pf and not (pack / pf).exists():
            rep.err(f"agent '{name}': prompt_file '{pf}' not found")
        if not pf and not a.get("system_prompt"):
            rep.warn(f"agent '{name}': no prompt_file or system_prompt")
        for t in (a.get("tools") or []):
            if t not in registered_tools and t not in BUILTIN_TOOLS:
                rep.warn(f"agent '{name}': tool '{t}' is neither registered nor a known built-in")


def check_readme(pack: Path, rep: Report):
    readme = pack / "README.md"
    if not readme.exists():
        rep.warn("no README.md (submissions should document models + required keys)")
        return
    text = readme.read_text(encoding="utf-8", errors="ignore")
    missing = [s for s in README_SECTIONS if s not in text]
    if missing:
        rep.warn(f"README.md missing section(s): {', '.join(missing)}")


# ── Submission-level checks: <name>/ = <name>/<code> + README.md + <name>.zip ──

def _content_hash(data: bytes) -> str:
    """Hash a file's content. Text is newline-normalised (dodges git autocrlf
    false-positives across OSes); binary is hashed raw."""
    try:
        data = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    except UnicodeDecodeError:
        pass
    return hashlib.sha256(data).hexdigest()


# PackSmith (anet/AnetTools/pack_tool) strips these building the zip, so a GENUINE
# export never contains them. Kept in sync with its _STRIP_DIRS / _STRIP_EXACT /
# _is_secret_env. Their presence in a submitted zip means it isn't a real export.
_ZIP_FORBIDDEN_DIRS = {"__pycache__", "node_modules", ".git", "archived"}
_ZIP_FORBIDDEN_EXACT = {".usage.json"}


def _forbidden_in_zip(rel: str) -> bool:
    parts = rel.split("/")
    if any(p in _ZIP_FORBIDDEN_DIRS for p in parts):
        return True
    base = parts[-1]
    return (base in _ZIP_FORBIDDEN_EXACT or base == ".env"
            or (base.endswith(".env") and base != ".env.example"))


# PackSmith legitimately makes the zip differ from the source folder, so we don't
# false-alarm on those:
#   • it EMBEDS/regenerates a README.md into the pack  -> READMEs/LICENSE: not compared
#   • all YAML config is author-tweakable + goes stale between exports -> WARN, not fail
# Strict (byte-identical) comparison is kept for the CODE / instruction surface —
# .py tool code, prompts, skills, data files.
#
# ⚠ SECURITY TRADEOFF: `config.yaml` here includes mcps/*/config.yaml, which defines
# the `command`+`args` an MCP server EXECUTES. Relaxing it (chosen deliberately — MCP
# configs go stale between exports) means a swapped MCP command in the zip is only a
# WARNING, not a failure. The zip's command is still reviewable (it prints in the
# report), and the folder config is still checked for machine-specific absolute paths.
# To re-harden, remove "config.yaml" from this set so MCP configs compare strictly.
_LENIENT_CONFIGS = {"anet.config.yaml", "exanet.config.yaml", "config.yaml"}


def _zip_policy(rel: str) -> str:
    base = rel.rsplit("/", 1)[-1]
    if base == "README.md" or base.upper().startswith("LICENSE"):
        return "doc"        # PackSmith embeds/regenerates a README; docs aren't code
    if base in _LENIENT_CONFIGS:
        return "config"     # declarative YAML — a content diff is a WARN (regenerate to sync)
    return "code"           # strict


def check_zip(zip_path: Path, pack_dir: Path, name: str, rep: Report):
    """THE supply-chain check: every EXECUTABLE / instruction file in the installable
    .zip must exist in the reviewed folder byte-for-byte. Defends the attack where the
    .zip (what PackSmith installs) carries code the reviewed folder does not — benign
    code in <name>/<code>/, malicious code hidden in <name>.zip.

    Direction matters: we require zip ⊆ folder (by content), NOT the reverse —
    PackSmith only ever STRIPS files (node_modules, .env, vendored MCP code), so
    folder-only files are expected. Per-file policy (see _zip_policy): docs are not
    compared, YAML config diffs (incl. mcps/*/config.yaml) are warnings, and the code
    surface (.py, prompts, skills, data) is strict.
    """
    try:
        zf = zipfile.ZipFile(zip_path)
    except Exception as exc:
        rep.err(f"{zip_path.name}: not a readable zip - {exc}")
        return
    with zf:
        files = [i for i in zf.infolist() if not i.is_dir()]
        if not files:
            rep.err(f"{zip_path.name}: empty archive")
            return
        matched = 0
        for info in files:
            arc = info.filename.replace("\\", "/").lstrip("/")
            rel = arc.split("/", 1)[1] if "/" in arc else arc      # strip the <name>/ root
            if not rel:
                continue
            if _forbidden_in_zip(rel):
                rep.err(f"{zip_path.name}: contains '{arc}' — PackSmith always strips this; "
                        f"the zip is not a genuine export (possible hand-tampering)")
                continue
            policy = _zip_policy(rel)
            if policy == "doc":
                continue                                   # README embedded / pure docs
            target = pack_dir / rel
            if not target.is_file():
                if policy == "config":
                    rep.warn(f"{zip_path.name}: '{rel}' is in the zip but not the folder "
                             f"(config — confirm it's intended)")
                else:
                    rep.err(f"{zip_path.name}: '{rel}' is in the zip but NOT in the reviewed "
                            f"folder {name}/ — installable code that can't be reviewed")
                continue
            try:
                same = _content_hash(zf.read(info)) == _content_hash(target.read_bytes())
            except Exception as exc:
                rep.warn(f"{zip_path.name}: could not compare '{rel}' - {exc}")
                continue
            if same:
                matched += 1
            elif policy == "config":
                rep.warn(f"{zip_path.name}: '{rel}' differs from {name}/{rel} — config out of "
                         f"date? regenerate the zip with /packsmith share")
            else:
                rep.err(f"{zip_path.name}: '{rel}' DIFFERS from {name}/{rel} — the installed "
                        f"file is not what was reviewed (possible tampering)")
        if not rep.errors:
            rep.warn(f"zip verified: {matched} code file(s) match the reviewed folder byte-for-byte")


def check_submission(submission: Path, rep: Report):
    """Verify the submission layout — <name>/<code>/ + <name>/README.md +
    <name>/<name>.zip all present — and that the zip matches the code. Returns the
    inner pack dir (for the content checks), or None if it can't be located."""
    name = submission.name
    pack_dir = submission / name
    if not (pack_dir / "anet.config.yaml").exists():
        cands = [p.parent for p in submission.glob("*/anet.config.yaml")]
        if len(cands) == 1:
            pack_dir = cands[0]
        elif not cands:
            rep.err(f"no pack folder found (expected {name}/<pack>/anet.config.yaml)")
            return None
        else:
            rep.err(f"multiple candidate pack folders under {name}/ - expected exactly one")
            return None

    readme = submission / "README.md"
    if not readme.exists():
        rep.err(f"missing README.md at the submission root ({name}/README.md)")
    else:
        text = readme.read_text(encoding="utf-8", errors="ignore")
        miss = [s for s in README_SECTIONS if s not in text]
        if miss:
            rep.warn(f"README.md missing section(s): {', '.join(miss)}")

    zip_path = submission / f"{pack_dir.name}.zip"
    if not zip_path.exists():
        rep.err(f"missing {pack_dir.name}.zip at the submission root - the installable "
                f"artifact (must match the reviewed folder)")
    else:
        check_zip(zip_path, pack_dir, pack_dir.name, rep)
    return pack_dir


# ── Orchestration ─────────────────────────────────────────────────────────────

def validate_pack(pack: Path, rep: Report, *, pack_readme: bool = True):
    anet, exanet = check_configs(pack, rep)
    if anet or exanet:
        check_secrets(pack, rep)
        check_mcps(pack, rep, anet, exanet)
        check_extools(pack, rep, exanet)
        check_exagents(pack, rep, exanet)
        if pack_readme:
            check_readme(pack, rep)


def validate_pack_path(pack: Path) -> Report:
    rep = Report(pack)
    validate_pack(pack, rep)
    return rep


def validate_submission(submission: Path) -> Report:
    rep = Report(submission)
    pack_dir = check_submission(submission, rep)
    if pack_dir is not None:
        validate_pack(pack_dir, rep, pack_readme=False)  # README lives at submission root
    return rep


def find_packs(root: Path) -> list[Path]:
    if (root / "anet.config.yaml").exists():
        return [root]
    packs = set()
    for cfg in root.rglob("anet.config.yaml"):
        if any(part in ("__pycache__", "node_modules", ".git") for part in cfg.parts):
            continue
        packs.add(cfg.parent)
    return sorted(packs)


def find_submissions(root: Path) -> list[Path]:
    subs = set()
    for cfg in root.rglob("anet.config.yaml"):
        if any(part in ("__pycache__", "node_modules", ".git") for part in cfg.parts):
            continue
        subs.add(cfg.parent.parent)   # submission = the parent of the pack folder
    return sorted(subs)


def _filter_changed(root: Path, dirs: list[Path]) -> list[Path]:
    """Keep only dirs containing a file changed vs origin/main (for CI on a PR)."""
    try:
        base = subprocess.run(["git", "merge-base", "HEAD", "origin/main"],
                              capture_output=True, text=True, cwd=root).stdout.strip() or "origin/main"
        out = subprocess.run(["git", "diff", "--name-only", base, "HEAD"],
                             capture_output=True, text=True, cwd=root).stdout
    except Exception as exc:
        print(f"(could not compute changed files: {exc}; validating all)", file=sys.stderr)
        return dirs
    touched = {ln for ln in out.splitlines() if ln.strip()}
    hit = []
    for d in dirs:
        rel = d.relative_to(root).as_posix() if d.is_relative_to(root) else d.as_posix()
        if any(f == rel or f.startswith(rel + "/") for f in touched):
            hit.append(d)
    return hit


def main() -> int:
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")   # keep CI log capture happy
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="Validate ANet pack submissions.")
    ap.add_argument("paths", nargs="*", type=Path, help="pack (or submission) dir(s)")
    ap.add_argument("--scan", type=Path, metavar="ROOT", help="find & validate everything under ROOT")
    ap.add_argument("--changed", action="store_true", help="with --scan: only units changed vs origin/main")
    ap.add_argument("--submission", action="store_true",
                    help="treat targets as SUBMISSION dirs (<name>/<code>/ + README.md + <name>.zip) "
                         "and run the structure + zip-integrity checks in addition to the pack checks")
    args = ap.parse_args()

    if args.submission:
        units = find_submissions(args.scan) if args.scan else list(args.paths)
        runner, noun = validate_submission, "submissions"
    else:
        if args.scan:
            units = find_packs(args.scan)
        else:
            units = [p for path in args.paths for p in find_packs(path)]
        runner, noun = validate_pack_path, "packs"

    if not (args.scan or args.paths):
        ap.error("give path(s) or --scan <root>")
    if args.scan and args.changed:
        units = _filter_changed(args.scan, units)

    if not units:
        print(f"No {noun} found to validate.")
        return 0

    reports = [runner(u) for u in units]
    print("\n".join(r.render() for r in reports))
    failed = [r for r in reports if not r.ok()]
    total_warn = sum(len(r.warns) for r in reports)
    print(f"\n{len(reports) - len(failed)}/{len(reports)} {noun} passed"
          f" | {len(failed)} failed | {total_warn} warning(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
