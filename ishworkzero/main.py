import os
from fastapi import FastAPI
from ishworkzero.adapters.registry import AdapterRegistry
from ishworkzero.infra.sqlite_ledger import SqliteLedger
from ishworkzero.core.policy import PolicyEngine
from ishworkzero.services.engine import Engine
from ishworkzero.infra.sqlite_store import SqliteCaseStore
from ishworkzero.infra.sqlite_credentials import SqliteCredentialStore
from ishworkzero.api.routes import Api
from ishworkzero.core.rbac import Permission
from ishworkzero.infra.sqlite_rbac import SqliteRBAC
from ishworkzero.core.rate_limit import SlidingWindowRateLimiter
from ishworkzero.infra.outbox import SqliteOutbox
from ishworkzero.infra.config import load_http_adapters
from ishworkzero.infra.sqlite_idempotency import SqliteIdempotencyStore
from ishworkzero.core.metrics import Metrics
from ishworkzero.core.proof import ProofSigner
from ishworkzero.infra.sqlite_jobs import SqliteJobQueue
from ishworkzero.infra.sqlite_data_fabric import SqliteDataSourceStore
from ishworkzero.data_fabric.connectors import PublicSourceManager
from uuid import uuid4
VERSION='0.5.0'
def create_app(store_path=None):
    store_path=store_path or os.getenv('ISHWORKZERO_DB','ishworkzero.db')
    registry=AdapterRegistry(); load_http_adapters(registry); ledger=SqliteLedger(store_path); policy=PolicyEngine(); store=SqliteCaseStore(store_path); credentials=SqliteCredentialStore(store_path)
    rbac=SqliteRBAC(store_path)
    operator_permissions={Permission('case','create'),Permission('case','read'),Permission('case','plan'),Permission('case','execute'),Permission('case','verify'),Permission('case','close'),Permission('case','proof'),Permission('case','ledger'),Permission('case','approve')}
    rbac.define_role('operator',operator_permissions)
    bootstrap=os.getenv('ISHWORKZERO_BOOTSTRAP_OPERATOR','')
    if bootstrap:
        for item in bootstrap.split(','):
            if ':' not in item: continue
            tenant,principal=item.split(':',1)
            if tenant and principal: rbac.assign(tenant,principal,'operator')
    proof_key_path=os.getenv('ISHWORKZERO_PROOF_KEY_PATH') or str(__import__('pathlib').Path(store_path).with_suffix('.proof.key'))
    jobs=SqliteJobQueue(store_path); jobs.recover_running()
    engine=Engine(registry,ledger,policy,idempotency=SqliteIdempotencyStore(store_path),outbox=SqliteOutbox(store_path),signer=ProofSigner(key_path=proof_key_path),jobs=jobs)
    app=FastAPI(title='ISHWORKZERO',version=VERSION,description='AI outcome assurance, real-data fabric, global intelligence and cryptographic proof infrastructure')
    metrics=Metrics()
    data_sources=SqliteDataSourceStore(store_path); global_sources=PublicSourceManager()
    @app.get('/api/v1/metrics')
    def metrics_endpoint(): return metrics.snapshot()
    @app.middleware('http')
    async def request_context(request,call_next):
        request_id=request.headers.get('X-Request-ID') or str(uuid4()); metrics.inc('http.requests')
        try: response=await call_next(request)
        except Exception: metrics.inc('http.errors'); raise
        response.headers['X-Request-ID']=request_id; response.headers['X-Content-Type-Options']='nosniff'; response.headers['X-Frame-Options']='DENY'; response.headers['Referrer-Policy']='no-referrer'; return response
    app.include_router(Api(engine,store,credentials,rbac,SlidingWindowRateLimiter(),data_sources,global_sources).router(),prefix='/api/v1')
    app.state.engine=engine; app.state.store=store; app.state.credentials=credentials; app.state.rbac=rbac; app.state.metrics=metrics; app.state.data_sources=data_sources; app.state.global_sources=global_sources
    return app
app=create_app(); __version__=VERSION
