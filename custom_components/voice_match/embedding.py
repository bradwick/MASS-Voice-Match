"""Voice embedding and vector search functionality."""
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import logging

from .storage import save_json, load_json
from .const import CONF_MODEL, DEFAULT_MODEL

_LOGGER = logging.getLogger(__name__)

# Global state
_MODEL = None
_INDEX = None
_ITEMS = None

INDEX_PATH = "/config/voice_match/index.faiss"
ITEMS_PATH = "/config/voice_match/items.json"


def get_model(model_name: str = DEFAULT_MODEL) -> SentenceTransformer:
    """Get or create the sentence transformer model."""
    global _MODEL
    
    if _MODEL is None:
        _LOGGER.info("Loading sentence transformer model: %s", model_name)
        _MODEL = SentenceTransformer(model_name)
    
    return _MODEL


def build_index(items: list, model_name: str = DEFAULT_MODEL) -> int:
    """
    Build a FAISS vector index from items.
    
    Args:
        items: List of items with 'text', 'name', and 'media_id' keys
        model_name: Name of the sentence transformer model to use
        
    Returns:
        Number of items indexed
    """
    global _INDEX, _ITEMS
    
    if not items:
        _LOGGER.warning("No items provided to build_index")
        return 0
    
    _LOGGER.info("Building voice match index with %d items using model: %s", 
                 len(items), model_name)
    
    try:
        # Get the model
        model = get_model(model_name)
        
        # Extract texts for embedding
        texts = [item.get("text", "") for item in items]
        
        # Generate embeddings
        embeddings = model.encode(texts, normalize_embeddings=True)
        embeddings = np.array(embeddings).astype("float32")
        
        # Create FAISS index (inner product for normalized embeddings)
        _INDEX = faiss.IndexFlatIP(embeddings.shape[1])
        _INDEX.add(embeddings)
        _ITEMS = items
        
        # Save to disk
        save(_ITEMS)
        
        _LOGGER.info("Voice match index built successfully with %d items", len(items))
        return len(items)
        
    except Exception as err:
        _LOGGER.error("Error building voice match index: %s", err)
        raise


def search(query: str, sensitivity: float = 0.7, model_name: str = DEFAULT_MODEL) -> tuple:
    """
    Search for the best match for a voice query.
    
    Args:
        query: The voice query text
        sensitivity: Match threshold (0.0-1.0), higher = stricter matching
        model_name: Name of the sentence transformer model to use
        
    Returns:
        Tuple of (item, score) where score is the similarity score
    """
    global _INDEX, _ITEMS
    
    if _INDEX is None or _ITEMS is None:
        _LOGGER.error("Index not loaded. Call load_index() first.")
        raise RuntimeError("Voice match index not loaded")
    
    if not query:
        raise ValueError("Query cannot be empty")
    
    try:
        # Get the model
        model = get_model(model_name)
        
        # Encode the query
        query_embedding = model.encode([query], normalize_embeddings=True)
        query_embedding = np.array(query_embedding).astype("float32")
        
        # Search the index
        scores, indices = _INDEX.search(query_embedding, 1)
        
        item_idx = int(indices[0][0])
        score = float(scores[0][0])
        
        _LOGGER.debug("Voice match query '%s': found '%s' with score %.3f", 
                     query, _ITEMS[item_idx].get("name", ""), score)
        
        return _ITEMS[item_idx], score
        
    except Exception as err:
        _LOGGER.error("Error searching voice match index: %s", err)
        raise


def save(items: list) -> None:
    """Save items to disk."""
    try:
        save_json(ITEMS_PATH, items)
        _LOGGER.debug("Saved %d items to %s", len(items), ITEMS_PATH)
    except Exception as err:
        _LOGGER.error("Error saving items: %s", err)
        raise


def load_index(model_name: str = DEFAULT_MODEL) -> list:
    """
    Load the cached vector index and items from disk.
    
    Args:
        model_name: Name of the sentence transformer model to use
        
    Returns:
        List of loaded items
    """
    global _ITEMS, _INDEX
    
    try:
        _LOGGER.info("Loading voice match index from cache")
        
        # Load items from disk
        _ITEMS = load_json(ITEMS_PATH, [])
        
        if not _ITEMS:
            _LOGGER.warning("No items found in cache")
            return []
        
        # Rebuild the index from items
        build_index(_ITEMS, model_name)
        
        _LOGGER.info("Voice match index loaded successfully with %d items", len(_ITEMS))
        return _ITEMS
        
    except Exception as err:
        _LOGGER.error("Error loading voice match index: %s", err)
        raise


def get_items() -> list:
    """Get the currently loaded items."""
    global _ITEMS
    return _ITEMS or []


def get_index_stats() -> dict:
    """Get statistics about the loaded index."""
    global _INDEX, _ITEMS
    
    return {
        "loaded": _INDEX is not None and _ITEMS is not None,
        "items_count": len(_ITEMS) if _ITEMS else 0,
        "index_type": type(_INDEX).__name__ if _INDEX else None,
    }
