# playwright MCP

Source: package
Repo: https://github.com/microsoft/playwright-mcp
Install: none — `npx @playwright/mcp` fetches it on first run
Entry: npx @playwright/mcp
Env: none

Microsoft's Playwright MCP server: full browser automation — navigate, click, type,
fill forms, snapshot the page, and take screenshots.

## Setup (recipient)

Nothing to clone or build. You only need **Node.js** on PATH; `npx` downloads the
`@playwright/mcp` package automatically the first time the server starts. The first
run may also download browser binaries (Playwright handles this).

Test it: `python -m anet.core.mcp_doctor playwright` (expects PASS + a tool list).
