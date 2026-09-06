from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime,timezone
from threading import RLock
from typing import Any,Callable

@dataclass(frozen=True)
class DomainEvent:
    type:str
    aggregate_id:str
    tenant_id:str
    payload:dict[str,Any]
    occurred_at:str=field(default_factory=lambda:datetime.now(timezone.utc).isoformat())

class EventBus:
    def __init__(self): self._subs:dict[str,list[Callable[[DomainEvent],None]]]={}; self._lock=RLock()
    def subscribe(self,event_type,handler):
        with self._lock: self._subs.setdefault(event_type,[]).append(handler)
    def publish(self,event):
        with self._lock: handlers=tuple(self._subs.get(event.type,()))+tuple(self._subs.get('*',()))
        for handler in handlers: handler(event)
