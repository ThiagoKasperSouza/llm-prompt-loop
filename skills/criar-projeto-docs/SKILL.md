---
name: criar-projeto-docs
description: Use when the user asks to create a project from docs or read all contents of a directory.
---

# Criar Projeto a partir de Docs

## Quando usar
Quando o prompt contém "use todos os conteúdos de ./docs/" ou "crie um projeto a partir de docs".

## DAG
1. read_dir (path = ./docs)
2. write_file (path = projeto, content = resultado de 1)

## Guardrails
- Bloquear comandos shell perigosos.
