# codegraph MCP

Source: repo
Repo: https://github.com/colbymchenry/codegraph.git
Install: git clone https://github.com/colbymchenry/codegraph.git && cd codegraph && npm install && npm run build
Entry: node <your-clone>/dist/bin/codegraph.js serve --mcp
Env: none

A production-grade code-graph server for AI agents: index a project once, then
query symbols, callers, file trees, and "what's affected by this change". Tools it
exposes over MCP: index, sync, query, context, files, affected, status.

## Setup (recipient)

This server runs from its **own source repo**, so its code is NOT shipped in the
pack — only this README and `config.yaml` are. To use it:

1. Clone and build it somewhere on your machine (requires Node.js):
   ```
   git clone https://github.com/colbymchenry/codegraph.git
   cd codegraph && npm install && npm run build
   ```
2. Edit `mcps/codegraph/config.yaml` so its `args` point at YOUR built entry file:
   ```yaml
   command: node
   args:
     - /absolute/path/to/your/codegraph/dist/bin/codegraph.js
     - serve
     - --mcp
   cwd: "."
   ```
3. Test it: `python -m anet.core.mcp_doctor codegraph` (expects PASS + a tool list).

## Note on `cwd`

`cwd: "."` is required — codegraph stores its graph inside the indexed project root
(`.code-review-graph/`, located by walking parent dirs like `.git`). It must run in
the project, not the default per-server data dir. The graph folder is git-ignored.
