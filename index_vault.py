#!/usr/bin/env python3
"""
Vault RAG — ChromaDB + Ollama qwen3-embedding
======================================================
Indexes markdown/text files into a local Chroma vector database
with semantic search via Ollama embeddings (1024-dim).

Usage:
  python3 index_vault.py                         # Full re-index
  python3 index_vault.py --update                 # Index only new/changed files
  python3 index_vault.py --query "question"       # Human-readable results
  python3 index_vault.py --query "question" --json  # JSON output for agents
"""

import os
import sys
import json
import hashlib
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Sequence

import chromadb
from chromadb.api.types import Documents, Embeddings, EmbeddingFunction

# ── CONFIG ──────────────────────────────────────────────────────────────────────
WORKSPACE = Path.home() / ".openclaw" / "workspace"
CHROMA_PATH = WORKSPACE / "rag" / "chroma_db"
OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "qwen3-embedding:0.6b"

SKIP_DIRS = {".git", ".stfolder", "__pycache__", ".obsidian", "node_modules",
             "chroma_db", "logs", ".cache", "media", "attachments", ".Trash", "Trash"}
SKIP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ipynb",
                   ".pyc", ".json", ".lock", ".yaml", ".yml",
                   ".bin", ".pickle", ".gz", ".tar", ".zip", ".whl",
                   ".ttf", ".woff", ".woff2", ".eot", ".otf",
                   ".mp3", ".mp4", ".wav", ".ogg", ".webm"}

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
STATE_FILE = WORKSPACE / "rag" / "index_state.json"

# ── EMBEDDING FUNCTION ──────────────────────────────────────────────────────────

class QwenEmbeddingFunction(EmbeddingFunction[Documents]):
    """Chroma-compatible embedding function via Ollama API."""
    def __init__(self, model: str = EMBED_MODEL, url: str = f"{OLLAMA_URL}/api/embeddings"):
        self._model = model
        self._url = url

    def __call__(self, input: Sequence[Documents]) -> Embeddings:
        results = []
        for text in input:
            data = json.dumps({"model": self._model, "prompt": text}).encode()
            req = urllib.request.Request(
                self._url, data=data, method="POST",
                headers={"Content-Type": "application/json"}
            )
            resp = urllib.request.urlopen(req, timeout=30)
            results.append(json.loads(resp.read())["embedding"])
        return results

# ── HELPERS ─────────────────────────────────────────────────────────────────────

def ensure_ollama():
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        models = [m["name"] for m in data.get("models", [])]
        if EMBED_MODEL in models:
            return True
        print(f"❌ {EMBED_MODEL} not found. Available: {models}", file=sys.stderr)
        return False
    except urllib.error.URLError:
        print("❌ Ollama not running. Start: ollama serve", file=sys.stderr)
        return False

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

def chunk_text(text: str, source: str) -> list[dict]:
    chunks = []
    start = 0
    text_len = len(text)
    chunk_idx = 0
    while start < text_len:
        end = min(start + CHUNK_SIZE, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append({
                "text": chunk,
                "source": source,
                "chunk_index": chunk_idx,
                "char_start": start,
                "char_end": end
            })
        chunk_idx += 1
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks

def file_hash(filepath: Path) -> str:
    try:
        return hashlib.md5(filepath.read_bytes()).hexdigest()
    except Exception:
        return ""

# ── FILE SCANNER ────────────────────────────────────────────────────────────────

def is_indexable(filepath: Path) -> bool:
    if not filepath.is_file():
        return False
    parts = set(filepath.parts)
    if SKIP_DIRS & parts:
        return False
    if filepath.suffix.lower() in SKIP_EXTENSIONS:
        return False
    allowed = {".md", ".txt", ".py", ".js", ".ts", ".html", ".css", ".sh", ".mjs"}
    if filepath.suffix.lower() not in allowed:
        return False
    if filepath.stat().st_size > 2_000_000:
        return False
    try:
        text = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    if len(text.strip()) < 20:
        return False
    null_ratio = text.count('\x00') / max(len(text), 1)
    if null_ratio > 0.05:
        return False
    return True

# ── FULL RE-INDEX ───────────────────────────────────────────────────────────────

def index_workspace():
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    ef = QwenEmbeddingFunction()

    try:
        client.delete_collection("vault")
    except Exception:
        pass

    collection = client.create_collection(
        name="vault",
        embedding_function=ef,
        metadata={"description": "Workspace vault RAG index", "model": EMBED_MODEL}
    )

    total_files = total_chunks = 0
    batch_docs, batch_ids, batch_metadatas = [], [], []
    state = {}

    def flush():
        nonlocal total_chunks
        if not batch_docs:
            return
        collection.add(documents=batch_docs, ids=batch_ids, metadatas=batch_metadatas)
        total_chunks += len(batch_docs)
        print(f"  Indexed {total_chunks} chunks...\r", end="", flush=True)
        batch_docs.clear()
        batch_ids.clear()
        batch_metadatas.clear()

    for filepath in sorted(WORKSPACE.rglob("*")):
        if not is_indexable(filepath):
            continue

        text = filepath.read_text(encoding="utf-8", errors="ignore")
        total_files += 1
        rel_path = str(filepath.relative_to(WORKSPACE))
        state[rel_path] = file_hash(filepath)

        for chunk in chunk_text(text, rel_path):
            batch_ids.append(f"{rel_path}:{chunk['chunk_index']}")
            batch_docs.append(chunk["text"])
            batch_metadatas.append({
                "source": chunk["source"],
                "chunk_index": chunk["chunk_index"],
                "char_start": chunk["char_start"],
                "char_end": chunk["char_end"]
            })
            if len(batch_docs) >= 200:
                flush()

    flush()
    save_state(state)
    print(f"\n✅ Indexed {total_files} files → {total_chunks} chunks")
    return total_files, total_chunks

# ── INCREMENTAL UPDATE ──────────────────────────────────────────────────────────

def update_index():
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    ef = QwenEmbeddingFunction()

    try:
        collection = client.get_collection("vault", embedding_function=ef)
    except Exception:
        print("No existing collection. Running full re-index.", file=sys.stderr)
        return index_workspace()

    old_state = load_state()
    new_state = {}
    added = updated = kept = 0
    current_files = set()

    for filepath in sorted(WORKSPACE.rglob("*")):
        if not is_indexable(filepath):
            continue

        text = filepath.read_text(encoding="utf-8", errors="ignore")
        rel_path = str(filepath.relative_to(WORKSPACE))
        current_files.add(rel_path)
        h = file_hash(filepath)
        new_state[rel_path] = h

        if rel_path in old_state and old_state[rel_path] == h:
            kept += 1
            continue

        if rel_path in old_state:
            chunk_ids = [f"{rel_path}:{i}" for i in range(10000)]
            try:
                existing = collection.get(ids=chunk_ids, include=[])
                if existing["ids"]:
                    collection.delete(ids=existing["ids"])
            except Exception:
                pass
            updated += 1
        else:
            added += 1

        batch_docs, batch_ids, batch_metas = [], [], []
        for chunk in chunk_text(text, rel_path):
            batch_ids.append(f"{rel_path}:{chunk['chunk_index']}")
            batch_docs.append(chunk["text"])
            batch_metas.append({
                "source": chunk["source"],
                "chunk_index": chunk["chunk_index"],
                "char_start": chunk["char_start"],
                "char_end": chunk["char_end"]
            })
        if batch_docs:
            collection.add(documents=batch_docs, ids=batch_ids, metadatas=batch_metas)

    # Deleted files
    deleted = set(old_state.keys()) - current_files
    for rel_path in deleted:
        chunk_ids = [f"{rel_path}:{i}" for i in range(10000)]
        try:
            existing = collection.get(ids=chunk_ids, include=[])
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception:
            pass

    save_state(new_state)
    print(f"✅ Update: +{added} new, ~{updated} changed, -{len(deleted)} deleted ({kept} unchanged)")
    print(f"   Collection: {collection.count()} chunks")
    return added + updated, collection.count()

# ── QUERY ───────────────────────────────────────────────────────────────────────

def query_vault(question: str, n_results: int = 5) -> list[dict]:
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    ef = QwenEmbeddingFunction()

    try:
        collection = client.get_collection("vault", embedding_function=ef)
    except Exception:
        print("❌ No index found. Run with no arguments to index first.", file=sys.stderr)
        return []

    results = collection.query(query_texts=[question], n_results=n_results)
    output = []
    if results and results.get("documents") and results["documents"][0]:
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            output.append({
                "source": meta["source"],
                "chunk_index": meta["chunk_index"],
                "text": doc,
                "score": round(1.0 - dist, 4) if dist else 0
            })
    return output

# ── MAIN ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--query":
        if len(sys.argv) < 3:
            print("Usage: python3 index_vault.py --query 'question' [--json]", file=sys.stderr)
            sys.exit(1)
        results = query_vault(sys.argv[2])
        if "--json" in sys.argv:
            print(json.dumps(results, ensure_ascii=False))
        else:
            print(f"🔍 '{sys.argv[2]}'\n")
            if not results:
                print("No results.")
            else:
                for i, r in enumerate(results):
                    print(f"── [{i+1}] {r['source']} (score: {r['score']:.4f})")
                    print(r["text"][:500])
                    print()

    elif len(sys.argv) > 1 and sys.argv[1] == "--update":
        if not ensure_ollama():
            sys.exit(1)
        start = time.time()
        update_index()
        print(f"⏱️  {time.time() - start:.1f}s")

    else:
        if not ensure_ollama():
            sys.exit(1)
        print("🔨 Indexing...")
        start = time.time()
        index_workspace()
        print(f"⏱️  {time.time() - start:.1f}s")
