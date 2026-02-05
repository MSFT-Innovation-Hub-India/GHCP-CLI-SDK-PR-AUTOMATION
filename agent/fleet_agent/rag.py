from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import re
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

@dataclass(frozen=True)
class Hit:
    doc_id: str
    score: float
    excerpt: str


# Token provider for Azure AD authentication
_credential = None
_token_provider = None

def _get_token() -> str:
    """Get Azure AD token using DefaultAzureCredential."""
    global _credential, _token_provider
    if _credential is None:
        _credential = DefaultAzureCredential()
        _token_provider = get_bearer_token_provider(
            _credential, "https://cognitiveservices.azure.com/.default"
        )
    return _token_provider()


def _get_client() -> OpenAI:
    """
    Create OpenAI client configured for Azure OpenAI Responses API.
    Uses base_url with /openai/v1 path (OpenAI v1 format, not Azure format).
    """
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    
    if not endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT must be set")
    
    # Ensure endpoint ends with /openai/v1 for Responses API compatibility
    base_url = endpoint.rstrip("/")
    if not base_url.endswith("/openai/v1"):
        base_url = f"{base_url}/openai/v1"
    
    return OpenAI(
        base_url=base_url,
        api_key=_get_token(),  # Azure AD token
    )


def search(query: str, k: int = 4) -> list[Hit]:
    """
    Search the Azure OpenAI vector store using the Responses API with file_search tool.
    
    Args:
        query: The search query string
        k: Maximum number of results to return (default: 4)
    
    Returns:
        List of Hit objects with document ID, score, and excerpt
    """
    vector_store_id = os.getenv("AZURE_OPENAI_VECTOR_STORE_ID", "")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    
    if not vector_store_id:
        raise ValueError("AZURE_OPENAI_VECTOR_STORE_ID must be set")
    
    client = _get_client()
    
    # Use Responses API with file_search tool
    response = client.responses.create(
        model=deployment,
        input=query,
        tools=[{
            "type": "file_search",
            "vector_store_ids": [vector_store_id],
            "max_num_results": k
        }]
    )
    
    hits: list[Hit] = []
    
    # Extract file search results from the response
    for output in response.output:
        if output.type == "file_search_call":
            for result in output.results or []:
                hits.append(Hit(
                    doc_id=result.filename or result.file_id,
                    score=result.score if hasattr(result, 'score') else 1.0,
                    excerpt=_extract_excerpt(result.text) if hasattr(result, 'text') else ""
                ))
    
    return hits[:k]


def _extract_excerpt(text: str, max_length: int = 520) -> str:
    """Extract a clean excerpt from the text."""
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[:max_length].rsplit(" ", 1)[0] + "..."


# ============================================================================
# Legacy local search (fallback if Azure OpenAI is not configured)
# ============================================================================

def _tok(s: str) -> list[str]:
    return [t for t in re.split(r"[^a-zA-Z0-9_]+", s.lower()) if len(t) >= 3]


def load_corpus(knowledge_root: Path) -> list[tuple[str, str]]:
    """Load markdown files from local knowledge directory (legacy fallback)."""
    docs: list[tuple[str, str]] = []
    for p in knowledge_root.rglob("*.md"):
        docs.append((str(p.relative_to(knowledge_root)), p.read_text(encoding="utf-8")))
    return docs


def search_local(docs: list[tuple[str, str]], query: str, k: int = 4) -> list[Hit]:
    """Legacy local keyword-based search (fallback if Azure OpenAI is not configured)."""
    q = _tok(query)
    scored: list[tuple[int, str, str]] = []
    for doc_id, text in docs:
        toks = _tok(text)
        score = sum(toks.count(term) for term in q)
        if score:
            scored.append((score, doc_id, text))
    scored.sort(reverse=True, key=lambda x: x[0])

    hits: list[Hit] = []
    for score, doc_id, text in scored[:k]:
        hits.append(Hit(doc_id=doc_id, score=float(score), excerpt=_excerpt_local(text, q)))
    return hits


def _excerpt_local(text: str, terms: list[str]) -> str:
    lower = text.lower()
    idxs = [lower.find(t) for t in terms if lower.find(t) != -1]
    idx = min(idxs) if idxs else 0
    start = max(0, idx - 160)
    return re.sub(r"\s+", " ", text[start:start+520]).strip()
