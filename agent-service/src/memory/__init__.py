"""Memory system (memory.md): working / semantic / episodic / procedural layers.

All vectors use the Ollama ``nomic-embed-text`` embedder (768-dim) by default; the
embedding endpoint is user-configurable from the frontend Settings UI and threaded
through per request, falling back to ``config.settings.EMBEDDING_BASE_URL``.
"""
