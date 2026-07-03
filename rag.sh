#!/bin/bash
# Wrapper for agents to call vault RAG
# Returns JSON: [{source, chunk_index, text, score}, ...]

QUERY="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -z "$QUERY" ]; then
    echo '[]'
    exit 0
fi

# Ensure Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    ollama serve &>/dev/null &
    for i in $(seq 1 10); do
        sleep 1
        curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && break
    done
fi

python3 "$SCRIPT_DIR/index_vault.py" --query "$QUERY" --json 2>/dev/null
