"""
CLI entry point for the Customer AI Support System.

Ingest a knowledge-base document (PDF or DOCX), then chat with the RAG assistant.
"""

import argparse
import hashlib
import json
import os
import sys

import google.generativeai as genai
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from ingestion_pipeline.ingestionPipeline import run_ingestion_pipeline
from inference_pipeline.inferencePipeline import run_inference_pipeline

CACHE_DIR = "knowledge_base_cache"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
GEMINI_MODEL = "gemini-1.5-flash-latest"


def get_file_hash(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def ensure_ingested(doc_path: str, doc_hash: str, embedding_model) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    index_path = os.path.join(CACHE_DIR, f"{doc_hash}.index")
    if os.path.exists(index_path):
        print(f"Using cached knowledge base for document hash: {doc_hash}")
        return
    run_ingestion_pipeline(
        doc_path=doc_path,
        doc_hash=doc_hash,
        embedding_model=embedding_model,
        cache_dir=CACHE_DIR,
    )


def run_chat(doc_hash: str, embedding_model, generative_model) -> None:
    loaded_indexes = {}
    loaded_chunks = {}
    history = []

    print("\nKnowledge base ready. Type your questions (or 'exit' / 'quit' to stop).\n")

    while True:
        try:
            query = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not query:
            continue
        if query.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break

        answer = run_inference_pipeline(
            query=query,
            history=history,
            doc_hash=doc_hash,
            cache_dir=CACHE_DIR,
            embedding_model=embedding_model,
            generative_model=generative_model,
            loaded_indexes=loaded_indexes,
            loaded_chunks=loaded_chunks,
        )

        print(f"\nAssistant > {answer}\n")
        history.append({"role": "user", "content": query})
        history.append({"role": "model", "content": answer})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Customer AI Support System — ingest a document and chat with the assistant."
    )
    parser.add_argument(
        "document",
        help="Path to a .pdf or .docx knowledge-base file",
    )
    args = parser.parse_args()

    doc_path = os.path.abspath(args.document)
    if not os.path.isfile(doc_path):
        print(f"Error: file not found: {doc_path}", file=sys.stderr)
        sys.exit(1)

    ext = os.path.splitext(doc_path)[1].lower()
    if ext not in {".pdf", ".docx"}:
        print("Error: only .pdf and .docx files are supported.", file=sys.stderr)
        sys.exit(1)

    load_dotenv()
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        print("Error: set GEMINI_API_KEY in backend/.env", file=sys.stderr)
        sys.exit(1)

    print("Loading embedding model (first run may download weights)...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    genai.configure(api_key=gemini_key)
    generative_model = genai.GenerativeModel(GEMINI_MODEL)

    doc_hash = get_file_hash(doc_path)
    print(f"Document: {os.path.basename(doc_path)}")
    ensure_ingested(doc_path, doc_hash, embedding_model)
    run_chat(doc_hash, embedding_model, generative_model)


if __name__ == "__main__":
    main()
