import asyncio
import json
import os
import subprocess
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
import urllib.request
from typing import List, Dict, Any

from guardrails import check_input, sanitize_output

PROMPTS: List[str] = [
  ["Resuma em 3 bullets o que é o LLMCompiler.Salve em markdown em ./bullets.md", ["tavily_search", "summarize", "write_file", "run_command"]],
  ["Pesquise sobre iot em 10 fontes. Salve titulo,link e resumo em ./iot.csv", ["tavily_search", "extract_csv","write_csv", "run_command"]],
  ["Liste as pastas em /home/thiago/Documents", ["list_dir", "run_command"]],
  ["Salve o resultado de ls -la /home/thiago/Documents em ./output.txt", ["write_file", "run_command"]]
]
PROMPTS_FILE = os.environ.get("PROMPTS_FILE")


def load_prompts() -> List[Any]:
    if PROMPTS_FILE and os.path.exists(PROMPTS_FILE):
        with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "prompts" in data:
            return data["prompts"]
    return PROMPTS


async def mcp_stdio_call(cmd: list, tool_name: str, arguments: dict, timeout: int = 60) -> str:
    import subprocess as sp
    proc = sp.Popen(cmd, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, text=True)
    try:
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "hermes", "version": "1.0"}}}
        proc.stdin.write(json.dumps(init) + "\n")
        proc.stdin.flush()
        # read init response
        line = proc.stdout.readline()
        # send initialized notification
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()
        # call tool
        call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments}}
        proc.stdin.write(json.dumps(call) + "\n")
        proc.stdin.flush()
        # read until response id 2
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
async def tool_tavily_search(query: str) -> str:
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


async def tool_context7(query: str, library=None) -> str:
    if not library:
        return "context7: libraryId required (format /owner/repo)"
    return await mcp_stdio_call(["npx", "-y", "@upstash/context7-mcp@latest"],
                               "query-docs", {"libraryId": library, "query": query})


async def tool_desktop_commander(cmd=None, command=None, **kwargs):
    cmd = cmd or command
    # Try start_process directly first
    res = await mcp_stdio_call(["npx", "-y", "@wonderwhy-er/desktop-commander"],
                               "start_process", {"command": cmd, "timeout_ms": 30000})
    if "Unknown tool" not in res and "not supported" not in res and "no tool found" not in res:
        return res
    # Fallback to execute_command
    res = await mcp_stdio_call(["npx", "-y", "@wonderwhy-er/desktop-commander"],
                               "execute_command", {"command": cmd})
    if "Unknown tool" not in res and "not supported" not in res and "no tool found" not in res:
        return res
    # Auto-discovery fallback
    import subprocess as sp, time
    proc = sp.Popen(["npx", "-y", "@wonderwhy-er/desktop-commander"],
                    stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, text=True)
    tool_name = None
    all_tools = []
    try:
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "hermes", "version": "1.0"}}}) + "\n")
        proc.stdin.flush()
        proc.stdout.readline()
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n")
        proc.stdin.flush()
        deadline = time.time() + 30
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line)
                if msg.get("id") == 2:
                    all_tools = [t.get("name") for t in msg.get("result", {}).get("tools", [])]
                    break
            except Exception:
                continue
        for preferred in ["start_process", "execute_command", "run_command", "shell"]:
            if preferred in all_tools:
                tool_name = preferred
                break
        if not tool_name:
            for n in all_tools:
                if n and "feedback" not in n and "get_config" not in n and ("execute" in n or "run" in n or "shell" in n or "command" in n):
                    tool_name = n
                    break
        if not tool_name and all_tools:
            tool_name = all_tools[0]
    finally:
        proc.kill()
    if not tool_name:
        return "desktop-commander: no tool found"
    return await mcp_stdio_call(["npx", "-y", "@wonderwhy-er/desktop-commander"],
                               tool_name, {"command": cmd})


MCP_PY = ["python3", "/home/thiago/Documents/llmcompiler-prompt-loop/mcp_server.py"]


async def tool_run_command(cmd=None, command=None, timeout_ms=30000, **kwargs):
    cmd = cmd or command
    from src.tools import mcp_stdio_call
    return await mcp_stdio_call(MCP_PY, "run_command", {"command": cmd, "timeout_ms": timeout_ms})


async def tool_write_file(path, content):
    from src.tools import mcp_stdio_call
    return await mcp_stdio_call(MCP_PY, "write_file", {"path": path, "content": content})


async def tool_list_dir(path="."):
    from src.tools import mcp_stdio_call
    return await mcp_stdio_call(MCP_PY, "list_dir", {"path": path})


async def tool_read_file(path):
    from src.tools import mcp_stdio_call
    return await mcp_stdio_call(MCP_PY, "read_file", {"path": path})

async def tool_extract_csv(text: str, columns: list) -> list:
    import urllib.request, json, re
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")
    prompt = (
        f"Você é um extrator de dados. A partir do texto abaixo, extraia uma lista de itens.\n"
        f"Colunas (exatamente): {', '.join(columns)}\n"
        f"Preencha TODAS as colunas, inclusive resumo (resumo de 1 frase do conteúdo).\n"
        f"Retorne APENAS um JSON array válido, sem texto adicional, no formato:\n"
        f'[{{"{columns[0]}": "valor", ...}}]\n\n'
        f"Texto:\n{text[:4000]}"
    )
    data = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(f"{ollama_url}/api/generate", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())["response"]
    m = re.search(r"\[.*\]", resp, re.S)
    if m:
        return json.loads(m.group(0))
    return []

async def tool_write_csv(path: str, rows: list) -> str:
    import csv, io
    if not rows:
        return "empty"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    from src.tools import mcp_stdio_call
    return await mcp_stdio_call(MCP_PY, "write_file", {"path": path, "content": buf.getvalue()})

async def tool_summarize(text: str, bullets: int = 3) -> str:
    import urllib.request, json
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")
    prompt = f"Resuma em {bullets} bullet points o seguinte texto:\n\n{text[:4000]}"
    data = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(f"{ollama_url}/api/generate", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["response"]


TOOLS = {
    "tavily_search": tool_tavily_search,
    "exa_search": tool_tavily_search,  # alias
    "context7": tool_context7,
    "run_command": tool_run_command,
    "write_file": tool_write_file,
    "list_dir": tool_list_dir,
    "read_file": tool_read_file,
    "summarize": tool_summarize,
    "extract_csv": tool_extract_csv,
    "write_csv": tool_write_csv,
}


# ---------- Planner (LLM emits DAG) ----------
def plan(prompt: str, tools=None, allowed_override=None) -> List[Dict[str, Any]]:
    if tools is None:
        tools = TOOLS
    # Least privilege
    if allowed_override:
        tools = {k: v for k, v in tools.items() if k in set(allowed_override)}
    low = prompt.lower()
    # Least privilege
    # Detectar "salve ... em csv" com Colunas:
    if "csv" in low:
        import re
        pm = re.search(r"(\./[\w./-]+)", prompt)
        outpath = pm.group(1) if pm else "output.csv"
        # Extrair colunas após "Salve" e antes de "em"
        cols_match = re.search(r"Salve\s+(.+?)\s+em", prompt, re.I)
        if cols_match:
            cols = [c.strip() for c in cols_match.group(1).replace(" e ", ",").split(",")]
        else:
            cols_match2 = re.search(r"Colunas:\s*(.+)", prompt, re.I)
            cols = [c.strip() for c in cols_match2.group(1).split(",")] if cols_match2 else None
        q = prompt.split("Salve")[0].split("salve")[0].strip() or prompt
        if cols:
            return [
                {"id": 1, "tool": "tavily_search", "args": {"query": q}, "deps": []},
                {"id": 2, "tool": "extract_csv", "args": {"text": None, "columns": cols}, "deps": [1]},
                {"id": 3, "tool": "write_csv", "args": {"path": outpath, "rows": None}, "deps": [2]},
            ]
        return [
            {"id": 1, "tool": "tavily_search", "args": {"query": q}, "deps": []},
            {"id": 2, "tool": "write_csv", "args": {"path": outpath, "rows": None}, "deps": [1]},
        ]

    # Detectar "resuma ... e salve em arquivo"
    import re
    pm = re.search(r"(\./[\w./-]+)", prompt)
    outpath = pm.group(1) if pm else "output.txt"
    if ("resum" in low or "bullet" in low) and ("salv" in low or "save" in low or "escrev" in low):
        # Extrair a parte de busca (antes de "salve")
        import re
        q = prompt.split("Salve")[0].split("salve")[0].strip()
        if not q:
            q = prompt
        return [
            {"id": 1, "tool": "tavily_search", "args": {"query": q}, "deps": []},
            {"id": 2, "tool": "summarize", "args": {"text": None, "bullets": 3}, "deps": [1]},
            {"id": 3, "tool": "write_file", "args": {"path": outpath, "content": None}, "deps": [2]},
        ]
    # Detectar "resuma em bullets"
    if "resum" in low or "bullet" in low:
        # Limpar a query de busca: remover instruções de resumo
        import re
        q = re.sub(r"resuma em \d+ bullets?\s*", "", prompt, flags=re.I).strip()
        if not q:
            q = prompt
        return [
            {"id": 1, "tool": "tavily_search", "args": {"query": q}, "deps": []},
            {"id": 2, "tool": "summarize", "args": {"text": None, "bullets": 3}, "deps": [1]},
        ]
    cmd_match = re.search(r"(ls\s+-la\s+[\w./-]+)", prompt)
    if ("salv" in low or "save" in low or "escrev" in low) and cmd_match:
        cmd = cmd_match.group(1)
        return [
            {"id": 1, "tool": "run_command", "args": {"cmd": cmd, "timeout_ms": 30000}, "deps": []},
            {"id": 2, "tool": "write_file", "args": {"path": outpath, "content": None}, "deps": [1]},
        ]
    forced = None
    if "desktop_commander" in low or "desktop-commander" in low or "desktop commander" in low:
        forced = "run_command"
    elif "context7" in low:
        forced = "context7"
    elif "exa" in low or "tavily" in low or "busca" in low or "search" in low:
        forced = "tavily_search"
    if forced and forced in TOOLS:
        return [{"id": 1, "tool": forced, "args": {"cmd": prompt, "query": prompt, "command": prompt}, "deps": []}]
    # Chama Ollama local...
    import urllib.request
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")
    tool_list = ", ".join(TOOLS.keys())
    system = ("""Voce é um planejador de tarefas. Dado um prompt, você deve gerar um plano de execução em formato JSON. 
        Antes de gerar o plano, você deve analisar o prompt e decidir quais ferramentas são necessárias para executar as tarefas.
        RACIOCINIO: 
            Pense passo a passo, mas registre apenas um esboço mínimo para cada etapa do raciocínio, com no máximo 5 palavras. Apresente a resposta ao final, após um separador ####.
            Diretrizes:

                Limite cada etapa a 5 palavras
                Foque nos cálculos/transformações essenciais
                Mantenha a progressão lógica
                NÃO INCLUA O RACIOCÍNIO NA RESPOSTA FINAL

        As ferramentas disponíveis são: """ + tool_list + """.
        Tavily- Use para pesquisa web, context7 - Use para pesquisa em repositórios de docs, run_command - Use para executar comandos no ambiente do usuário.
        write_file - Use para salvar arquivos, list_dir - Use para listar diretórios, read_file - Use para ler arquivos.
        Cada tarefa deve ser representada como um objeto JSON com os seguintes campos:
        - id: um número inteiro único que identifica a tarefa.
        - tool: o nome da ferramenta a ser usada para executar a tarefa. Deve ser uma das ferramentas disponíveis.
        - args: um objeto JSON que contém os argumentos necessários para executar a tarefa.
        - deps: uma lista de ids de tarefas que devem ser concluídas antes desta tarefa.
        Use deps para paralelismo. 
        
        RESPOSTA:
            O plano deve ser representado como um array JSON de tarefas. 
            Se o prompt não puder ser atendido com as ferramentas disponíveis, retorne uma tarefa única usando a ferramenta tavily_search com o prompt como argumento.
            Se o prompt pedir para salvar um arquivo, use desktop_commander (LISTE AS TOOLS e use a que for melhor) e inclua o caminho do arquivo no argumento da tarefa correspondente.
            Sem texto extra.""")
    body = json.dumps({"model": model, "prompt": f"{system}\n\nPrompt: {prompt}\nJSON:",
                       "stream": False, "format": "json"}).encode()
    req = urllib.request.Request(f"{ollama_url}/api/generate", data=body,
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode())
        text = data.get("response", "[]")
        tasks = json.loads(text)
        if isinstance(tasks, dict):
            tasks = tasks.get("tasks", [])
        if not isinstance(tasks, list) or not tasks:
            raise ValueError("plano inválido")
        for t in tasks:
            if t.get("tool") not in TOOLS:
                raise ValueError("tool desconhecida")
        return tasks
    except Exception:
        fallback = list(tools.keys())[0] if tools else "run_command"
        return [{"id": 1, "tool": fallback, "args": {"query": prompt}, "deps": []}]


# ---------- DAG executor (parallel levels) ----------
async def execute_dag(tasks: List[Dict[str, Any]], prompt: str = "") -> Dict[int, str]:
    results: Dict[int, str] = {}
    remaining = list(tasks)
    for i, t in enumerate(remaining):
        t.setdefault("id", i + 1)
        t.setdefault("deps", [])
        # Normalizar deps: se vier lista de dicts, extrair id
        norm = []
        for d in t["deps"]:
            if isinstance(d, dict):
                norm.append(d.get("id", d.get("task", None)))
            else:
                norm.append(d)
        t["deps"] = [x for x in norm if x is not None]
    while remaining:
        ready = [t for t in remaining if all(d in results for d in t.get("deps", []))]
        if not ready:
            break
        async def run(t):
            tool = TOOLS[t["tool"]]
            args = t.get("args", {}) or {}
            if args is None:
                args = {}
            # Normalização de args por tool
            if t["tool"] == "run_command":
                import re
                low = prompt.lower()
                m = re.search(r"(/[\w./-]+)", prompt)
                path = m.group(1) if m else "."
                if "list" in low or "pastas" in low or "diretor" in low:
                    cmd = f"ls -la {path}"
                    args = {"cmd": cmd, "timeout_ms": 30000}
                elif "salv" in low or "save" in low or "escrev" in low:
                    pm = re.search(r"(\./[\w./-]+)", prompt)
                    outpath = pm.group(1) if pm else "output.txt"
                    # Detectar comando a executar (ex.: ls -la /path)
                    cmd_match = re.search(r"(ls\s+-la\s+[\w./-]+)", prompt)
                    if cmd_match:
                        cmd = cmd_match.group(1)
                        args = {"cmd": cmd, "timeout_ms": 30000}
                    # Fallback: salvar o prompt
                    if not cmd_match:
                        m = re.search(r"(/[\w./-]+)", prompt)
                        path = m.group(1) if m else "."
                        cmd = f"ls -la {path}"
                        args = {"cmd": cmd, "timeout_ms": 30000}
                else:
                    cmd = args.get("cmd", args.get("command", prompt))
                    args = {"cmd": cmd, "timeout_ms": 30000}
                if t["tool"] == "run_command":
                    args = {"cmd": cmd, "timeout_ms": 30000}
            if t["tool"] == "context7" and "query" not in args:
                args = {"query": args.get("q", prompt), "library": args.get("library", None)}
            if t["tool"] == "tavily_search" and "query" not in args:
                args = {"query": args.get("q", prompt)}
            # Se summarize com text None, usar resultado da dependência
            if t["tool"] == "summarize" and args.get("text") is None:
                dep_id = (t.get("deps") or [None])[0]
                args["text"] = results.get(dep_id, "")
            # Se extract_csv com text None, usar resultado da dependência
            if t["tool"] == "extract_csv" and args.get("text") is None:
                dep_id = (t.get("deps") or [None])[0]
                args["text"] = results.get(dep_id, "")
            # Se write_csv com rows None, usar resultado da dependência
            if t["tool"] == "write_csv" and args.get("rows") is None:
                dep_id = (t.get("deps") or [None])[0]
                args["rows"] = results.get(dep_id, [])
            # Se write_file com content None, usar resultado da dependência
            if t["tool"] == "write_file" and args.get("content") is None:
                dep_id = (t.get("deps") or [None])[0]
                args["content"] = results.get(dep_id, "")
            if args is None:
                results[t["id"]] = t.get("_result", "done")
            else:
                out = await tool(**args)
                results[t["id"]] = sanitize_output(out) if isinstance(out, str) else out
        await asyncio.gather(*[run(t) for t in ready])
        for t in ready:
            remaining.remove(t)
    return results


async def run_one(prompt_item) -> Dict[str, Any]:
    # Suporta string ou [prompt, [allowed_tools]]
    if isinstance(prompt_item, (list, tuple)):
        prompt = str(prompt_item[0])
        allowed = prompt_item[1] if len(prompt_item) > 1 else None
    else:
        prompt = str(prompt_item)
        allowed = None
    ok, reason = check_input(prompt)
    if not ok:
        return {"status": "error", "prompt": prompt, "error": reason}
    tasks = plan(prompt, TOOLS, allowed_override=allowed)
    res = await execute_dag(tasks, prompt)
    return {"status": "ok", "prompt": prompt, "result": res}


async def main():
    prompts = load_prompts()
    results = []
    for i, p in enumerate(prompts, 1):
        print(f"[{i}/{len(prompts)}] {p}")
        r = await run_one(p)
        results.append(r)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    if os.environ.get("SAVE_RESULTS", "1") == "1":
        with open("results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nConcluído: {len(results)} prompts. Saída em results.json")


if __name__ == "__main__":
    asyncio.run(main())
