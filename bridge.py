#!/usr/bin/env python3
"""Small generic MCP-over-WebSocket bridge for ZeroScript DeepSeek.

Configured MCP servers speak stdio JSON-RPC. The browser extension speaks a tiny
WebSocket protocol on 127.0.0.1:8765. No Roblox/Studio-specific code lives here.
"""
import asyncio, json, os, sys
from pathlib import Path

try:
    import websockets
except ImportError:
    print("Missing dependency: pip install websockets", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config.json"
HOST, PORT = "127.0.0.1", 8765

def load_config():
    if not CONFIG.exists(): return {"mcpServers": {}}
    with CONFIG.open("r", encoding="utf-8") as f: return json.load(f)

class MCPServer:
    def __init__(self, sid, spec):
        self.sid, self.spec = sid, spec
        self.proc = None; self.lock = asyncio.Lock(); self.tools = []; self.next_id = 1
    async def start(self):
        cmd = self.spec.get("command"); args = self.spec.get("args", [])
        env = os.environ.copy(); env.update(self.spec.get("env", {}))
        if not cmd: raise RuntimeError(f"server {self.sid}: command missing")
        self.proc = await asyncio.create_subprocess_exec(cmd, *args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
        await self.request("initialize", {"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"ZeroScript-DeepSeek","version":"2.0.0"}})
        await self.notify("notifications/initialized", {})
        result = await self.request("tools/list", {})
        self.tools = result.get("tools", []) if isinstance(result, dict) else []
    async def stop(self):
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try: await asyncio.wait_for(self.proc.wait(), 2)
            except asyncio.TimeoutError: self.proc.kill()
        self.proc = None
    async def _read_message(self):
        line = await self.proc.stdout.readline()
        if not line: raise RuntimeError(f"server {self.sid} closed stdout")
        return json.loads(line.decode("utf-8"))
    async def request(self, method, params):
        async with self.lock:
            if not self.proc or self.proc.returncode is not None: await self.start()
            rid = self.next_id; self.next_id += 1
            self.proc.stdin.write((json.dumps({"jsonrpc":"2.0","id":rid,"method":method,"params":params})+"\n").encode())
            await self.proc.stdin.drain()
            while True:
                msg = await self._read_message()
                if msg.get("id") != rid: continue
                if "error" in msg: raise RuntimeError(json.dumps(msg["error"]))
                return msg.get("result", {})
    async def notify(self, method, params):
        if not self.proc or self.proc.returncode is not None: return
        self.proc.stdin.write((json.dumps({"jsonrpc":"2.0","method":method,"params":params})+"\n").encode())
        await self.proc.stdin.drain()
    async def call(self, name, arguments):
        return await self.request("tools/call", {"name":name,"arguments":arguments})

servers = {}
def all_tools():
    out=[]
    for sid, srv in servers.items():
        for tool in srv.tools:
            t=dict(tool); t["name"] = f"{sid}/{tool.get('name','')}"; t["server"] = sid; out.append(t)
    return out
async def call_tool(name, arguments):
    sid, sep, bare = name.partition("/"); srv = servers.get(sid) if sep else None
    if srv is None and not sep:
        matches=[s for s in servers.values() if any(t.get("name") == name for t in s.tools)]
        if len(matches) == 1: srv, bare = matches[0], name
    if srv is None: raise RuntimeError(f"unknown tool: {name}")
    result = await srv.call(bare, arguments or {})
    text=[c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"] if isinstance(result, dict) else []
    return {"text":"\n".join(text), "result":result}
async def handler(ws):
    async for raw in ws:
        msg = None
        try:
            msg=json.loads(raw); typ=msg.get("type"); rid=msg.get("id")
            if typ == "list_tools": await ws.send(json.dumps({"id":rid,"tools":all_tools()})); continue
            if typ == "call_tool":
                result=await call_tool(msg.get("name",""), msg.get("arguments",{})); await ws.send(json.dumps({"id":rid, **result})); continue
            await ws.send(json.dumps({"id":rid,"error":f"unknown message type: {typ}"}))
        except Exception as e:
            await ws.send(json.dumps({"id":msg.get("id") if msg else None,"error":str(e)}))
async def main():
    cfg=load_config()
    for sid,spec in (cfg.get("mcpServers") or {}).items():
        try:
            srv=MCPServer(sid,spec); await srv.start(); servers[sid]=srv; print(f"[bridge] {sid}: {len(srv.tools)} tools")
        except Exception as e: print(f"[bridge] {sid}: failed: {e}", file=sys.stderr)
    async with websockets.serve(handler, HOST, PORT):
        print(f"[bridge] listening on ws://{HOST}:{PORT}"); await asyncio.Future()
if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
