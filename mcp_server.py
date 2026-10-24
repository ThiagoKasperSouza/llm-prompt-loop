import json, subprocess, os, sys


def handle(req):
    method = req.get("method")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req.get("id"), "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "python-mcp", "version": "1.0"},
        }}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req.get("id"), "result": {"tools": [
            {"name": "run_command", "description": "Run a shell command",
             "inputSchema": {"type": "object", "properties": {"command": {"type": "string"}, "timeout_ms": {"type": "number"}}, "required": ["command"]}},
            {"name": "write_file", "description": "Write text to a file",
             "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
            {"name": "list_dir", "description": "List directory contents",
             "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
            {"name": "read_file", "description": "Read a file",
             "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
        ]}}
    if method == "tools/call":
        name = req["params"]["name"]
        args = req["params"].get("arguments", {})
        try:
            if name == "run_command":
                cmd = args["command"]
                timeout = args.get("timeout_ms", 30000) / 1000.0
                out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
                text = (out.stdout or "") + (out.stderr or "")
                return {"jsonrpc": "2.0", "id": req.get("id"), "result": {"content": [{"type": "text", "text": text or "(no output)"}]}}
            if name == "write_file":
                path = args["path"]
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(args["content"])
                return {"jsonrpc": "2.0", "id": req.get("id"), "result": {"content": [{"type": "text", "text": f"written: {path}"}]}}
            if name == "list_dir":
                path = args["path"]
                entries = os.listdir(path)
                return {"jsonrpc": "2.0", "id": req.get("id"), "result": {"content": [{"type": "text", "text": "\n".join(entries)}]}}
            if name == "read_file":
                with open(args["path"], "r", encoding="utf-8") as f:
                    return {"jsonrpc": "2.0", "id": req.get("id"), "result": {"content": [{"type": "text", "text": f.read()}]}}
            return {"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32601, "message": f"unknown tool {name}"}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32000, "message": str(e)}}
    return {"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32601, "message": "method not found"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
