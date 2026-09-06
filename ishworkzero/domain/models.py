from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator


def now() -> datetime:
    return datetime.now(timezone.utc)

class CaseStatus(str, Enum):
    OPEN='OPEN'; PLANNED='PLANNED'; EXECUTING='EXECUTING'; VERIFYING='VERIFYING'; VERIFIED='VERIFIED'; PROVED='PROVED'; CLOSED='CLOSED'; FAILED_SAFE='FAILED_SAFE'

class VerificationStatus(str, Enum):
    VERIFIED='VERIFIED'; UNVERIFIED='UNVERIFIED'; UNKNOWN='UNKNOWN'; FAILED_SAFE='FAILED_SAFE'

class Evidence(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(default_factory=lambda: str(uuid4()))
    source: str
    kind: str
    claim: str
    value: Any
    observed_at: datetime = Field(default_factory=now)
    digest: str | None = None
    independent: bool = False
    @field_validator('source','kind','claim')
    @classmethod
    def nonempty(cls,v:str)->str:
        if not v.strip(): raise ValueError('must not be empty')
        return v

class OutcomeCondition(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str
    operator: Literal['equals','not_equals','greater_than','less_than','greater_or_equal','less_or_equal','contains','not_contains','exists']
    expected: Any
    verifier: str | None = None
    min_independent_sources: int | None = Field(default=None, ge=1)
    @field_validator('path','operator')
    @classmethod
    def nonempty(cls,v:str)->str:
        if not v.strip(): raise ValueError('must not be empty')
        return v

class OutcomeContract(BaseModel):
    model_config = ConfigDict(extra='forbid')
    goal: str
    required: list[OutcomeCondition] = Field(default_factory=list)
    forbidden: list[OutcomeCondition] = Field(default_factory=list)
    min_independent_sources: int = Field(default=1, ge=1)

class Action(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(default_factory=lambda: str(uuid4()))
    adapter: str
    operation: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    authorized_by: str
    risk_level: Literal['LOW','MEDIUM','HIGH'] = 'LOW'
    requires_approval: bool = False
    approved_by: str | None = None
    approved_at: datetime | None = None
    idempotency_key: str = Field(default_factory=lambda: str(uuid4()))

class VerificationResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: VerificationStatus
    checks: list[dict[str, Any]]
    reason: str | None = None
    verified_at: datetime = Field(default_factory=now)

class Proof(BaseModel):
    model_config = ConfigDict(extra='forbid')
    algorithm: Literal['Ed25519'] = 'Ed25519'
    digest: str
    signature: str
    public_key: str
    created_at: datetime = Field(default_factory=now)

class Case(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    title: str
    intent: str
    status: CaseStatus = CaseStatus.OPEN
    outcome: OutcomeContract
    actions: list[Action] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    verification: VerificationResult | None = None
    proof: Proof | None = None
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
