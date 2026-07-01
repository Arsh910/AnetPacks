# mypack — an ANet pack

> The first pack in the **AnetPacks** repo, and the one I use day-to-day. A
> general-purpose setup: strong code + research models, a Telegram notifier, a
> code-graph and a browser MCP, and RecMem long-term memory.

An **ANet pack** is a self-contained workspace folder — models, custom tools,
custom agents, MCP wiring, learned skills, and a persona — that you activate with
`/changepack`. This README is also the **template** every pack in this repo should
follow (see [Using this as a template](#using-this-as-a-template) and the
[Submission checklist](#submission-checklist)).

---

## At a glance

| | |
|---|---|
| **Engine** | AdaptOrch (task-adaptive: decompose → DAG → route → execute → synthesize) |
| **Memory** | RecMem (3-tier recurrence memory) — `memory.backend: recmem` |
| **Primary provider** | OpenRouter (everything routes through one `OPENROUTER_API_KEY`) |
| **Built-in agents** | 4 (research · code · computer · checker) |
| **Custom agents** | 1 — `tele_agent` (Telegram notifier) |
| **Custom tools** | 1 — `tele_tool` |
| **MCP servers** | 2 — `codegraph`, `playwright` |
| **Skills** | 1 example |
| **Persona** | `SOUL.md` — "Anet": precise, direct, no filler |

---

## Models

Every agent runs through **OpenRouter**. Nothing here needs a paid search key
(web search uses DuckDuckGo).

| Role | Model | Notes |
|---|---|---|
| **Manager** (plans & coordinates) | `anthropic/claude-sonnet-4.6` | the router/decomposer/synthesizer brain |
| **research_agent** | `openai/gpt-5.4-mini` | web research, fetch, downloads |
| **code_agent** | `anthropic/claude-haiku-4.5` | + MCP `codegraph`, `playwright` |
| **computer_agent** | `nex-agi/nex-n2-pro:free` | Windows desktop automation |
| **checker_agent** | `nex-agi/nex-n2-pro:free` | validates other agents' output |
| **tele_agent** (custom) | `openai/gpt-oss-20b:free` | sends Telegram messages/files |

> The **memory** and per-stage **orchestration** models default to the manager
> model; both can be overridden in `anet.config.yaml` (see the commented blocks).

---

## What's inside

### Custom agent — `tele_agent`
Sends Telegram messages, photos, and documents. Enabled in `exanet.config.yaml`;
auto-routed on requests like *"notify via telegram"* / *"send file via telegram"*.
Uses the `tele_tool` below. **Requires** Telegram credentials (see
[Requirements](#requirements)).

### Custom tool — `tele_tool`
The Python tool `tele_agent` calls to talk to the Telegram Bot API.
Lives in `ExTools/tele_tool/`.

### MCP servers
| Server | Purpose | Prereq |
|---|---|---|
| **codegraph** | Code-graph search/context for `code_agent` (symbols, references, impacted files) | `npm i -g codegraph` + a built `codegraph.js`, then index a project once |
| **playwright** | Full browser automation for `code_agent` | Node.js (`npx @playwright/mcp`) |

### Skills
`skills/example_skill.md` — a starter skill. ANet writes new skills automatically
after complex, self-corrected tasks and injects relevant ones into future tasks.

### Persona
`SOUL.md` defines **Anet**: precise, direct, no sycophancy, one-line confirmations.
Injected into the manager's prompts only.

---

## Requirements

| Need | For | How |
|---|---|---|
| `OPENROUTER_API_KEY` | **all agents** (required) | add to `~/.anet/.env` via `/keys` |
| Node.js | `codegraph` + `playwright` MCP | install Node; MCPs launch via `node`/`npx` |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | `tele_agent` only | put in `ExAgents/tele_agent/.env` |

> ⚠️ **Portability note (codegraph):** `mcps/codegraph/config.yaml` currently points
> at an **absolute path** on the author's machine. Before this pack works elsewhere,
> that path must be corrected for the target machine (or the server installed
> globally and the arg pointed at the global binary). A submitted pack should not
> hard-code machine-specific absolute paths — see the [checklist](#submission-checklist).

---

## Use this pack

```text
/packsmith add <path-or-zip-of-this-pack>   # install it into ~/.anet/shared_packs/
/changepack mypack                          # activate it
/keys                                       # add OPENROUTER_API_KEY (+ Telegram creds if using tele_agent)
```

Then just talk to ANet. `/agents`, `/tools`, `/mcps` show what loaded.

---

## Pack structure

Every pack — including yours — is exactly this layout:

```text
mypack/
├── anet.config.yaml     # models · memory · context · skills · persona · orchestration
├── exanet.config.yaml   # which ExTools/ExAgents are registered + built-in attachments
├── SOUL.md              # persona injected into the manager
├── ExTools/<name>/      # custom tools — __init__.py exporting run() + SCHEMA
├── ExAgents/<name>/     # custom agents — prompt.md (+ optional .env for secrets)
├── mcps/<name>/         # MCP server configs — config.yaml (command + args)
└── skills/<name>.md     # learned procedures
```

- `anet.config.yaml` sets models/providers per agent and the memory/engine config.
- `exanet.config.yaml` is the **only** place external tools/agents are wired — the
  core `anet/` package is never touched.
- **Secrets never ship:** each integration's `.env` (e.g. Telegram creds) stays
  local and is stripped when a pack is exported.

---

## Using this as a template

To author a new pack for this repo, copy this folder's structure and:

1. Replace the models in `anet.config.yaml` with your choices (keep `memory.backend`
   and the `context` block — they're the current engine defaults).
2. Register only the tools/agents you actually ship in `exanet.config.yaml`
   (leave `tools:`/`agents:` empty if none).
3. Write a README **in this format** — the [At a glance](#at-a-glance),
   [Models](#models), [What's inside](#whats-inside), and [Requirements](#requirements)
   sections are what reviewers and CI read.
4. Run the [Submission checklist](#submission-checklist) before opening a PR.

---

## Submission checklist

A pack is ready to submit when all of these hold (these map to the CI checks):

- [ ] **Submission layout**: `<name>/<name>/` (pack code) + `<name>/README.md` +
      `<name>/<name>.zip` — all three present.
- [ ] **Zip integrity** *(the critical supply-chain check)*: `<name>.zip` is a faithful
      PackSmith export — every file in it exists in the reviewed `<name>/` folder
      **byte-for-byte**, and it contains no paths PackSmith always strips
      (`node_modules/`, `__pycache__/`, `.git/`, `.env`). The installed artifact must
      equal the reviewed code. Regenerate the zip with ANet's `/packsmith share`,
      then drop it at the submission root — never hand-edit it.
- [ ] `anet.config.yaml` and `exanet.config.yaml` are **valid YAML**.
- [ ] `memory.backend` is `recmem` or `mem0`; `context` block present.
- [ ] Every agent has a `model` + `provider`; providers are one of
      `openrouter · google · openai · anthropic · vertex_google · vertex_anthropic`.
- [ ] No **secrets** committed — no real values in any `.env`; no keys/tokens in YAML.
- [ ] No **machine-specific absolute paths** in `mcps/*/config.yaml` (use relative
      paths / global binaries / documented install steps).
- [ ] Every ExTool referenced in `exanet.config.yaml` exists under `ExTools/<name>/`
      and exports `run()` + `SCHEMA`; every ExAgent has its `prompt_file`.
- [ ] Every MCP named in an agent's `mcp:` list exists under `mcps/<name>/`.
- [ ] A **README** in this format documenting models + required keys.

---

<sub>Part of the **AnetPacks** repo · activate with <code>/changepack</code> · MIT.</sub>
