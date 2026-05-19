import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from .storage import save_json, load_json
import os

MODEL = SentenceTransformer("all-MiniLM-L6-v2")

INDEX = None
ITEMS = None

INDEX_PATH = "/config/voice_match/index.faiss"
ITEMS_PATH = "/config/voice_match/items.json"


def build_index(items):
    global INDEX, ITEMS

    texts = [i["text"] for i in items]
    vecs = MODEL.encode(texts, normalize_embeddings=True)
    vecs = np.array(vecs).astype("float32")

    INDEX = faiss.IndexFlatIP(vecs.shape[1])
    INDEX.add(vecs)
    ITEMS = items

    save(items)


def search(query):
    q = MODEL.encode([query], normalize_embeddings=True)
    q = np.array(q).astype("float32")

    scores, idx = INDEX.search(q, 1)
    i = int(idx[0][0])

    return ITEMS[i], float(scores[0][0])


def save(items):
    save_json(ITEMS_PATH, items)


def load():
    global ITEMS
    ITEMS = load_json(ITEMS_PATH, [])
    return ITEMS
