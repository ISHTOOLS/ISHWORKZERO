from __future__ import annotations
from dataclasses import dataclass
from threading import RLock
from typing import Any

@dataclass(frozen=True)
class IdempotencyRecord:
    key: str
    fingerprint: str
    result: Any

class IdempotencyStore:
    def __init__(self):
        self._records: dict[str,IdempotencyRecord] = {}
        self._lock=RLock()
    def get(self,key):
        with self._lock: return self._records.get(key)
    def put(self,key,fingerprint,result):
        with self._lock:
            old=self._records.get(key)
            if old and old.fingerprint != fingerprint: raise ValueError("Idempotency key reused with different request")
            if old: return old
            rec=IdempotencyRecord(key,fingerprint,result); self._records[key]=rec; return rec
