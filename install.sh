#!/bin/bash
# vault-rag installer for OpenClaw
# Run: curl -fsSL https://raw.githubusercontent.com/[USER]/openclaw-vault-rag/main/install.sh | bash
set -e

echo "🔨 Installing Vault RAG for OpenClaw..."

VAULT_DIR="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
RAG_DIR="$VAULT_DIR/rag"

# Clone or copy
if command -v git &>/dev/null && [ -d "$RAG_DIR" ]; then
    echo "   RAG directory already exists at $RAG_DIR"
    echo "   Run: cd $RAG_DIR && git pull"
elif command -v git &>/dev/null; then
    echo "   Cloning from GitHub..."
    git clone https://github.com/[USER]/openclaw-vault-rag.git "$RAG_DIR"
else
    echo "❌ Git not found. Clone manually:"
    echo "   git clone https://github.com/[USER]/openclaw-vault-rag.git $RAG_DIR"
    exit 1
fi

# Check Python deps
echo "   Checking Python dependencies..."
python3 -c "import chromadb" 2>/dev/null || {
    echo "   Installing chromadb..."
    pip install chromadb --quiet
}
python3 -c "import ollama" 2>/dev/null || {
    echo "   Installing ollama Python client..."
    pip install ollama --quiet
}

# Check Ollama
if command -v ollama &>/dev/null; then
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        if curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if 'qwen3-embedding:0.6b' in [m['name'] for m in d.get('models',[])] else 1)" 2>/dev/null; then
            echo "   ✅ qwen3-embedding:0.6b already pulled"
        else
            echo "   📥 Pulling qwen3-embedding:0.6b (639MB)..."
            ollama pull qwen3-embedding:0.6b
        fi
    else
        echo "   Starting Ollama..."
        ollama serve &>/dev/null &
        sleep 3
        echo "   📥 Pulling qwen3-embedding:0.6b (639MB)..."
        ollama pull qwen3-embedding:0.6b
    fi
else
    echo "⚠️  Ollama not found. Install: curl -fsSL https://ollama.com/install.sh | sh"
    echo "   Then pull: ollama pull qwen3-embedding:0.6b"
fi

# Set up auto-start on reboot
if ! crontab -l 2>/dev/null | grep -q "ollama serve"; then
    (crontab -l 2>/dev/null; echo "@reboot sleep 10 && /usr/local/bin/ollama serve &>/var/tmp/ollama.log &") | crontab -
    echo "   ✅ Added Ollama auto-start to crontab"
fi

# Set up nightly reindex
if ! crontab -l 2>/dev/null | grep -q "index_vault.py --update"; then
    (crontab -l 2>/dev/null; echo "0 3 * * * cd $RAG_DIR && python3 index_vault.py --update >> $RAG_DIR/reindex.log 2>&1") | crontab -
    echo "   ✅ Added nightly reindex cron (3 AM HKT)"
fi

echo ""
echo "✅ Vault RAG installed!"
echo ""
echo "Quick start:"
echo "  1. Build the index:  cd $RAG_DIR && python3 index_vault.py"
echo "  2. Query it:         python3 $RAG_DIR/index_vault.py --query 'your question' --json"
echo "  3. Update:           python3 $RAG_DIR/index_vault.py --update"
echo ""
echo "Your agents now have RAG memory."
