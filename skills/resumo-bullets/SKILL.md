---
name: resumo-bullets
description: Use when the user asks to summarize in bullets or create a bullet-point summary.
---

# Resumo em Bullets

## Quando usar
Quando o prompt contém "resuma em bullets" ou "resumo em N bullets".

## DAG
1. tavily_search (query = tópico extraído do prompt)
2. summarize (text = resultado de 1, bullets = N)

## Guardrails
- Bloquear queries com padrões suspeitos.
