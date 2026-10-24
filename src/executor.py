import asyncio


async def execute_dag(tasks, tools, prompt=""):
    results = {}
    remaining = list(tasks)
    for i, t in enumerate(remaining):
        t.setdefault("id", i + 1)
        t.setdefault("deps", [])
        norm = []
        for d in t["deps"]:
            if isinstance(d, dict):
                norm.append(d.get("id"))
            else:
                norm.append(d)
        t["deps"] = [x for x in norm if x is not None]
    while remaining:
        ready = [t for t in remaining if all(d in results for d in t["deps"])]
        if not ready:
            break

        async def run(t):
            tool = tools[t["tool"]]
            args = t.get("args", {}) or {}
            if t["tool"] == "desktop_commander":
                import re
                m = re.search(r"(/[\w./-]+)", prompt)
                path = m.group(1) if m else "."
                low = prompt.lower()
                if "list" in low or "pastas" in low or "diretor" in low:
                    cmd = f"ls -la {path}"
                elif "salv" in low or "save" in low or "escrev" in low:
                    pm = re.search(r"(\./[\w./-]+)", prompt)
                    outpath = pm.group(1) if pm else "output.txt"
                    # Tentar write_file do desktop-commander
                    try:
                        from src.tools import mcp_stdio_call
                        res = await mcp_stdio_call(["npx", "-y", "@wonderwhy-er/desktop-commander"],
                                                   "write_file", {"path": outpath, "content": prompt})
                        # se sucesso, armazenar resultado e pular start_process
                        args = None  # sinal para não executar start_process
                        results_placeholder = res
                    except Exception:
                        cmd = f"echo '{prompt}' > {outpath}"
                        args = {"command": cmd, "timeout_ms": 30000}
            if t["tool"] == "context7" and "query" not in args:
                args = {"query": args.get("q", prompt), "library": args.get("library", None)}
            if t["tool"] == "exa_search" and "query" not in args:
                args = {"query": args.get("q", prompt)}
            if args is None:
                results[t["id"]] = results_placeholder
            else:
                out = await tool(**args)
                results[t["id"]] = out

        await asyncio.gather(*[run(t) for t in ready])
        for t in ready:
            remaining.remove(t)
    return results
