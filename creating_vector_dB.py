# vector_index.py
#
# Purpose:
#   1. Load your markdown files
#   2. Split them into chunks
#   3. Enrich chunk text with project/section context
#   4. Embed those chunks
#   5. Store them in a persistent Chroma vector database
#   6. Run a quick retrieval test
#
# Install:
#   pip install -U langchain langchain-core langchain-text-splitters langchain-openai langchain-chroma python-dotenv
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
DOCS_DIR = BASE_DIR / "my_agent" / "source"   # folder containing your .md files
CHROMA_DIR = BASE_DIR / "chroma_db"           # where Chroma will persist data locally


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
    chunk_size=1200,
    chunk_overlap=150,
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

    title = title.strip()

    prefixes = [
        "Project Dossier:",
        "Project:",
    ]

    for prefix in prefixes:
        if title.startswith(prefix):
            return title[len(prefix):].strip()

    return title


def clean_section_title(title: str | None) -> str | None:
    """
    Example:
        '2. Executive Summary' -> 'Executive Summary'
    We remove a leading numeric prefix like '1. ', '2. ', etc.
    """
    if not title:
        return title

    title = title.strip()

    parts = title.split(". ", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return parts[1].strip()

    return title


def build_contextualized_chunk_text(
    original_text: str,
    project: str | None,
    section: str | None,
    file_name: str | None,
) -> str:
    """
    Build richer chunk text so embeddings include document context.

    Example output:

        Project: Scada Virtual Agent
        Section: Tech Stack
        File: SCADA_agent_dossier.md

        ## 9. Tech Stack
        - Python
        - FastAPI
        - LangGraph
    """
    prefix_lines = []

    if project:
        prefix_lines.append(f"Project: {project}")
    if section:
        prefix_lines.append(f"Section: {section}")
    if file_name:
        prefix_lines.append(f"File: {file_name}")

    prefix = "\n".join(prefix_lines).strip()
    body = original_text.strip()

    if prefix:
        return f"{prefix}\n\n{body}"

    return body


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

        # Add a stable header-level index before recursive splitting
        metadata["header_chunk_index"] = i

        cleaned_text = doc.page_content.strip()
        if not cleaned_text:
            continue

        enriched_docs.append(
            Document(
                page_content=cleaned_text,
                metadata=metadata,
            )
        )

    # Second pass: split only long sections further
    final_chunks = recursive_splitter.split_documents(enriched_docs)

    # Add a final per-file chunk index after recursive splitting
    # and rewrite the chunk text so the embeddings include metadata context.
    cleaned_final_chunks: List[Document] = []

    for j, chunk in enumerate(final_chunks):
        chunk_text = chunk.page_content.strip()
        if not chunk_text:
            continue

        chunk.metadata["chunk_index"] = j

        chunk.page_content = build_contextualized_chunk_text(
            original_text=chunk_text,
            project=chunk.metadata.get("project"),
            section=chunk.metadata.get("section"),
            file_name=chunk.metadata.get("file_name"),
        )

        cleaned_final_chunks.append(chunk)

    return cleaned_final_chunks


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
def build_embeddings() -> OpenAIEmbeddings:
    """
    Build the embeddings model.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY is not set.")

    return OpenAIEmbeddings(model="text-embedding-3-large")


# ------------------------------------------------------------
# 7. Build / open the Chroma vector store
# ------------------------------------------------------------
def build_vector_store(embeddings: OpenAIEmbeddings) -> Chroma:
    """
    Build a persistent local Chroma vector store.
    """
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
    Add split documents into the vector store with stable IDs.
    """
    ids = [
        f"{chunk.metadata.get('project_slug', 'unknown')}::"
        f"{chunk.metadata.get('header_chunk_index', 'x')}::"
        f"{chunk.metadata.get('chunk_index', i)}"
        for i, chunk in enumerate(chunks)
    ]

    vector_store.add_documents(documents=chunks, ids=ids)


# ------------------------------------------------------------
# 9. Quick retrieval test
# ------------------------------------------------------------
def test_retrieval(vector_store: Chroma, query: str, k: int = 8) -> None: # increased k
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
    # test_retrieval(vector_store, "What is the tech stack of the SCADA project?")
    # test_retrieval(vector_store, "Which projects use LangGraph?")
    # test_retrieval(vector_store, "What are the limitations of the e-commerce agent?")
    test_retrieval(vector_store, "What are the limitations of the e-commerce agent?")

    if CHROMA_DIR.exists():
        print("Exists")
    else:
        print("Does not exist")