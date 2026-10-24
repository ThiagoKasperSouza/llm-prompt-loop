import re
from typing import Tuple

# Padrões de entrada bloqueados
INPUT_BLOCK_PATTERNS = [
    r"(?i)ignore (all )?previous instructions",
    r"(?i)system prompt",
    r"(?i)jailbreak",
    r"(?i)rm\s+-rf",
    r"(?i)drop\s+table",
]

# Padrões de saída a redigir
PII_PATTERNS = [
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "[CPF_REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z]{2,}\b", re.I), "[EMAIL_REDACTED]"),
]

MAX_PROMPT_CHARS = 4000
MAX_OUTPUT_CHARS = 20000


def check_input(prompt: str) -> Tuple[bool, str]:
    if not prompt or not prompt.strip():
        return False, "prompt vazio"
    if len(prompt) > MAX_PROMPT_CHARS:
        return False, f"prompt excede {MAX_PROMPT_CHARS} chars"
    for pat in INPUT_BLOCK_PATTERNS:
        if re.search(pat, prompt):
            return False, f"prompt bloqueado por padrão: {pat}"
    return True, "ok"


def sanitize_output(text: str) -> str:
    for pat, repl in PII_PATTERNS:
        text = pat.sub(repl, text)
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[:MAX_OUTPUT_CHARS] + "\n...[TRUNCATED]"
    return text
