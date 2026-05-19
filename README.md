# MASS Voice Match

A Home Assistant integration that provides semantic voice search for your Music Assistant library.

## Features
- **Semantic Search**: Use vector embeddings (FAISS + Sentence Transformers) to match garbled STT to your actual music.
- **Fuzzy Fallback**: Works on any environment (including those that can't run Torch) using rapidfuzz.
- **Conversation Agent**: Register as a primary voice handler for "Play [Music]" commands.
- **UI Configurable**: Easy setup via Home Assistant integrations page.

## Installation
1. Add this repository as a Custom Repository in HACS.
2. Search for "MASS Voice Match" and download.
3. Restart Home Assistant.
4. Go to Settings -> Devices & Services -> Add Integration -> MASS Voice Match.

### Advanced (Vector) Search
To use the advanced vector search features, your system must be able to install `sentence-transformers` and `faiss-cpu`. If your system (e.g. some Home Assistant OS versions or exotic CPUs) cannot install these, the integration will automatically fall back to standard fuzzy matching, which is still very effective.

If you are a power user and want to force-install dependencies:
```bash
pip install sentence-transformers faiss-cpu
```
(Note: This is usually handled automatically by Home Assistant if your environment is compatible.)

## Configuration
- **Music Assistant Instance**: Select your MASS integration.
- **Default Media Player**: The player where music will start when using voice commands.
- **Matching Threshold**: How strict the match should be (0.0 to 1.0).
- **Model**: The Sentence Transformer model to use (default: `all-MiniLM-L6-v2`).
