from __future__ import annotations
import hashlib,json
from typing import Any
from ishworkzero.domain.models import Evidence

def evidence_digest(evidence:Evidence)->str:
    body=evidence.model_dump(mode='json'); body.pop('digest',None)
    return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def seal_evidence(evidence:Evidence)->Evidence:
    evidence.digest=evidence_digest(evidence); return evidence

def verify_evidence(evidence:Evidence)->bool:
    return bool(evidence.digest) and evidence.digest==evidence_digest(evidence)
