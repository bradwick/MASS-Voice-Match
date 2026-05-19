"""Voice embedding and vector search functionality."""
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import logging
import os

from .const import DEFAULT_MODEL, DOMAIN

_LOGGER = logging.getLogger(__name__)

def get_model(hass, model_name: str = DEFAULT_MODEL) -> SentenceTransformer:
    """Get or create the sentence transformer model."""
    if "model" not in hass.data[DOMAIN]:
        _LOGGER.info("Loading sentence transformer model: %s", model_name)
        hass.data[DOMAIN]["model"] = SentenceTransformer(model_name)

    return hass.data[DOMAIN]["model"]


def build_index(hass, items: list, model_name: str = DEFAULT_MODEL, save_path: str = None) -> int:
    """
    Build a FAISS vector index from items and optionally save it.
    """
    if not items:
        _LOGGER.warning("No items provided to build_index")
        return 0

    _LOGGER.info("Building voice match index with %d items", len(items))

    try:
        model = get_model(hass, model_name)

        texts = [item.get("text", "") for item in items]

        embeddings = model.encode(texts, normalize_embeddings=True)
        embeddings = np.array(embeddings).astype("float32")

        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)

        hass.data[DOMAIN]["index"] = index
        hass.data[DOMAIN]["items"] = items

        if save_path:
            faiss.write_index(index, save_path)
            _LOGGER.info("Saved FAISS index to %s", save_path)

        return len(items)

    except Exception as err:
        _LOGGER.error("Error building voice match index: %s", err)
        raise


def load_index(hass, items: list, load_path: str):
    """Load FAISS index from disk if it exists, otherwise return False."""
    if not items or not os.path.exists(load_path):
        return False

    try:
        index = faiss.read_index(load_path)
        if index.ntotal != len(items):
            _LOGGER.warning("Stored index size mismatch, rebuilding...")
            return False

        hass.data[DOMAIN]["index"] = index
        hass.data[DOMAIN]["items"] = items
        _LOGGER.info("Loaded FAISS index from %s", load_path)
        return True
    except Exception as err:
        _LOGGER.warning("Error loading FAISS index: %s", err)
        return False


def search(hass, query: str, model_name: str = DEFAULT_MODEL) -> tuple:
    """
    Search for the best match for a voice query.
    """
    index = hass.data[DOMAIN].get("index")
    items = hass.data[DOMAIN].get("items")

    if index is None or items is None:
        raise RuntimeError("Voice match index not loaded")

    if not query:
        raise ValueError("Query cannot be empty")

    try:
        model = get_model(hass, model_name)

        query_embedding = model.encode([query], normalize_embeddings=True)
        query_embedding = np.array(query_embedding).astype("float32")

        scores, indices = index.search(query_embedding, 1)

        item_idx = int(indices[0][0])
        score = float(scores[0][0])

        _LOGGER.debug("Voice match query '%s': found '%s' with score %.3f",
                     query, items[item_idx].get("name", ""), score)

        return items[item_idx], score

    except Exception as err:
        _LOGGER.error("Error searching voice match index: %s", err)
        raise
