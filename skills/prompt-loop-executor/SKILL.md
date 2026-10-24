---
name: prompt-loop-executor
description: Use when running a deterministic loop over a list of prompts with LLMCompiler. Handles guardrails, skills, system prompt, and MCP config.
---

# Prompt Loop Executor (LLMCompiler)

## Quando usar
- Executar uma lista de prompts em loop até terminar.
- Cada prompt vira um plano DAG via LLMCompiler.

## Passos
1. Carregar prompts de `PROMPTS` ou `PROMPTS_FILE`.
2. Para cada prompt: `check_input` → planejar DAG → executar → `sanitize_output`.
3. Persistir resultados em `results.json`.

## Guardrails
- Bloquear prompts com injeção, PII, comandos destrutivos.
- Redigir PII na saída.
- Limitar tamanho (4000 in / 20000 out).

## MCPs
- tavily, context7, python-mcp(ver `mcp_config.json`).

## Skills
- `skills/` contém skills reutilizáveis.
