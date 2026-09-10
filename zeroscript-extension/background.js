// SPDX-License-Identifier: GPL-3.0-or-later
// Minimal extension-side WebSocket client for the local generic MCP bridge.
(() => {
  "use strict";
  const WS_URL = "ws://127.0.0.1:8765";
  const PROVIDER_URLS = ["https://chat.deepseek.com/*"];
  let ws = null, connecting = null, nextId = 1;
  const pending = new Map();
  function rejectAll(error) { for (const [, p] of pending) p.reject(error); pending.clear(); }
  function connect() {
    if (ws && ws.readyState === WebSocket.OPEN) return Promise.resolve(ws);
    if (connecting) return connecting;
    connecting = new Promise((resolve, reject) => {
      const s = new WebSocket(WS_URL);
      const timer = setTimeout(() => { try { s.close(); } catch {} reject(new Error("bridge connection timeout")); }, 2500);
      s.onopen = () => { clearTimeout(timer); ws = s; resolve(s); };
      s.onmessage = e => { let msg; try { msg=JSON.parse(e.data); } catch { return; } if (msg.id != null && pending.has(msg.id)) { const p=pending.get(msg.id); pending.delete(msg.id); msg.error?p.reject(new Error(msg.error)):p.resolve(msg); } chrome.tabs.query({url:PROVIDER_URLS}, tabs => tabs.forEach(t => chrome.tabs.sendMessage(t.id,{type:"bridge_status",status:{connected:true}}).catch(()=>{}))); };
      s.onerror = () => {};
      s.onclose = () => { if (ws === s) ws=null; rejectAll(new Error("bridge connection closed")); };
    }).finally(() => { connecting=null; });
    return connecting;
  }
  async function request(type, payload={}) { const s=await connect(); const id=nextId++; return new Promise((resolve,reject)=>{ pending.set(id,{resolve,reject}); s.send(JSON.stringify({type,id,...payload})); }); }
  chrome.runtime.onMessage.addListener((msg,_sender,sendResponse)=>{
    if (!msg?.type) return;
    if (msg.type === "list_tools") { request("list_tools").then(r=>sendResponse({ok:true,...r})).catch(e=>sendResponse({ok:false,error:e.message})); return true; }
    if (msg.type === "call_tool") { request("call_tool",{name:msg.name,arguments:msg.arguments||{}}).then(r=>sendResponse({ok:true,...r})).catch(e=>sendResponse({ok:false,error:e.message})); return true; }
    if (msg.type === "bridge_status") { connect().then(()=>sendResponse({connected:true})).catch(e=>sendResponse({connected:false,error:e.message})); return true; }
  });
})();
