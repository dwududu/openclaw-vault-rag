# Vault RAG — Persistent Semantic Memory for OpenClaw Agents

A drop-in RAG system that indexes your OpenClaw workspace/vault into ChromaDB, powered by local Ollama embeddings. Gives every agent persistent semantic memory without cloud APIs.

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/dwududu/openclaw-vault-rag/main/install.sh | bash
```

Or manually:

```bash
git clone https://github.com/dwududu/openclaw-vault-rag.git ~/.openclaw/skills/vault-rag
cd ~/.openclaw/skills/vault-rag
./install.sh
```

## How It Works

1. **Indexes** your entire workspace (`vault/`, project files, notes) into ChromaDB
2. **Embeds** using Ollama + `qwen3-embedding:0.6b` (fully local, 1024-dim vectors)
3. **Auto-recalls** top relevant chunks before each agent turn
4. **Auto-reindexes** nightly to catch new/changed files

## Architecture

```
~/.openclaw/workspace/rag/
├── index_vault.py        # Index, update, query pipeline
├── rag.sh                # Wrapper for agent shell access
├── requirements.txt      # Python dependencies
├── chroma_db/            # Chroma persistent vector store
├── index_state.json      # File hash state for incremental updates
├── install.sh            # One-command installer
└── SKILL.md              # Agent skill definition
```

## Prerequisites

- OpenClaw (obviously)
- Ollama (`curl -fsSL https://ollama.com/install.sh | sh`)
- Python 3.10+ (deps in `requirements.txt`)

The installer handles package deps automatically via `requirements.txt`.

## Usage

### For agents (built-in tool)

After install, agents have access to `rag_search` — they call it automatically before responding to inject relevant vault context.

Manual query:

```bash
python3 ~/.openclaw/workspace/rag/index_vault.py --query "what is the everly project"
python3 ~/.openclaw/workspace/rag/index_vault.py --query "everly project" --json
```

### For cron (auto-reindex)

Set up nightly incremental updates:

```bash
crontab -l > /tmp/crontab
echo "0 3 * * * cd ~/.openclaw/workspace/rag && python3 index_vault.py --update" >> /tmp/crontab
crontab /tmp/crontab
```

## Configuration

Edit `~/.openclaw/workspace/rag/index_vault.py` top section:

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBED_MODEL` | `qwen3-embedding:0.6b` | Ollama embedding model |
| `CHUNK_SIZE` | `500` | Characters per chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API endpoint |
| `SKIP_DIRS` | (see file) | Directories to ignore |
| `SKIP_EXTENSIONS` | (see file) | File extensions to skip |

## Performance

- ~300 chunks/minute on Tegra/ARM (GPU-accelerated qwen3-embedding)
- ~800 chunks/minute on x86 with good CPU
- Queries return in 0.5–2s

## Why ChromaDB?

- **Persistent by default** — survive reboots, no cloud
- **Local embeddings** — Ollama runs qwen3-embedding on your own hardware
- **Incremental updates** — only reindex changed files
- **Self-contained** — single SQLite file, zero infra

## License

MIT
