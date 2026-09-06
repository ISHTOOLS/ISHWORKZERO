from __future__ import annotations
from typing import Any
from ishworkzero.adapters.base import Adapter
from ishworkzero.domain.models import Evidence,VerificationStatus
class MemoryAdapter(Adapter):
    name='test-memory'
    trust_domain='test-memory'
    def __init__(self,state=None): self.state=state if state is not None else {}
    def execute(self,operation,parameters):
        if operation!='set': raise ValueError('Test memory adapter supports only set')
        parts=parameters['path'].split('.'); cur=self.state
        for p in parts[:-1]: cur=cur.setdefault(p,{})
        cur[parts[-1]]=parameters['value']
        return [Evidence(source=self.name,kind='execution',claim=parameters['path'],value=parameters['value'],independent=False)]
    def observe(self,query):
        cur:Any=self.state
        for p in query['path'].split('.'):
            if not isinstance(cur,dict) or p not in cur: return VerificationStatus.UNKNOWN,[]
            cur=cur[p]
        return VerificationStatus.VERIFIED,[Evidence(source=self.name,kind='observation',claim=query['path'],value=cur,independent=True)]
