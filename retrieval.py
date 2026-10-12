"""Local lexical embeddings for the small Chinese story corpus (no API calls)."""

import hashlib
import math
import re
from collections import Counter

from langchain_core.embeddings import Embeddings


class StoryEmbeddings(Embeddings):
    dimensions = 512

    def embed_query(self, text):
        parts = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text.lower())
        terms = []
        for part in parts:
            if re.fullmatch(r"[\u4e00-\u9fff]+", part):
                terms.extend(part)
                terms.extend(part[i : i + 2] for i in range(len(part) - 1))
            else:
                terms.append(part)
        vector = [0.0] * self.dimensions
        for term, count in Counter(terms).items():
            index = (
                int.from_bytes(hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest(), "big") % self.dimensions
            )
            vector[index] += 1 + math.log(count)
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]
