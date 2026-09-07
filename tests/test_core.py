from ishworkzero.adapters.registry import AdapterRegistry
from ishworkzero.adapters.memory import MemoryAdapter
from ishworkzero.core.ledger import ActionLedger
from ishworkzero.core.policy import PolicyEngine
from ishworkzero.domain.models import *
from ishworkzero.services.engine import Engine

def make_engine(state=None):
    registry=AdapterRegistry(); registry.register(MemoryAdapter(state if state is not None else {})); return Engine(registry,ActionLedger(),PolicyEngine({('test-memory','set')}))

def make_case(path='shipment.status',expected='READY'):
    return Case(tenant_id='t1',title='Shipment',intent='make shipment ready',outcome=OutcomeContract(goal='ready',required=[OutcomeCondition(path=path,operator='equals',expected=expected)]),actions=[Action(adapter='test-memory',operation='set',parameters={'path':path,'value':expected},authorized_by='user:t1')])

def test_full_case_lifecycle():
    e=make_engine(); c=make_case(); e.plan(c); e.execute(c); e.verify(c); e.prove_and_close(c); assert c.status==CaseStatus.CLOSED and c.verification.status==VerificationStatus.VERIFIED and e.ledger.verify()
def test_unknown_cannot_close():
    e=make_engine(); c=Case(tenant_id='t1',title='Unknown',intent='x',outcome=OutcomeContract(goal='x',required=[OutcomeCondition(path='missing.value',operator='equals',expected=1)])); e.plan(c); e.execute(c); e.verify(c); assert c.verification.status==VerificationStatus.UNKNOWN and c.status==CaseStatus.FAILED_SAFE
def test_ledger_detects_tampering():
    e=make_engine(); c=make_case(); e.plan(c); e.ledger.entries[0].payload['goal']='tampered'; assert not e.ledger.verify()
def test_forbidden_condition_fails_safe():
    e=make_engine(); c=Case(tenant_id='t1',title='Forbidden',intent='x',outcome=OutcomeContract(goal='x',forbidden=[OutcomeCondition(path='shipment.cancelled',operator='equals',expected=True)]),actions=[Action(adapter='test-memory',operation='set',parameters={'path':'shipment.cancelled','value':True},authorized_by='user:t1')]); e.plan(c); e.execute(c); e.verify(c); assert c.status==CaseStatus.FAILED_SAFE and c.verification.status==VerificationStatus.UNVERIFIED
def test_no_policy_grant_fails_safe():
    e=Engine(AdapterRegistry(),ActionLedger(),PolicyEngine()); c=make_case(); e.plan(c); e.execute(c); assert c.status==CaseStatus.FAILED_SAFE
def test_duplicate_idempotency_key_fails_safe():
    e=make_engine(); c=make_case(); c.actions.append(c.actions[0].model_copy()); e.plan(c); e.execute(c); assert c.status==CaseStatus.FAILED_SAFE
