---
name: vault-rag
description: "Semantic search over your OpenClaw workspace/vault using ChromaDB + Ollama embeddings. Fully local, no cloud APIs."
license: MIT
homepage: https://github.com/dwududu/openclaw-vault-rag
---

# Vault RAG — OpenClaw Skill

Transforms your OpenClaw workspace/vault into a queryable semantic memory. Every agent gets persistent RAG across all your markdown, notes, and project files — fully local, zero cloud APIs.

## What it does

This skill installs a ChromaDB-powered RAG pipeline that:

1. **Indexes** your entire workspace (`vault/`, projects, memory, configs) into a local vector database
2. **Embeds** using Ollama's `qwen3-embedding:0.6b` (1024-dim, fully local on GPU/CPU)
3. Lets you **query** semantically: "find everything about the Everly project" returns relevant chunks
4. **Updates incrementally** — only reindexes changed files

## Tools provided

After install, agents in the session get:

- `clawbox__bash /home/clawbox/.openclaw/workspace/rag/rag-search.sh "query"` — returns JSON of top-5 results with source paths, relevance scores, and chunk text
- `clawbox__bash python3 /home/clawbox/.openclaw/workspace/rag/index_vault.py --update` — incrementally reindex changed files

## When to use

- David asks a question that references prior work, deep research, or vault projects
- An agent needs context from a project file, meeting note, or decision log
- Cross-referencing information across multiple vault directories
- Any query where the answer might live in an `.md` file somewhere in the workspace

**Best for:** factual recall, project context, decision history, research references.

**Not for:** conversation history (use `memory_search` for session transcripts).

## How it works

```
Query → qwen3-embedding (via Ollama) → ChromaDB vector search → Top-5 chunks with scores
```

The index lives at `~/.openclaw/workspace/rag/chroma_db/` — a standard Chroma persistent database. The embedding model is a 600MB GGUF file running locally via Ollama.

## Initial setup

If the index doesn't exist yet:

```bash
# Ensure ollama is running
ollama serve &
# Full re-index (takes ~30-60min for a large vault)
cd ~/.openclaw/workspace/rag && python3 index_vault.py
```

After initial index, use `--update` for daily maintenance:

```bash
python3 ~/.openclaw/workspace/rag/index_vault.py --update
```

## Configuration

The indexer automatically:
- Skips binary files, images, PDFs, git directories
- Only indexes `.md`, `.txt`, `.py`, `.js`, `.ts`, `.html`, `.css`, `.sh`, `.mjs`
- Skips files > 2MB
- Chunks at 500 characters with 50-char overlap

All config lives at the top of `index_vault.py` — edit `EMBED_MODEL`, `CHUNK_SIZE`, `SKIP_DIRS`, etc.

## Files

| File | Purpose |
|------|---------|
| `index_vault.py` | Main pipeline: index, update, query |
| `rag.sh` | Bash wrapper for agent consumption (returns JSON) |
| `chroma_db/` | Chroma persistent vector store (auto-created) |
| `index_state.json` | File MD5 hashes for incremental updates |
