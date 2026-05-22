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


def search(hass, query: str, model_name: str = DEFAULT_MODEL) -> tuple:
    """
    Search for the best match using Vector Search (if available) or Fuzzy Matching.
    """
    items = hass.data[DOMAIN].get("items")
    index = hass.data[DOMAIN].get("index")
    model = get_model(hass, model_name)

    if not items:
        raise RuntimeError("Voice match items not loaded")

    if not query:
        raise ValueError("Query cannot be empty")

    query_lower = query.lower().strip()

    # Early exact match check
    for item in items:
        if query_lower == item.get("text", "").lower().strip() or \
           query_lower == item.get("name", "").lower().strip():
            _LOGGER.debug("Found early exact match: %s", item.get("text"))
            return item, 1.0

    # Try Vector Search first
    if index and model:
        try:
            _LOGGER.debug("Vector search query: '%s'", query)
            query_embedding = model.encode([query], normalize_embeddings=True)
            query_embedding = np.array(query_embedding).astype("float32")

            scores, indices = index.search(query_embedding, 10)

            _LOGGER.debug("Vector search returned %d results", len(indices[0]))

            best_idx = -1
            best_score = -1.0
            exact_match_item = None

            for i in range(len(indices[0])):
                idx = int(indices[0][i])
                if idx < 0: continue

                score = float(scores[0][i])
                item = items[idx]
                item_text = item.get("text", "").lower().strip()
                item_name = item.get("name", "").lower().strip()

                _LOGGER.debug("Result %d: '%s' (score: %.3f)", i + 1, item.get("name"), score)

                if exact_match_item is None:
                    if query_lower == item_text or query_lower == item_name:
                        exact_match_item = item

                if i == 0:
                    best_idx = idx
                    best_score = score

            if exact_match_item:
                _LOGGER.debug("Found exact match in vector results: %s", exact_match_item.get("text"))
                return exact_match_item, 1.0

            # Sanity check: verify vector match with a fuzzy score to avoid false positives
            if best_idx >= 0:
                best_item = items[best_idx]
                fuzzy_score = fuzz.token_set_ratio(
                    query_lower,
                    best_item.get("text", "").lower().strip()
                ) / 100.0

                # If fuzzy score is low, it's likely a false positive from the vector model
                # token_set_ratio is more lenient, so we use a higher threshold (0.6)
                if fuzzy_score < 0.6:
                    _LOGGER.debug("Vector match '%s' failed fuzzy sanity check (score %.3f)",
                                 best_item.get("text"), fuzzy_score)
                    # We continue to fuzzy fallback instead of returning this
                else:
                    _LOGGER.debug("Vector match query '%s': found '%s' with score %.3f (fuzzy sanity: %.3f)",
                                 query, best_item.get("name", ""), best_score, fuzzy_score)
                    return best_item, best_score

        except Exception as err:
            _LOGGER.warning("Vector search failed: %s. Falling back to fuzzy.", err)

    # Fallback to Fuzzy Matching
    _LOGGER.debug("Using fuzzy matching for query: %s", query)

    texts = [item.get("text", "") for item in items]
    # Using a hybrid approach for fuzzy fallback:
    # token_set_ratio is good for partial matches, but can give high scores to short common words.
    # We combine it with ratio to ensure some overall similarity.
    best_item = None
    best_fuzzy_score = -1.0

    # We use a smaller limit for manual scoring
    results = process.extract(
        query,
        texts,
        scorer=fuzz.token_set_ratio,
        limit=20,
        processor=lambda x: x.lower().strip()
    )

    if results:
        for matched_text, ts_score, idx in results:
            ts_score /= 100.0
            r_score = fuzz.ratio(query_lower, matched_text.lower().strip()) / 100.0

            # Hybrid score: heavily weighted towards token_set but penalized if ratio is extremely low
            hybrid_score = (ts_score * 0.8) + (r_score * 0.2)

            if hybrid_score > best_fuzzy_score:
                best_fuzzy_score = hybrid_score
                best_item = items[idx]

        if best_item:
            _LOGGER.debug("Fuzzy match query '%s': found '%s' with score %.3f",
                         query, best_item.get("name", ""), best_fuzzy_score)
            return best_item, best_fuzzy_score

    return None, 0.0
