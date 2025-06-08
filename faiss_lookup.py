# -*- coding: utf-8 -*-
"""
Created on Tue May 20 12:44:53 2025

@author: tommy
"""

import faiss
import pickle
import tempfile
from io import BytesIO
from sentence_transformers import SentenceTransformer
from cryptography.fernet import Fernet

class EncryptedAnswerRetriever:
    def __init__(self, encrypted_index_path: str, encrypted_meta_path: str, decryption_key: bytes, model_name: str = "all-MiniLM-L6-v2"):
        self.encrypted_index_path = encrypted_index_path
        self.encrypted_meta_path = encrypted_meta_path
        self.decryption_key = decryption_key
        self.model_name = model_name
        self._index = None
        self._metadata = None
        self._embedder = None
        self.cipher = Fernet(self.decryption_key)

    @property
    def index(self):
        if self._index is None:
            with open(self.encrypted_index_path, "rb") as f:
                encrypted = f.read()
                decrypted = self.cipher.decrypt(encrypted)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".index") as tmp:
                    tmp.write(decrypted)
                    tmp.flush()
                    self._index = faiss.read_index(tmp.name)
        return self._index

    @property
    def metadata(self):
        if self._metadata is None:
            with open(self.encrypted_meta_path, "rb") as f:
                decrypted = self.cipher.decrypt(f.read())
                self._metadata = pickle.load(BytesIO(decrypted))
        return self._metadata

    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = SentenceTransformer(self.model_name)
        return self._embedder

    def get_nearest_neighbors(self, query: str, n: int = 3):
        query_vec = self.embedder.encode([query], convert_to_numpy=True)
        D, I = self.index.search(query_vec, k=n)
        return [self.metadata[i] for i in I[0]]

