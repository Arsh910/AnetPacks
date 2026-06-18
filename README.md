<h1 align="center">ANet Packs</h1>

<p align="center">Shareable workspaces for <a href="https://github.com/Arsh910/Anet">ANet</a> — a community home for packs.</p>

---

## What's a pack?

A **pack** is a complete ANet workspace bundled into one folder you can share: its
config (models/providers), custom **tools** and **agents**, **MCP** wiring, learned
**skills**, and persona. Hand someone a pack and they get your *exact* setup — the
same capabilities, ready to use.

A pack is just files, so it's portable and reviewable:

```
<pack>/
├── anet.config.yaml      models / providers
├── exanet.config.yaml    which tools & agents are wired up
├── ExTools/  ExAgents/   custom tools and agents (real code)
├── mcps/                 MCP server configs
├── skills/               learned procedures
└── SOUL.md               persona
```

## What this repo is for

A place to **share and discover** ANet packs — purpose-built setups others can
install and build on (a "DevOps" pack, a "research analyst" pack, a "frontend"
pack, and so on). Browse, grab one that fits, or contribute your own.

## Using a pack

With ANet installed, add a pack from its zip and switch to it:

```text
/packsmith add <path-to-pack.zip>
/changepack <pack-name>
```

ANet imports it into `~/.anet/shared_packs/`, asks for any API keys it needs, and
runs only the setup its README documents.

## Making one

Build a workspace in ANet (`/packsmith new`, then `/newtool` · `/newagent` ·
`/addmcp`), then bundle it:

```text
/packsmith share
```

This produces a zip with **all secrets stripped** and a generated README, ready to
share here.

## A note on trust

A pack contains **runnable code** (tools, MCP servers). Treat installing one like
installing an extension — review what's inside before you activate it. Secrets are
never bundled: you supply your own API keys locally.

---

<p align="center"><sub>For ANet itself, see the <a href="https://github.com/Arsh910/Anet">main repo</a>. MIT licensed.</sub></p>
