from __future__ import annotations
from dataclasses import dataclass,field
import hashlib,json
from ishworkzero.core.events import EventBus,DomainEvent
from ishworkzero.core.idempotency import IdempotencyStore
from ishworkzero.core.ledger import ActionLedger
from ishworkzero.core.evidence import seal_evidence,verify_evidence
from ishworkzero.core.policy import PolicyEngine
from ishworkzero.core.verification import OutcomeVerificationEngine
from ishworkzero.core.proof import ProofSigner
from ishworkzero.domain.models import *
def _evidence_list(value): return [v if isinstance(v, Evidence) else Evidence.model_validate(v) for v in value]
from ishworkzero.adapters.registry import AdapterRegistry
from ishworkzero.core.outcome import OutcomeContractCompiler
from ishworkzero.core.jobs import JobQueue
from ishworkzero.core.state import transition
from ishworkzero.infra.outbox import SqliteOutbox
@dataclass
class Engine:
    registry:AdapterRegistry
    ledger:ActionLedger
    policy:PolicyEngine=field(default_factory=PolicyEngine)
    events:EventBus=field(default_factory=EventBus)
    idempotency:IdempotencyStore=field(default_factory=IdempotencyStore)
    verifier:OutcomeVerificationEngine|None=None
    signer:ProofSigner=field(default_factory=ProofSigner)
    jobs:JobQueue=field(default_factory=JobQueue)
    outbox:SqliteOutbox|None=None
    def __post_init__(self):
        if self.verifier is None: self.verifier=OutcomeVerificationEngine(self.registry,self.ledger)
        if self.outbox is None: self.outbox=SqliteOutbox('ishworkzero.db')
    def _event(self,case,event,payload): self.events.publish(DomainEvent(event,case.id,case.tenant_id,payload)); self.outbox.enqueue(case.tenant_id,case.id,event,payload)
    def plan(self,case):
        OutcomeContractCompiler.validate(case.outcome)
        if case.status!=CaseStatus.OPEN: raise ValueError('Case is not open')
        if not case.outcome.required and not case.outcome.forbidden: raise ValueError('Outcome contract has no verifiable conditions')
        transition(case.status, CaseStatus.PLANNED); case.status=CaseStatus.PLANNED; case.updated_at=now(); self.ledger.append(case.id,'PLAN',{'goal':case.outcome.goal}); self._event(case,'CASE_PLANNED',{'goal':case.outcome.goal}); return case
    def execute(self,case):
        if case.status!=CaseStatus.PLANNED: raise ValueError('Case must be planned')
        transition(case.status, CaseStatus.EXECUTING); case.status=CaseStatus.EXECUTING; self.ledger.append(case.id,'EXECUTION_STARTED',{'action_count':len(case.actions)})
        try:
            seen=set()
            for action in case.actions:
                if action.idempotency_key in seen: raise ValueError('Duplicate action idempotency key in case')
                seen.add(action.idempotency_key)
                if (action.requires_approval or action.risk_level == 'HIGH') and not action.approved_by: raise PermissionError('Action requires explicit human approval before execution')
                decision=self.policy.authorize(action,action.authorized_by)
                if not decision.allowed: raise PermissionError(decision.reason)
                adapter=self.registry.get(action.adapter)
                fingerprint=hashlib.sha256(json.dumps({'adapter':action.adapter,'operation':action.operation,'parameters':action.parameters},sort_keys=True,default=str).encode()).hexdigest()
                cached=self.idempotency.get(action.idempotency_key)
                if cached:
                    if cached.fingerprint!=fingerprint: raise ValueError('Idempotency key reused with different action')
                    evidence=_evidence_list(cached.result)
                else:
                    job=self.jobs.enqueue(f'action:{case.id}:{action.id}'); evidence=self.jobs.run(job.id,lambda: adapter.execute(action.operation,action.parameters)); self.idempotency.put(action.idempotency_key,fingerprint,evidence)
                sealed=[seal_evidence(e) for e in evidence]; case.evidence.extend(sealed)
                self.ledger.append(case.id,'ACTION',{'action_id':action.id,'adapter':action.adapter,'operation':action.operation,'evidence_ids':[e.id for e in sealed]})
            case.updated_at=now(); self._event(case,'CASE_EXECUTED',{'actions':len(case.actions)}); return case
        except Exception as exc:
            transition(case.status, CaseStatus.FAILED_SAFE); case.status=CaseStatus.FAILED_SAFE; self.ledger.append(case.id,'FAILED_SAFE',{'error':type(exc).__name__,'message':str(exc)}); case.updated_at=now(); self._event(case,'CASE_FAILED_SAFE',{'error':type(exc).__name__}); return case
    def verify(self,case):
        if case.status!=CaseStatus.EXECUTING: raise ValueError('Case is not ready for verification')
        if any(not verify_evidence(e) for e in case.evidence if e.digest): case.status=CaseStatus.FAILED_SAFE; raise ValueError('Evidence integrity failure')
        transition(case.status, CaseStatus.VERIFYING); case.status=CaseStatus.VERIFYING; status,checks,reason=self.verifier.verify(case); case.verification=VerificationResult(status=status,checks=checks,reason=reason)
        target_status=CaseStatus.VERIFIED if status==VerificationStatus.VERIFIED else CaseStatus.FAILED_SAFE; transition(case.status, target_status); case.status=target_status
        self.ledger.append(case.id,'VERIFY',case.verification.model_dump(mode='json')); case.updated_at=now(); self._event(case,'CASE_VERIFIED' if status==VerificationStatus.VERIFIED else 'CASE_UNVERIFIED',{'status':status.value}); return case
    def prove_and_close(self,case):
        if case.status!=CaseStatus.VERIFIED or not case.verification or case.verification.status!=VerificationStatus.VERIFIED: raise ValueError('Only independently verified cases can be proved and closed')
        if not self.ledger.verify(): raise ValueError('Ledger integrity failure')
        if any(not verify_evidence(e) for e in case.evidence): raise ValueError('Evidence integrity failure')
        proof_material={'case_id':case.id,'tenant_id':case.tenant_id,'goal':case.outcome.goal,'verification':case.verification.model_dump(mode='json'),'evidence_digests':sorted(e.digest or '' for e in case.evidence)}
        evidence_digest=hashlib.sha256(json.dumps(proof_material,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest(); signature=self.signer.sign(evidence_digest)
        case.proof=Proof(digest=evidence_digest,signature=signature,public_key=self.signer.public_key_b64)
        proof=self.ledger.append(case.id,'PROOF',{'verification':'VERIFIED','evidence_count':len(case.evidence),'evidence_digest':evidence_digest,'signature':signature,'public_key':case.proof.public_key})
        if not self.signer.verify(evidence_digest,signature): raise ValueError('Proof signature self-verification failed')
        transition(case.status, CaseStatus.CLOSED); self.ledger.append(case.id,'CLOSED',{'proof_hash':proof.hash}); case.status=CaseStatus.CLOSED; case.updated_at=now(); self._event(case,'CASE_CLOSED',{'proof_hash':proof.hash}); return case
