"""Keyword search with BM25, stored as a sparse matrix so it stays fast and small in memory."""
import json
import re
from array import array
from collections import Counter
import numpy as np
import snowballstemmer
from scipy import sparse

TOKENIZER = "words+snowball-english-1"     # part of the saved index's key: change it when tokens() changes
_stemmer = snowballstemmer.stemmer("english")
_stems = {}


def stem(word):
    """overrule / overruled / overruling -> 'overrul' (without it, 'overrule' in a question never
    matched 'overruled' in Loper Bright). Cached: the same words come back millions of times."""
    s = _stems.get(word)
    if s is None:
        s = _stems[word] = _stemmer.stemWord(word)
    return s


def tokens(text):
    return [stem(w) for w in re.findall(r"[a-z0-9§]+", (text or "").lower())]


class BM25:
    def __init__(self, texts, k1=1.5, b=0.75):
        # (chunk, word, count) triples in compact arrays (4 bytes each): Python lists would need
        # about 1 GB for our 104,904 chunks / 27.5 million words.
        self.vocab, rows, cols, counts = {}, array("i"), array("i"), array("f")
        lengths = np.zeros(len(texts), dtype=np.float32)
        for d, text in enumerate(texts):
            c = Counter(tokens(text))
            lengths[d] = sum(c.values())
            for term, tf in c.items():
                rows.append(d)
                cols.append(self.vocab.setdefault(term, len(self.vocab)))
                counts.append(tf)
        rows, cols = np.frombuffer(rows, dtype=np.int32), np.frombuffer(cols, dtype=np.int32)
        tf = np.frombuffer(counts, dtype=np.float32)
        df = np.bincount(cols, minlength=len(self.vocab))
        n = max(len(texts), 1)
        idf = np.log((n - df + 0.5) / (df + 0.5) + 1.0).astype(np.float32)
        avgdl = lengths.mean() if len(texts) else 1.0
        # BM25 weight of each (chunk, word): idf * tf*(k1+1) / (tf + k1*(1-b+b*len/avgdl))
        norm = k1 * (1 - b + b * lengths[rows] / avgdl)
        weights = idf[cols] * tf * (k1 + 1) / (tf + norm)
        self.matrix = sparse.csc_matrix((weights, (rows, cols)),
                                        shape=(len(texts), len(self.vocab)), dtype=np.float32)

    def scores(self, query):
        ids = [self.vocab[t] for t in set(tokens(query)) if t in self.vocab]
        if not ids:
            return np.zeros(self.matrix.shape[0], dtype=np.float32)
        return np.asarray(self.matrix[:, ids].sum(axis=1)).ravel()

    def save(self, path, key):
        """Save the matrix and the vocabulary; `key` identifies the index they were built from."""
        sparse.save_npz(f"{path}.npz", self.matrix)
        json.dump({"key": key, "vocab": self.vocab}, open(f"{path}.json", "w"))

    @classmethod
    def load(cls, path, key):
        """The saved BM25 if it was built from the same index (same key), otherwise None."""
        try:
            meta = json.load(open(f"{path}.json"))
            if meta["key"] != key:
                return None
            obj = cls.__new__(cls)
            obj.vocab, obj.matrix = meta["vocab"], sparse.load_npz(f"{path}.npz").tocsc()
            return obj
        except (OSError, ValueError, KeyError):
            return None
