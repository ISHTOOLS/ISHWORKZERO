from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from threading import RLock
from uuid import uuid4
from datetime import datetime,timezone

class JobStatus(str,Enum): QUEUED='QUEUED'; RUNNING='RUNNING'; SUCCEEDED='SUCCEEDED'; FAILED='FAILED'
@dataclass
class Job:
    id:str; name:str; status:JobStatus=JobStatus.QUEUED; attempts:int=0; error:str|None=None; created_at:str=''; updated_at:str=''
class JobQueue:
    def __init__(self): self._jobs={}; self._lock=RLock()
    def enqueue(self,name):
        now=datetime.now(timezone.utc).isoformat(); j=Job(str(uuid4()),name,created_at=now,updated_at=now)
        with self._lock: self._jobs[j.id]=j
        return j
    def run(self,job_id,fn):
        with self._lock: j=self._jobs[job_id]; j.status=JobStatus.RUNNING; j.attempts+=1
        try: result=fn(); j.status=JobStatus.SUCCEEDED; return result
        except Exception as exc: j.status=JobStatus.FAILED; j.error=str(exc); raise
        finally: j.updated_at=datetime.now(timezone.utc).isoformat()
