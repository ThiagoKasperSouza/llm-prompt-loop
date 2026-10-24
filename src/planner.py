import json, os, urllib.request


def allowed_tools(prompt, all_tools):
    low = prompt.lower()
    allowed = set()
    if any(k in low for k in ["lista", "list", "pastas", "diretor", "arquivo", "file", "filesystem", "salv", "save", "escrev", "write", "read", "cat", "ls"]):
        allowed.update(["run_command", "write_file", "list_dir", "read_file"])
    if any(k in low for k in ["busca", "search", "web", "tavily", "pesquis"]):
        allowed.update(["tavily_search"])
    if any(k in low for k in ["doc", "document", "context7", "biblioteca", "library"]):
        allowed.update(["context7"])
    if not allowed:
        allowed = set(all_tools.keys())
    return {k: v for k, v in all_tools.items() if k in allowed}


def plan(prompt, tools, ollama_url="http://localhost:11434", model="qwen2.5:0.5b"):
    tools = allowed_tools(prompt, tools)
    # Heurística: forçar tool mencionada explicitamente
    forced = None
    low = prompt.lower()
    if "desktop_commander" in low or "desktop-commander" in low or "desktop commander" in low:
        forced = "run_command"
    elif "context7" in low:
        forced = "context7"
    elif "exa" in low:
        forced = "exa_search"
    if forced and forced in tools:
        return [{"id": 1, "tool": forced, "args": {"cmd": prompt, "query": prompt, "command": prompt}, "deps": []}]
    tool_list = ", ".join(tools.keys())
    system = ("Você é um planejador LLMCompiler. Retorne APENAS JSON array de tarefas: "
              "[{\"id\": int, \"tool\": uma de [" + tool_list + "], "
              "\"args\": {...}, \"deps\": [ids]}]. "
              "Use run_command para shell, write_file para salvar, list_dir para listar, read_file para ler. "
              "Use exa_search para busca web. Use context7 para docs (libraryId /owner/repo). "
              "Use deps para paralelismo. Sem texto extra.")
    body = json.dumps({"model": model, "prompt": f"{system}\n\nPrompt: {prompt}\nJSON:",
                       "stream": True}).encode()
    req = urllib.request.Request(f"{ollama_url}/api/generate", data=body,
                                headers={"Content-Type": "application/json"})
    collected = ""
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            for line in r:
                if not line:
                    continue
                try:
                    obj = json.loads(line.decode())
                    chunk = obj.get("response", "")
                    collected += chunk
                    print(chunk, end="", flush=True)
                    if obj.get("done"):
                        break
                except Exception:
                    continue
        print()
        tasks = json.loads(collected)
        if isinstance(tasks, dict):
            tasks = tasks.get("tasks", [])
        for t in tasks:
            t.setdefault("id", 1)
            t.setdefault("deps", [])
        return tasks if tasks else [{"id": 1, "tool": list(tools)[0], "args": {"query": prompt}, "deps": []}]
    except Exception:
        return [{"id": 1, "tool": list(tools)[0], "args": {"query": prompt}, "deps": []}]
