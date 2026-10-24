#!/usr/bin/env bash
set -e
docker compose up -d
sleep 5
docker exec local-llm ollama pull qwen2.5:0.5b
echo "Modelo qwen2.5:0.5b pronto em http://localhost:11434"
