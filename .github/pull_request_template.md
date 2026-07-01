<!-- Submitting or updating an ANet pack? Fill this in. CI (validate-packs) runs
     automatically; you can run it locally first:  python cicd/validate.py --submission <name> -->

## Pack

**Name:** `<name>`
**What it's for (one line):**

### Models
<!-- paste your pack's model table (from its README) -->

| Role | Model | Provider |
|---|---|---|
| Manager |  |  |
| … |  |  |

### Required API keys / prerequisites
<!-- e.g. OPENROUTER_API_KEY; Node.js for MCP X; Telegram creds for agent Y -->

---

## Submission checklist

- [ ] Layout: `<name>/<name>/` (code) + `<name>/README.md` + `<name>/<name>.zip` all present.
- [ ] `<name>.zip` was regenerated with `/packsmith share` and **matches** the code folder
      (not hand-edited). CI verifies this byte-for-byte.
- [ ] No secrets committed (no real values in any `.env`; use `.env.example`).
- [ ] No machine-specific absolute paths in `mcps/*/config.yaml`.
- [ ] Every agent has `model` + `provider`; `memory.backend` is `recmem` or `mem0`.
- [ ] README documents the models and required keys.
- [ ] `python cicd/validate.py --submission <name>` passes locally.
