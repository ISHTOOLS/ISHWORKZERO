from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from dataclasses import dataclass,field
from typing import Any

def canonical(value: Any)->str:
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str)

@dataclass
class LedgerEntry:
    sequence:int; case_id:str; event:str; payload:dict[str,Any]; previous_hash:str
    timestamp:str=field(default_factory=lambda:datetime.now(timezone.utc).isoformat())
    hash:str=''
    def seal(self):
        body={'sequence':self.sequence,'case_id':self.case_id,'event':self.event,'payload':self.payload,'previous_hash':self.previous_hash,'timestamp':self.timestamp}
        self.hash=hashlib.sha256(canonical(body).encode()).hexdigest(); return self

class ActionLedger:
    def __init__(self): self.entries=[]
    def append(self,case_id,event,payload):
        previous=self.entries[-1].hash if self.entries else 'GENESIS'
        return self._append(LedgerEntry(len(self.entries)+1,case_id,event,payload,previous).seal())
    def _append(self,e): self.entries.append(e); return e
    def verify(self):
        previous='GENESIS'
        for i,e in enumerate(self.entries,1):
            if e.sequence!=i or e.previous_hash!=previous: return False
            expected=LedgerEntry(e.sequence,e.case_id,e.event,e.payload,e.previous_hash,e.timestamp).seal().hash
            if expected!=e.hash: return False
            previous=e.hash
        return True
    def case_entries(self,case_id): return [e for e in self.entries if e.case_id==case_id]
