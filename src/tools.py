import os, json, subprocess, urllib.request


async def mcp_stdio_call(cmd, tool_name, arguments, timeout=60):
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    try:
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "hermes", "version": "1.0"}}}) + "\n")
        proc.stdin.flush()
        proc.stdout.readline()
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}}) + "\n")
        proc.stdin.flush()
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line)
                if msg.get("id") == 2:
                    content = msg.get("result", {}).get("content", [])
                    texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                    return "\n".join(texts) if texts else json.dumps(msg)[:4000]
            except Exception:
                continue
        return (proc.stderr.read() or "no response")[:4000]
    except Exception as e:
        return f"mcp error: {e}"
    finally:
        proc.kill()


async def tool_tavily_search(query):
    from tavily import TavilyClient
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return "tavily: TAVILY_API_KEY not set"
    try:
        client = TavilyClient(api_key=api_key)
        res = client.search(query, max_results=5)
        results = res.get("results", [])
        texts = []
        for r in results:
            texts.append(f"Title: {r.get('title')}\nURL: {r.get('url')}\n{r.get('content','')[:500]}")
        return "\n\n".join(texts) if texts else "no results"
    except Exception as e:
        return f"tavily error: {e}"


async def tool_exa_agent(query):
    # Auto-discover tool name containing agent/research
    import subprocess as sp, time
    # Exa is HTTP, use tools/list via JSON-RPC over HTTP
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode()
    api_key = os.environ.get("EXA_API_KEY", "")
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "User-Agent": "hermes/1.0"}
    if api_key:
        headers["x-api-key"] = api_key
    req = urllib.request.Request("https://mcp.exa.ai/mcp", data=payload, headers=headers)
    tool_name = None
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            msg = json.loads(r.read().decode())
        for t in msg.get("result", {}).get("tools", []):
            n = t.get("name", "")
            if "agent" in n or "research" in n or "deep" in n:
                tool_name = n
                break
        if not tool_name:
            names = [t.get("name") for t in msg.get("result", {}).get("tools", [])]
            tool_name = names[0] if names else "web_search_exa"
    except Exception as e:
        return f"exa list error: {e}"
    # call it
    payload = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": tool_name, "arguments": {"query": query}}}).encode()
    req = urllib.request.Request("https://mcp.exa.ai/mcp", data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
        texts = []
        current_data = ""
        for line in raw.splitlines():
            line = line.rstrip("\n")
            if line.startswith("data:"):
                current_data += line[5:].strip() + "\n"
            elif line.strip() == "":
                if current_data.strip():
                    try:
                        obj = json.loads(current_data.strip())
                        content = obj.get("result", {}).get("content", [])
                        for c in content:
                            if c.get("type") == "text":
                                texts.append(c.get("text", ""))
                    except Exception:
                        pass
                    current_data = ""
        if current_data.strip():
            try:
                obj = json.loads(current_data.strip())
                content = obj.get("result", {}).get("content", [])
                for c in content:
                    if c.get("type") == "text":
                        texts.append(c.get("text", ""))
            except Exception:
                pass
        if texts:
            return "\n".join(texts)[:4000]
        try:
            data = json.loads(raw)
            content = data.get("result", {}).get("content", [])
            texts = [c.get("text", "") for c in content if c.get("type") == "text"]
            if texts:
                return "\n".join(texts)[:4000]
        except Exception:
            pass
        return raw[:4000]
    except Exception as e:
        return f"exa agent error: {e}"


async def tool_context7(query, library=None):
    if not library:
        return "context7: libraryId required (format /owner/repo)"
    return await mcp_stdio_call(["npx", "-y", "@upstash/context7-mcp@latest"],
                               "query-docs", {"libraryId": library, "query": query})


MCP_PY = ["python3", "/home/thiago/Documents/llmcompiler-prompt-loop/mcp_server.py"]


async def tool_run_command(cmd):
    return await mcp_stdio_call(MCP_PY, "run_command", {"command": cmd, "timeout_ms": 30000})


async def tool_write_file(path, content):
    return await mcp_stdio_call(MCP_PY, "write_file", {"path": path, "content": content})


async def tool_list_dir(path="."):
    return await mcp_stdio_call(MCP_PY, "list_dir", {"path": path})


async def tool_read_file(path):
    return await mcp_stdio_call(MCP_PY, "read_file", {"path": path})


async def tool_desktop_commander(cmd=None, command=None, **kwargs):
    # Backward compat: delegate to run_command
    return await tool_run_command(cmd or command or "")


def get_tools():
    return {
        "tavily_search": tool_tavily_search,
        "context7": tool_context7,
        "run_command": tool_run_command,
        "write_file": tool_write_file,
        "list_dir": tool_list_dir,
        "read_file": tool_read_file,
    }
