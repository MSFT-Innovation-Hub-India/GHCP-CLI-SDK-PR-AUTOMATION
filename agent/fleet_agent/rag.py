from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import re
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents.knowledgebases import KnowledgeBaseRetrievalClient
from azure.search.documents.knowledgebases.models import (
    KnowledgeBaseMessage,
    KnowledgeBaseMessageTextContent,
    KnowledgeBaseRetrievalRequest,
    KnowledgeRetrievalLowReasoningEffort,
    KnowledgeRetrievalMediumReasoningEffort,
    KnowledgeRetrievalMinimalReasoningEffort,
    KnowledgeRetrievalOutputMode,
)

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


def _get_kb_client() -> KnowledgeBaseRetrievalClient:
    endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT", "")
    kb_name = os.getenv("AZURE_AI_KB_NAME", "")

    if not endpoint or not kb_name:
        raise ValueError(
            "AZURE_AI_SEARCH_ENDPOINT and AZURE_AI_KB_NAME must be set"
        )

    return KnowledgeBaseRetrievalClient(
        endpoint=endpoint,
        knowledge_base_name=kb_name,
        credential=DefaultAzureCredential(),
    )


def _kb_reasoning_effort() -> object:
    value = os.getenv("AZURE_AI_KB_REASONING_EFFORT", "low").strip().lower()
    if value == "minimal":
        return KnowledgeRetrievalMinimalReasoningEffort()
    if value == "low":
        return KnowledgeRetrievalLowReasoningEffort()
    return KnowledgeRetrievalMediumReasoningEffort()


def _extract_kb_hits(result: object, k: int) -> list[Hit]:
    import json as _json

    hits: list[Hit] = []
    references = getattr(result, "references", None) or []

    # Build lookup: ref index -> metadata from the references list
    ref_meta: dict[int, tuple[str, float]] = {}
    for idx, ref in enumerate(references):
        blob_url = getattr(ref, "blob_url", None) or ""
        # Use the last path segment of the blob URL as a readable doc id
        doc_id = blob_url.rsplit("/", 1)[-1] if blob_url else f"reference-{idx}"
        score = getattr(ref, "reranker_score", None) or 1.0
        ref_meta[idx] = (doc_id, float(score))

    # Extract content from the response messages.
    # The KB returns extractive data as a JSON array in
    # result.response[0].content[0].text with objects like
    # {"ref_id": 0, "content": "..."}
    resp_messages = getattr(result, "response", None) or []
    for msg in resp_messages:
        msg_content = getattr(msg, "content", None) or []
        for block in msg_content:
            text = getattr(block, "text", None) or ""
            if not text:
                continue
            try:
                items = _json.loads(text)
            except (_json.JSONDecodeError, TypeError):
                # Not JSON – treat the raw text as a single hit
                items = [{"ref_id": 0, "content": text}]

            if not isinstance(items, list):
                items = [items]

            for item in items:
                if not isinstance(item, dict):
                    continue
                content = item.get("content") or item.get("text") or ""
                if not content:
                    continue
                ref_id = item.get("ref_id", 0)
                doc_id, score = ref_meta.get(ref_id, (f"reference-{ref_id}", 1.0))
                hits.append(Hit(
                    doc_id=doc_id,
                    score=score,
                    excerpt=_extract_excerpt(content),
                ))
                if len(hits) >= k:
                    return hits

    return hits


def search(query: str, k: int = 4) -> list[Hit]:
    """
    Search the Azure AI Search knowledge base and return extractive results.

    If the knowledge base settings are not configured, falls back to local
    markdown search. The Azure OpenAI Responses API search is kept for
    reference only and is not used by the application.

    Args:
        query: The search query string
        k: Maximum number of results to return (default: 4)

    Returns:
        List of Hit objects with document ID, score, and excerpt
    """
    if not (
        os.getenv("AZURE_AI_SEARCH_ENDPOINT")
        and os.getenv("AZURE_AI_KB_NAME")
    ):
        raise ValueError(
            "Azure AI Search knowledge base settings are required for RAG. "
            "Set AZURE_AI_SEARCH_ENDPOINT and AZURE_AI_KB_NAME."
        )

    client = _get_kb_client()
    request = KnowledgeBaseRetrievalRequest(
        messages=[
            KnowledgeBaseMessage(
                role="user",
                content=[KnowledgeBaseMessageTextContent(text=query.strip())],
            )
        ],
        include_activity=False,
        output_mode=KnowledgeRetrievalOutputMode.EXTRACTIVE_DATA,
        retrieval_reasoning_effort=_kb_reasoning_effort(),
    )
    result = client.retrieve(request)
    return _extract_kb_hits(result, k)


def search_openai_vector_store_reference(query: str, k: int = 4) -> list[Hit]:
    """
    Reference implementation for Azure OpenAI Responses API + file_search.
    Not used by the application; kept for comparison and fallback testing.
    """
    vector_store_id = os.getenv("AZURE_OPENAI_VECTOR_STORE_ID", "")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    if not vector_store_id:
        raise ValueError("AZURE_OPENAI_VECTOR_STORE_ID must be set")

    client = _get_client()

    response = client.responses.create(
        model=deployment,
        input=query,
        tools=[{
            "type": "file_search",
            "vector_store_ids": [vector_store_id],
            "max_num_results": k,
        }],
    )

    hits: list[Hit] = []
    seen_files: set[str] = set()

    for output in response.output:
        if output.type == "file_search_call" and output.results:
            for result in output.results:
                file_id = getattr(result, "filename", None) or getattr(result, "file_id", "unknown")
                if file_id not in seen_files:
                    seen_files.add(file_id)
                    hits.append(Hit(
                        doc_id=file_id,
                        score=getattr(result, "score", 1.0),
                        excerpt=_extract_excerpt(getattr(result, "text", "")),
                    ))

        elif output.type == "message" and hasattr(output, "content"):
            for content_block in output.content:
                if hasattr(content_block, "annotations"):
                    for annotation in content_block.annotations:
                        if hasattr(annotation, "filename") and annotation.filename:
                            file_id = annotation.filename
                            if file_id not in seen_files:
                                seen_files.add(file_id)
                                text = getattr(content_block, "text", "")
                                hits.append(Hit(
                                    doc_id=file_id,
                                    score=1.0,
                                    excerpt=_extract_excerpt(text),
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
