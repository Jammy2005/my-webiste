# vector_index.py
#
# Purpose:
#   1. Load your markdown files
#   2. Split them into chunks
#   3. Embed those chunks
#   4. Store them in a persistent Chroma vector database
#   5. Run a quick retrieval test
#
# Install:
#   pip install -U langchain langchain-core langchain-text-splitters langchain-openai langchain-chroma
#
# Environment:
#   export OPENAI_API_KEY="your_key_here"

from pathlib import Path
from typing import List
import shutil
import os

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

from dotenv import load_dotenv
load_dotenv()

# ------------------------------------------------------------
# 1. Paths
# ------------------------------------------------------------
# Resolve everything relative to this file so deployment is safer.
BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "my_agent" / "source"        # folder containing your .md files
CHROMA_DIR = BASE_DIR / "chroma_db"                # where Chroma will persist data locally


# ------------------------------------------------------------
# 2. Splitter setup
# ------------------------------------------------------------
# Your docs are structured like:
#   # Project Name
#   ## Executive Summary
#   ## Technical Architecture
# etc.
#
# So we split first by project and section.
headers_to_split_on = [
    ("#", "project"),
    ("##", "section"),
]

markdown_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=headers_to_split_on,
    strip_headers=False,  # keep headers in the chunk text itself
)

# Secondary splitter for sections that are too long.
recursive_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1800,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""],
)


# ------------------------------------------------------------
# 3. Small helpers to clean metadata
# ------------------------------------------------------------
def clean_project_title(title: str | None) -> str | None:
    """
    Example:
        'Project Dossier: Scada Virtual Agent' -> 'Scada Virtual Agent'
    If the text doesn't contain that prefix, leave it unchanged.
    """
    if not title:
        return title
    prefix = "Project Dossier:"
    if title.startswith(prefix):
        return title[len(prefix):].strip()
    return title.strip()


def clean_section_title(title: str | None) -> str | None:
    """
    Example:
        '2. Executive Summary' -> 'Executive Summary'
    We remove a leading numeric prefix like '1. ', '2. ', etc.
    """
    if not title:
        return title

    # Split once on the first ". " pattern if it looks like "2. Something"
    parts = title.split(". ", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return parts[1].strip()

    return title.strip()


# ------------------------------------------------------------
# 4. Split one markdown file into LangChain Documents
# ------------------------------------------------------------
def split_markdown_file(file_path: Path) -> List[Document]:
    """
    Read a markdown file, split by headers, then split long sections further.
    """
    raw_text = file_path.read_text(encoding="utf-8")

    # First pass: split by markdown headers
    header_docs = markdown_splitter.split_text(raw_text)

    enriched_docs: List[Document] = []

    for i, doc in enumerate(header_docs):
        metadata = dict(doc.metadata)

        # Clean up metadata so retrieval/filtering is nicer later
        metadata["project"] = clean_project_title(metadata.get("project"))
        metadata["section"] = clean_section_title(metadata.get("section"))

        # Add file-level metadata
        metadata["source"] = str(file_path)
        metadata["file_name"] = file_path.name
        metadata["project_slug"] = file_path.stem

        # Add a stable chunk source id before recursive splitting
        metadata["header_chunk_index"] = i

        enriched_docs.append(
            Document(
                page_content=doc.page_content,
                metadata=metadata,
            )
        )

    # Second pass: split only long sections further
    final_chunks = recursive_splitter.split_documents(enriched_docs)

    # Add a final per-file chunk index after recursive splitting
    for j, chunk in enumerate(final_chunks):
        chunk.metadata["chunk_index"] = j

    return final_chunks


# ------------------------------------------------------------
# 5. Split all markdown files
# ------------------------------------------------------------
def load_all_chunks(docs_dir: Path) -> List[Document]:
    """
    Load and split all .md files in the docs directory.
    """
    if not docs_dir.exists():
        raise FileNotFoundError(f"Docs directory does not exist: {docs_dir}")

    markdown_files = sorted(docs_dir.glob("*.md"))

    if not markdown_files:
        raise FileNotFoundError(f"No .md files found in: {docs_dir}")

    all_chunks: List[Document] = []

    for md_file in markdown_files:
        file_chunks = split_markdown_file(md_file)
        all_chunks.extend(file_chunks)

    return all_chunks


# ------------------------------------------------------------
# 6. Build the embedding model
# ------------------------------------------------------------
# OpenAIEmbeddings is LangChain's wrapper for OpenAI embedding models.
# You can swap this later if you want another provider.

def build_embeddings() -> OpenAIEmbeddings:
    if not os.getenv("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY is not set.")

    return OpenAIEmbeddings(model="text-embedding-3-large")


# ------------------------------------------------------------
# 7. Build / open the Chroma vector store
# ------------------------------------------------------------
# Chroma can persist locally via persist_directory.
def build_vector_store(embeddings: OpenAIEmbeddings) -> Chroma:
    return Chroma(
        collection_name="project_dossiers",
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DIR),
    )


# ------------------------------------------------------------
# 8. Index the chunks
# ------------------------------------------------------------
def index_documents(vector_store: Chroma, chunks: List[Document]) -> None:
    """
    Add split documents into the vector store.
    """
    # If you re-run this script a lot during development,
    # you may want to clear the collection first.
    # Easiest option is to delete the chroma_db folder manually.
    vector_store.add_documents(chunks)


# ------------------------------------------------------------
# 9. Quick retrieval test
# ------------------------------------------------------------
def test_retrieval(vector_store: Chroma, query: str, k: int = 4) -> None:
    """
    Run a similarity search and print the top results.
    """
    results = vector_store.similarity_search(query, k=k)

    print("\n" + "=" * 100)
    print(f"QUERY: {query}")
    print(f"TOP {k} RESULTS")
    print("=" * 100)

    for i, doc in enumerate(results, start=1):
        print(f"\nRESULT {i}")
        print("- Metadata:")
        print(doc.metadata)
        print("- Content preview:")
        print(doc.page_content[:900])


# ------------------------------------------------------------
# 10. Main
# ------------------------------------------------------------
if __name__ == "__main__":
    print(f"Loading docs from: {DOCS_DIR}")
    chunks = load_all_chunks(DOCS_DIR)
    print(f"Total chunks loaded: {len(chunks)}")

    if CHROMA_DIR.exists():
        print("Removing existing Chroma DB...")
        shutil.rmtree(CHROMA_DIR)
    
    embeddings = build_embeddings()
    vector_store = build_vector_store(embeddings)

    print("Indexing chunks into Chroma...")
    index_documents(vector_store, chunks)
    print("Done indexing.")

    # Run a few test searches to sanity-check retrieval
    test_retrieval(vector_store, "What is the tech stack of the SCADA project?")
    test_retrieval(vector_store, "Which projects use LangGraph?")
    test_retrieval(vector_store, "What are the limitations of the e-commerce agent?")