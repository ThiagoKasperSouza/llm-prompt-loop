import json, subprocess, os, sys, asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MCP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")

def call_mcp(method, params):
    proc = subprocess.Popen(
        [sys.executable, MCP_PATH],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "proxy", "version": "1.0"}}}
    proc.stdin.write(json.dumps(init) + "\n")
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": method, "params": params}) + "\n")
    proc.stdin.flush()
    # read responses
    resp = None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if obj.get("id") == 2:
            resp = obj
            break
    proc.stdin.close()
    proc.wait()
    return resp

@app.post("/run_pipeline")
async def run_pipeline(body: dict):
    prompt = body.get("prompt", "")
    allowed = body.get("allowed_tools")
    params = {"name": "run_pipeline", "arguments": {"prompt": prompt, "allowed_tools": allowed}}
    resp = await asyncio.to_thread(call_mcp, "tools/call", params)
    return resp

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
