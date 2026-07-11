"""Voice embedding and vector search functionality with fuzzy fallback."""
import numpy as np
import logging
import os
from rapidfuzz import process, fuzz

from .const import DEFAULT_MODEL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Lazy imports for heavy ML libraries
_FAISS = None
_SENTENCE_TRANSFORMERS = None

def _get_faiss():
    global _FAISS
    if _FAISS is None:
        try:
            import faiss
            _FAISS = faiss
        except ImportError:
            _FAISS = False
    return _FAISS

def _get_st():
    global _SENTENCE_TRANSFORMERS
    if _SENTENCE_TRANSFORMERS is None:
        try:
            from sentence_transformers import SentenceTransformer
            _SENTENCE_TRANSFORMERS = SentenceTransformer
        except ImportError:
            _SENTENCE_TRANSFORMERS = False
    return _SENTENCE_TRANSFORMERS


def get_model(hass, model_name: str = DEFAULT_MODEL):
    """Get or create the sentence transformer model."""
    if "model" not in hass.data[DOMAIN]:
        st_class = _get_st()
        if st_class:
            _LOGGER.info("Loading sentence transformer model: %s", model_name)
            try:
                hass.data[DOMAIN]["model"] = st_class(model_name)
            except Exception as err:
                _LOGGER.warning("Failed to load sentence transformer: %s. Using fuzzy fallback.", err)
                hass.data[DOMAIN]["model"] = False
        else:
            _LOGGER.info("sentence-transformers not available. Using fuzzy fallback.")
            hass.data[DOMAIN]["model"] = False

    return hass.data[DOMAIN]["model"]


def build_index(hass, items: list, model_name: str = DEFAULT_MODEL, save_path: str = None) -> int:
    """
    Build a FAISS vector index from items and optionally save it.
    """
    if not items:
        _LOGGER.warning("No items provided to build_index")
        return 0

    hass.data[DOMAIN]["items"] = items

    model = get_model(hass, model_name)
    faiss_lib = _get_faiss()

    if not model or not faiss_lib:
        _LOGGER.info("Vector search libraries missing. Using fuzzy matching only.")
        hass.data[DOMAIN]["index"] = False
        return len(items)

    _LOGGER.info("Building voice match vector index with %d items", len(items))

    try:
        texts = [item.get("text", "") for item in items]

        embeddings = model.encode(texts, normalize_embeddings=True)
        embeddings = np.array(embeddings).astype("float32")

        index = faiss_lib.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)

        hass.data[DOMAIN]["index"] = index

        if save_path:
            faiss_lib.write_index(index, save_path)
            _LOGGER.info("Saved FAISS index to %s", save_path)

        return len(items)

    except Exception as err:
        _LOGGER.error("Error building voice match index: %s", err)
        hass.data[DOMAIN]["index"] = False
        return len(items)


def load_index(hass, items: list, load_path: str):
    """Load FAISS index from disk if it exists, otherwise return False."""
    hass.data[DOMAIN]["items"] = items

    faiss_lib = _get_faiss()
    if not items or not os.path.exists(load_path) or not faiss_lib:
        return False

    try:
        index = faiss_lib.read_index(load_path)
        if index.ntotal != len(items):
            _LOGGER.warning("Stored index size mismatch, rebuilding...")
            return False

        hass.data[DOMAIN]["index"] = index
        _LOGGER.info("Loaded FAISS index from %s", load_path)
        return True
    except Exception as err:
        _LOGGER.warning("Error loading FAISS index: %s", err)
        return False


def _detect_requested_media_type(query: str) -> tuple:
    """Detect if there is an explicit media type requested, and return (cleaned_query, media_type)."""
    query_lower = query.lower().strip()

    # Prefix patterns
    prefixes = {
        "album": [r"^(?:the\s+)?album\s+(.+)$"],
        "artist": [r"^(?:the\s+)?artist\s+(.+)$", r"^(?:the\s+)?band\s+(.+)$", r"^(?:the\s+)?singer\s+(.+)$"],
        "playlist": [r"^(?:the\s+)?playlist\s+(.+)$"],
        "track": [r"^(?:the\s+)?track\s+(.+)$", r"^(?:the\s+)?song\s+(.+)$"],
        "radio": [r"^(?:the\s+)?radio\s+(.+)$", r"^(?:the\s+)?station\s+(.+)$", r"^(?:the\s+)?radio\s+station\s+(.+)$"]
    }

    import re
    for media_type, pat_list in prefixes.items():
        for pattern in pat_list:
            match = re.match(pattern, query_lower, re.IGNORECASE)
            if match:
                return match.group(1).strip(), media_type

    # Suffix patterns (more specific patterns first)
    suffixes = {
        "album": [r"^(.+?)\s+album$"],
        "artist": [r"^(.+?)\s+artist$", r"^(.+?)\s+band$", r"^(.+?)\s+singer$"],
        "playlist": [r"^(.+?)\s+playlist$"],
        "track": [r"^(.+?)\s+track$", r"^(.+?)\s+song$"],
        "radio": [r"^(.+?)\s+radio\s+station$", r"^(.+?)\s+radio$", r"^(.+?)\s+station$"]
    }

    for media_type, pat_list in suffixes.items():
        for pattern in pat_list:
            match = re.match(pattern, query_lower, re.IGNORECASE)
            if match:
                return match.group(1).strip(), media_type

    return query_lower, None


def search_top_n(hass, query: str, limit: int = 5, model_name: str = DEFAULT_MODEL) -> list:
    """
    Search for top N matching items using Vector Search (with fuzzy fallback).
    Supports media type prioritization and returns deduplicated results sorted by score.
    Each element in the returned list is a tuple: (item, score).
    """
    items = hass.data[DOMAIN].get("items")
    index = hass.data[DOMAIN].get("index")
    model = get_model(hass, model_name)

    if not items:
        raise RuntimeError("Voice match items not loaded")

    if not query:
        raise ValueError("Query cannot be empty")

    query_lower = query.lower().strip()
    search_query, requested_type = _detect_requested_media_type(query)

    # Track deduplicated results: uri -> (item, score)
    results_map = {}

    # Helper to add/update result with the highest score
    def add_result(item, score):
        uri = item.get("uri")
        if not uri:
            return
        if uri not in results_map or score > results_map[uri][1]:
            results_map[uri] = (item, score)

    # 1. Early exact matches
    for item in items:
        item_text_lower = item.get("text", "").lower().strip()
        item_name_lower = item.get("name", "").lower().strip()

        if search_query == item_text_lower or search_query == item_name_lower or \
           query_lower == item_text_lower or query_lower == item_name_lower:
            score = 1.0
            if requested_type and item.get("type") == requested_type:
                score = 1.05  # Priority boost
            add_result(item, score)

    # 2. Try Vector Search
    vector_success = False
    if index and model:
        try:
            _LOGGER.debug("Vector search query: '%s' (cleaned: '%s', type: %s)", query, search_query, requested_type)
            query_embedding = model.encode([search_query], normalize_embeddings=True)
            query_embedding = np.array(query_embedding).astype("float32")

            # Search a larger pool to allow deduplication
            search_limit = min(50, len(items))
            scores, indices = index.search(query_embedding, search_limit)

            for i in range(len(indices[0])):
                idx = int(indices[0][i])
                if idx < 0:
                    continue

                score = float(scores[0][i])
                item = items[idx]

                # Boost requested media type
                if requested_type and item.get("type") == requested_type:
                    score += 0.15

                # Fuzzy sanity check
                item_text = item.get("text", "").lower().strip()
                fuzzy_score = fuzz.token_set_ratio(search_query, item_text) / 100.0

                if fuzzy_score >= 0.6:
                    add_result(item, score)
                    vector_success = True
                else:
                    _LOGGER.debug("Vector match '%s' failed fuzzy sanity check (score %.3f, fuzzy %.3f)",
                                 item.get("name"), score, fuzzy_score)

        except Exception as err:
            _LOGGER.warning("Vector search failed in search_top_n: %s. Falling back to fuzzy.", err)

    # 3. Fallback to Fuzzy Matching
    if not vector_success:
        _LOGGER.debug("Using fuzzy matching for query: '%s' (cleaned: '%s', type: %s)", query, search_query, requested_type)
        texts = [item.get("text", "") for item in items]

        # Extract top fuzzy candidates
        fuzzy_limit = min(100, len(items))
        fuzzy_results = process.extract(
            search_query,
            texts,
            scorer=fuzz.token_set_ratio,
            limit=fuzzy_limit,
            processor=lambda x: x.lower().strip()
        )

        if fuzzy_results:
            for matched_text, ts_score, idx in fuzzy_results:
                ts_score /= 100.0
                item = items[idx]

                r_score = fuzz.ratio(search_query, matched_text.lower().strip()) / 100.0
                hybrid_score = (ts_score * 0.8) + (r_score * 0.2)

                # Boost requested media type
                if requested_type and item.get("type") == requested_type:
                    hybrid_score += 0.15

                add_result(item, hybrid_score)

    # Sort results by score in descending order
    sorted_results = sorted(results_map.values(), key=lambda x: x[1], reverse=True)

    # Cap score at 1.0 for final presentation, keeping order
    final_results = []
    for item, score in sorted_results[:limit]:
        final_results.append((item, min(1.0, score)))

    return final_results


def search(hass, query: str, model_name: str = DEFAULT_MODEL) -> tuple:
    """
    Search for the best match using Vector Search (if available) or Fuzzy Matching.
    """
    results = search_top_n(hass, query, limit=1, model_name=model_name)
    if results:
        return results[0]
    return None, 0.0
