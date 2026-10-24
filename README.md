# LLMCompiler Prompt Loop

Sistema que lê uma lista de prompts e executa cada um via LLMCompiler (DAG paralelo), com guardrails de entrada/saída, skills, system prompt e configuração de MCPs (exa, context7, desktop-commander).

## Estrutura

- `main.py` — loop determinístico sobre a lista de prompts; cada prompt vira um plano LLMCompiler.
- `system_prompt.md` — system prompt do agente.
- `guardrails.py` — filtros de entrada/saída (PII, injeção, tamanho, tópicos).
- `skills/` — skills reutilizáveis.
- `mcp_config.json` — declaração dos MCPs.
- `requirements.txt`.

## Uso

```bash
pip install -r requirements.txt
python main.py
```

Edite `PROMPTS` em `main.py` ou passe um arquivo JSON via `PROMPTS_FILE`.
