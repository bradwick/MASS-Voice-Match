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

    # Try Vector Search first
    if index and model:
        try:
            query_embedding = model.encode([query], normalize_embeddings=True)
            query_embedding = np.array(query_embedding).astype("float32")

            scores, indices = index.search(query_embedding, 1)

            item_idx = int(indices[0][0])
            score = float(scores[0][0])

            _LOGGER.debug("Vector match query '%s': found '%s' with score %.3f",
                         query, items[item_idx].get("name", ""), score)

            return items[item_idx], score
        except Exception as err:
            _LOGGER.warning("Vector search failed: %s. Falling back to fuzzy.", err)

    # Fallback to Fuzzy Matching
    _LOGGER.debug("Using fuzzy matching for query: %s", query)

    texts = [item.get("text", "") for item in items]
    result = process.extractOne(query, texts, scorer=fuzz.WRatio)

    if result:
        matched_text, score, idx = result
        # Normalize rapidfuzz score (0-100) to match vector search (0-1 approx)
        normalized_score = score / 100.0
        _LOGGER.debug("Fuzzy match query '%s': found '%s' with score %.3f",
                     query, items[idx].get("name", ""), normalized_score)
        return items[idx], normalized_score

    return items[0], 0.0
