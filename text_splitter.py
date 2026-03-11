# pip install -U langchain-text-splitters langchain-core

from pathlib import Path
from typing import List

from langchain_core.documents import Document

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


# ------------------------------------------------------------
# 1. Point this at the folder containing your markdown dossiers
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "my_agent" / "source"  # change this to your real folder path


# ------------------------------------------------------------
# 2. Choose which markdown headers to split on
# ------------------------------------------------------------
# Your documents use headings like:
#   # Project Dossier: ...
#   ## 1. One-Sentence Summary
#   ## 2. Executive Summary
#   ### 8.1 User → Frontend → Backend
#
# So we split on H1, H2, and H3.
headers_to_split_on = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]


# ------------------------------------------------------------
# 3. Create the markdown header splitter
# ------------------------------------------------------------
# strip_headers=False means the actual header text stays inside the chunk.
# I recommend this for RAG because the chunk itself will still contain
# labels like "## Technical Architecture", which helps retrieval.
markdown_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=headers_to_split_on,
    strip_headers=False,
)


# ------------------------------------------------------------
# 4. Create the secondary splitter for long sections
# ------------------------------------------------------------
# This kicks in AFTER header splitting.
#
# Why do this?
# Some sections like Executive Summary or Technical Architecture
# may still be too long to embed as one chunk.
#
# These separators tell LangChain how to try splitting:
# first by paragraph, then by line, then by space, then by character.
#
# You can tune chunk_size/chunk_overlap later.
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1800,      # character-based starting point
    chunk_overlap=200,    # overlap between neighboring chunks
    separators=["\n\n", "\n", ". ", " ", ""],
)


# ------------------------------------------------------------
# 5. Function to split one markdown file
# ------------------------------------------------------------
def split_markdown_file(file_path: Path) -> List[Document]:
    """
    Read one markdown file, split it by markdown headers first,
    then split oversized sections into smaller overlapping chunks.
    Returns a list of LangChain Document objects.
    """

    # Read the raw markdown text
    raw_text = file_path.read_text(encoding="utf-8")

    # First pass: split by markdown headers
    # Each returned Document will already have metadata like:
    #   {"h1": "...", "h2": "...", "h3": "..."}
    header_docs = markdown_splitter.split_text(raw_text)

    # Add useful file-level metadata to every section
    # This is very important for retrieval later.
    enriched_docs = []
    for doc in header_docs:
        # Copy existing metadata from the markdown splitter
        metadata = dict(doc.metadata)

        # Add your own metadata
        metadata["source"] = str(file_path)
        metadata["file_name"] = file_path.name
        metadata["project"] = file_path.stem  # e.g. "SCADA_agent_dossier"

        # Create a new Document with updated metadata
        enriched_docs.append(
            Document(
                page_content=doc.page_content,
                metadata=metadata,
            )
        )

    # Second pass: split long sections into smaller chunks
    # IMPORTANT:
    # We use split_documents(...) rather than split_text(...)
    # so LangChain keeps the metadata from each section.
    final_chunks = text_splitter.split_documents(enriched_docs)

    return final_chunks


# ------------------------------------------------------------
# 6. Function to split all markdown files in a folder
# ------------------------------------------------------------
def split_all_markdown_files(docs_dir: Path) -> List[Document]:
    """
    Find all .md files in the folder, split each one,
    and combine everything into one big list of chunks.
    """

    all_chunks = []

    # Grab all markdown files in sorted order
    markdown_files = sorted(docs_dir.glob("*.md"))

    for md_file in markdown_files:
        file_chunks = split_markdown_file(md_file)
        all_chunks.extend(file_chunks)

    return all_chunks


# ------------------------------------------------------------
# 7. Run the splitter
# ------------------------------------------------------------
chunks = split_all_markdown_files(DOCS_DIR)

print(f"Total chunks created: {len(chunks)}")


# ------------------------------------------------------------
# 8. Inspect a few example chunks
# ------------------------------------------------------------
# This helps you sanity-check whether the split is good.
for i, chunk in enumerate(chunks[:5], start=1):
    print("\n" + "=" * 80)
    print(f"CHUNK {i}")
    print("- Metadata:")
    print(chunk.metadata)
    print("- Content preview:")
    print(chunk.page_content[:800])  # first 800 chars
    print("=" * 80)


# ------------------------------------------------------------
# 9. Optional: turn chunks into plain dicts for debugging / JSON
# ------------------------------------------------------------
chunk_dicts = [
    {
        "content": chunk.page_content,
        "metadata": chunk.metadata,
    }
    for chunk in chunks
]

# Example:
# print(chunk_dicts[0])