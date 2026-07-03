#!/bin/bash
# RAG skill integration for OpenClaw agents
# This script is called by agents to search the local vault RAG.
#
# Usage: rag-search.sh "your query"
# Returns: JSON on stdout, errors on stderr

QUERY="$1"

if [ -z "$QUERY" ]; then
    echo '[]'
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Ensure Ollama is running (non-blocking, silent error if already up)
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    ollama serve &>/dev/null &
    for i in $(seq 1 10); do
        sleep 1
        curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && break
    done
fi

# Run the query, capture JSON, clean stderr
python3 "$SCRIPT_DIR/index_vault.py" --query "$QUERY" --json 2>/dev/null
