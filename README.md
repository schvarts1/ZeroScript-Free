# ZeroScript DeepSeek

A stripped-down fork of ZeroScript containing only the DeepSeek browser extension and a generic local MCP server bridge.

## Architecture

DeepSeek → browser extension → `ws://127.0.0.1:8765` → configured MCP servers over stdio.

There is no Roblox Studio integration, Roblox-specific provider, Creator Store code, or multi-provider support.

## Setup

1. Install Python 3.9+.
2. Install dependencies: `python -m pip install -r requirements.txt`.
3. Configure MCP servers in `config.json`.
4. Start `bridge.py` (or `start.bat` on Windows).
5. Load `zeroscript-extension` as an unpacked Chrome/Edge extension.
6. Open DeepSeek and use the ZeroScript control in the page.

MCP tools are exposed to DeepSeek as `server/tool` names. The bridge does not execute arbitrary browser JavaScript or expose a public network listener; it binds to loopback only.
