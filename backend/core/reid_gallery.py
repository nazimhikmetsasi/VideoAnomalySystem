"""Gorunume dayali kisi galerisi (DeepSORT MobileNet embedding)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np

logger = logging.getLogger('video_pipeline')

ROOT = Path(__file__).resolve().parents[2]


def _l2(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(x) + 1e-9)
    return x / n


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(_l2(a), _l2(b)))


class ReIDGallery:
    """
    Kisi gorunum bankasi.
    - Farkli kisiler: benzerlik yetmezse / belirsizse yeni ID
    - Ayni kisi tekrar (kisa kayip / video tekrar): embedding eslesirse ayni ID
    - Uniforma: belirsizlikte en dusuk (en eski) ID tercih edilir; son kisiye yapisma engellenir
    """

    def __init__(self):
        self.min_sim = float(os.getenv('REID_MIN_SIM', 0.82))
        self.min_margin = float(os.getenv('REID_MIN_MARGIN', 0.035))
        self.tie_eps = float(os.getenv('REID_TIE_EPS', 0.03))
        self.ema = float(os.getenv('REID_EMA', 0.12))
        path = os.getenv('REID_GALLERY_PATH', 'data/reid_gallery.npz')
        self.path = Path(path)
        if not self.path.is_absolute():
            self.path = ROOT / self.path
        self._enroll: dict[int, np.ndarray] = {}
        self._emb: dict[int, np.ndarray] = {}
        self._next_id = 1
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = np.load(self.path, allow_pickle=False)
            ids = data['ids'].tolist()
            embs = data['embs']
            enrolls = data['enrolls'] if 'enrolls' in data.files else embs
            for i, sid in enumerate(ids):
                sid = int(sid)
                self._emb[sid] = _l2(embs[i])
                self._enroll[sid] = _l2(enrolls[i])
            if self._emb:
                self._next_id = max(self._emb.keys()) + 1
            logger.info(f"ReID galeri yuklendi | {len(self._emb)} kisi")
        except Exception as e:
            logger.warning(f"ReID galeri okunamadi: {e}")

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self._emb:
                return
            ids = np.array(sorted(self._emb.keys()), dtype=np.int32)
            embs = np.stack([self._emb[i] for i in ids], axis=0)
            enrolls = np.stack(
                [self._enroll.get(i, self._emb[i]) for i in ids],
                axis=0,
            )
            np.savez_compressed(self.path, ids=ids, embs=embs, enrolls=enrolls)
        except Exception as e:
            logger.warning(f"ReID galeri yazilamadi: {e}")

    def update(self, sid: int, feat: np.ndarray | None, persist: bool = False):
        if feat is None:
            return
        feat = _l2(feat)
        if sid not in self._enroll:
            self._enroll[sid] = feat
            self._emb[sid] = feat
        else:
            # Enrollment sabit kalir; EMA sadece yumuşak takip icin
            self._emb[sid] = _l2((1.0 - self.ema) * self._emb[sid] + self.ema * feat)
        if persist:
            self.save()

    def _score(self, feat: np.ndarray, sid: int) -> float:
        """Enrollment agirlikli skor (son kisiye EMA kaymasini azaltir)."""
        en = self._enroll.get(sid)
        em = self._emb.get(sid)
        if en is None and em is None:
            return 0.0
        if en is None:
            return cosine(feat, em)
        if em is None:
            return cosine(feat, en)
        return 0.7 * cosine(feat, en) + 0.3 * cosine(feat, em)

    def match(
        self,
        feat: np.ndarray | None,
        busy_ids: set[int],
        blocked_ids: set[int] | None = None,
    ) -> int | None:
        """
        En iyi eslesme.
        - busy / blocked haric
        - Uniforma belirsizligi: yakin skorlarda en dusuk ID (ilk kayit)
        """
        if feat is None or not self._emb:
            return None
        feat = _l2(feat)
        blocked = blocked_ids or set()
        scores: list[tuple[float, int]] = []
        for sid in self._emb:
            if sid in busy_ids or sid in blocked:
                continue
            scores.append((self._score(feat, sid), sid))
        if not scores:
            return None

        scores.sort(reverse=True)
        best_sim, best_id = scores[0]
        if best_sim < self.min_sim:
            return None

        second = scores[1][0] if len(scores) > 1 else 0.0
        close = [
            sid for sim, sid in scores
            if sim >= self.min_sim and (best_sim - sim) <= self.tie_eps
        ]

        # Birden fazla uniforma benzeri eslesme → en eski (en dusuk) ID
        if len(close) >= 2:
            chosen = min(close)
            logger.info(
                f"ReID belirsiz uniforma | adaylar={sorted(close)} | "
                f"secilen={chosen} | best={best_sim:.3f}"
            )
            return chosen

        if best_sim - second < self.min_margin:
            return None
        return best_id

    def alloc(
        self,
        feat: np.ndarray | None,
        busy_ids: set[int],
        blocked_ids: set[int] | None = None,
    ) -> int:
        matched = self.match(feat, busy_ids, blocked_ids)
        if matched is not None:
            self.update(matched, feat, persist=True)
            logger.info(f"ReID eslesme | ID={matched}")
            return matched
        sid = self._next_id
        self._next_id += 1
        self.update(sid, feat, persist=True)
        logger.info(f"ReID yeni kisi | ID={sid}")
        return sid
