from __future__ import annotations
import os
from datetime import datetime, timezone
from fastapi import APIRouter,HTTPException,Header,Query
from pydantic import BaseModel,Field
from ishworkzero.domain.models import Case,OutcomeContract,Action
from ishworkzero.services.engine import Engine
from ishworkzero.services.store import CaseStore
from ishworkzero.core.proof import ProofSigner
from ishworkzero.core.rate_limit import SlidingWindowRateLimiter
from ishworkzero.core.rbac import RBAC
from ishworkzero.core.proof_bundle import build_proof_bundle
from ishworkzero.data_fabric.models import DataSource,DataSourceKind,DataSourceStatus,ConnectionTestRequest,QueryRequest
from ishworkzero.data_fabric.connectors import inspect_sql,execute_read_query,resolve_connection_ref,PublicSourceManager
from ishworkzero.infra.sqlite_data_fabric import SqliteDataSourceStore

class CreateCase(BaseModel):
    title:str=Field(min_length=1,max_length=240); intent:str=Field(min_length=1,max_length=4000); outcome:OutcomeContract; actions:list[Action]=Field(default_factory=list)

class RegisterDataSource(BaseModel):
    name:str=Field(min_length=1,max_length=160); kind:DataSourceKind; connection_ref:str=Field(min_length=1,max_length=500)

class Api:
    def __init__(self,engine:Engine,store:CaseStore,credentials=None,rbac:RBAC|None=None,limiter:SlidingWindowRateLimiter|None=None,data_sources:SqliteDataSourceStore|None=None,global_sources:PublicSourceManager|None=None):
        self.engine=engine; self.store=store; self.credentials=credentials; self.rbac=rbac; self.limiter=limiter or SlidingWindowRateLimiter(); self.data_sources=data_sources; self.global_sources=global_sources or PublicSourceManager()
    def router(self):
        r=APIRouter()
        def require_tenant(value):
            if not value or not value.strip(): raise HTTPException(400,'X-Tenant-ID header is required')
            return value.strip()
        def auth(api_key,tenant_header,permission=('case','read')):
            requested=require_tenant(tenant_header); rate_key=api_key or requested
            if not self.limiter.allow(rate_key): raise HTTPException(429,'Rate limit exceeded')
            if self.credentials is None or os.getenv('ISHWORKZERO_REQUIRE_AUTH','0')!='1': return requested
            tenant=self.credentials.authenticate(api_key)
            if tenant is None: raise HTTPException(401,'Invalid API credential')
            if requested!=tenant: raise HTTPException(403,'Credential is not authorized for this tenant')
            if self.rbac is not None:
                principal=api_key.split('.',1)[0] if api_key and '.' in api_key else ''
                if not principal or not self.rbac.allowed(tenant,principal,*permission): raise HTTPException(403,'Insufficient permission')
            return tenant
        @r.post('/cases',response_model=Case)
        def create(body:CreateCase,x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')):
            tenant_id=auth(x_api_key,x_tenant_id,('case','create')); case=Case(tenant_id=tenant_id,**body.model_dump()); self.store.put(case); payload={'tenant_id':tenant_id,'title':case.title}; self.engine.ledger.append(case.id,'CASE_CREATED',payload); self.engine.outbox.enqueue(tenant_id,case.id,'CASE_CREATED',payload); return case
        @r.get('/cases',response_model=list[Case])
        def list_cases(limit:int=Query(default=100,ge=1,le=500),offset:int=Query(default=0,ge=0),x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')): return self.store.list(auth(x_api_key,x_tenant_id,('case','read')),limit,offset)
        @r.get('/cases/{case_id}',response_model=Case)
        def get(case_id:str,x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')):
            tenant=auth(x_api_key,x_tenant_id,('case','read'))
            try:return self.store.get(case_id,tenant)
            except KeyError: raise HTTPException(404,'Case not found')
        @r.post('/cases/{case_id}/plan',response_model=Case)
        def plan(case_id:str,x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')): return self._run(case_id,auth(x_api_key,x_tenant_id,('case','plan')),self.engine.plan)
        @r.post('/cases/{case_id}/actions/{action_id}/approve',response_model=Case)
        def approve(case_id:str,action_id:str,x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')):
            tenant=auth(x_api_key,x_tenant_id,('case','approve'))
            try: case,version=self.store.get_with_version(case_id,tenant)
            except KeyError: raise HTTPException(404,'Case not found')
            actor=(x_api_key.split('.',1)[0] if x_api_key and '.' in x_api_key else 'human-approver')
            for action in case.actions:
                if action.id == action_id:
                    if action.approved_by: raise HTTPException(409,'Action is already approved')
                    if actor == action.authorized_by: raise HTTPException(403,'Action author cannot approve the same action')
                    action.approved_by=actor; action.approved_at=datetime.now(timezone.utc); case.updated_at=datetime.now(timezone.utc)
                    self.engine.ledger.append(case.id,'ACTION_APPROVED',{'action_id':action.id,'approved_by':actor}); self.store.put(case,expected_version=version); return case
            raise HTTPException(404,'Action not found')
        @r.post('/cases/{case_id}/execute',response_model=Case)
        def execute(case_id:str,x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')): return self._run(case_id,auth(x_api_key,x_tenant_id,('case','execute')),self.engine.execute)
        @r.post('/cases/{case_id}/verify',response_model=Case)
        def verify(case_id:str,x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')): return self._run(case_id,auth(x_api_key,x_tenant_id,('case','verify')),self.engine.verify)
        @r.post('/cases/{case_id}/close',response_model=Case)
        def close(case_id:str,x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')): return self._run(case_id,auth(x_api_key,x_tenant_id,('case','close')),self.engine.prove_and_close)
        @r.get('/cases/{case_id}/proof')
        def proof(case_id:str,x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')):
            tenant=auth(x_api_key,x_tenant_id,('case','proof'))
            try: case=self.store.get(case_id,tenant)
            except KeyError: raise HTTPException(404,'Case not found')
            if not case.proof: raise HTTPException(404,'Proof not available')
            valid=ProofSigner.verify_public(case.proof.public_key,case.proof.digest,case.proof.signature)
            return {'case_id':case.id,'status':case.status,'proof':case.proof.model_dump(mode='json'),'signature_valid':valid}
        @r.get('/cases/{case_id}/proof-bundle')
        def proof_bundle(case_id:str,x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')):
            tenant=auth(x_api_key,x_tenant_id,('case','proof'))
            try: case=self.store.get(case_id,tenant)
            except KeyError: raise HTTPException(404,'Case not found')
            try: return build_proof_bundle(case)
            except ValueError as exc: raise HTTPException(409,str(exc))
        @r.get('/cases/{case_id}/ledger')
        def ledger(case_id:str,x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')):
            tenant=auth(x_api_key,x_tenant_id,('case','ledger'))
            try: self.store.get(case_id,tenant)
            except KeyError: raise HTTPException(404,'Case not found')
            return {'case_id':case_id,'integrity':self.engine.ledger.verify(),'entries':[e.__dict__ for e in self.engine.ledger.case_entries(case_id)]}
        @r.get('/data-sources',response_model=list[DataSource])
        def data_sources_list(x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')):
            tenant=auth(x_api_key,x_tenant_id,('case','read')); return self.data_sources.list(tenant)
        @r.post('/data-sources/test')
        def data_source_test(body:ConnectionTestRequest,x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')):
            auth(x_api_key,x_tenant_id,('case','read'))
            try:
                schemas,objects,caps=inspect_sql(body.kind,body.connection_url)
                return {'status':'READY','connection_ok':True,'schemas':schemas,'objects':objects[:500],'capabilities':caps}
            except Exception as exc:
                return {'status':'UNAVAILABLE','connection_ok':False,'error':str(exc)[:500]}
        @r.post('/data-sources',response_model=DataSource)
        def data_source_register(body:RegisterDataSource,x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')):
            tenant=auth(x_api_key,x_tenant_id,('case','create'))
            if not body.connection_ref.startswith(('env:','secret:')): raise HTTPException(400,'Only env:NAME or secret:NAME references are allowed; credentials are never stored in source definitions')
            source=DataSource(tenant_id=tenant,name=body.name,kind=body.kind,connection_ref=body.connection_ref)
            try:
                url=resolve_connection_ref(body.connection_ref); schemas,objects,caps=inspect_sql(body.kind,url); source.status=DataSourceStatus.READY; source.capabilities=caps; source.discovered_schemas=schemas; source.discovered_objects=objects[:500]
            except Exception as exc:
                source.status=DataSourceStatus.UNAVAILABLE; source.last_error=str(exc)[:500]
            self.data_sources.put(source); return source
        @r.post('/data-sources/{source_id}/refresh',response_model=DataSource)
        def data_source_refresh(source_id:str,x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')):
            tenant=auth(x_api_key,x_tenant_id,('case','read'))
            try: source=self.data_sources.get(tenant,source_id)
            except KeyError: raise HTTPException(404,'Data source not found')
            try:
                url=resolve_connection_ref(source.connection_ref); schemas,objects,caps=inspect_sql(source.kind,url); source.status=DataSourceStatus.READY; source.capabilities=caps; source.discovered_schemas=schemas; source.discovered_objects=objects[:500]; source.last_error=None
            except Exception as exc: source.status=DataSourceStatus.UNAVAILABLE; source.last_error=str(exc)[:500]
            source.updated_at=datetime.now(timezone.utc); self.data_sources.put(source); return source
        @r.post('/data-sources/{source_id}/query')
        def data_source_query(source_id:str,body:QueryRequest,x_tenant_id:str=Header(default=''),x_api_key:str=Header(default='')):
            tenant=auth(x_api_key,x_tenant_id,('case','read'))
            try: source=self.data_sources.get(tenant,source_id); url=resolve_connection_ref(source.connection_ref)
            except KeyError: raise HTTPException(404,'Data source not found')
            except ValueError as exc: raise HTTPException(409,str(exc))
            try: return {'source_id':source_id,'rows':execute_read_query(source.kind,url,body.query,body.limit),'status':'READY'}
            except Exception as exc: raise HTTPException(409,str(exc)[:500])
        @r.post('/global/intelligence/refresh')
        def global_refresh(): return self.global_sources.refresh()
        @r.get('/global/intelligence')
        def global_intelligence(): return self.global_sources.refresh()
        @r.get('/unresolved-problems')
        def unresolved_problems(): return self.global_sources.refresh().model_dump(mode='json')
        @r.get('/health')
        def health(): return {'status':'ok','ledger_integrity':self.engine.ledger.verify(),'outbox_pending':len(self.engine.outbox.pending())}
        @r.get('/ready')
        def ready():
            if not self.engine.ledger.verify(): raise HTTPException(503,'Ledger integrity failure')
            return {'status':'ready'}
        return r
    def _run(self,case_id,tenant_id,fn):
        try:
            case,version=self.store.get_with_version(case_id,tenant_id); case=fn(case); self.store.put(case,expected_version=version); return case
        except KeyError: raise HTTPException(404,'Case not found')
        except RuntimeError as exc: raise HTTPException(409,str(exc))
        except (ValueError,PermissionError) as exc: raise HTTPException(409,str(exc))
