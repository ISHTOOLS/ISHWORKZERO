from fastapi.testclient import TestClient
from ishworkzero.main import create_app

def test_api_full_lifecycle(tmp_path):
    app=create_app(str(tmp_path/'test.db')); client=TestClient(app); h={'X-Tenant-ID':'api-test'}
    assert client.get('/api/v1/health').json()['status']=='ok'
    body={'title':'Shipment','intent':'ready','outcome':{'goal':'ready','required':[{'path':'shipment.status','operator':'equals','expected':'READY'}]},'actions':[]}
    r=client.post('/api/v1/cases',json=body,headers=h); assert r.status_code==200
    cid=r.json()['id']; assert client.get(f'/api/v1/cases/{cid}',headers=h).status_code==200
    assert client.get(f'/api/v1/cases/{cid}',headers={'X-Tenant-ID':'other'}).status_code==404

def test_api_requires_tenant(tmp_path):
    client=TestClient(create_app(str(tmp_path/'test.db'))); r=client.get('/api/v1/cases'); assert r.status_code==400

def test_api_human_approval_for_high_risk_action(tmp_path):
    from ishworkzero.adapters.memory import MemoryAdapter
    from ishworkzero.domain.models import Action
    app=create_app(str(tmp_path/'approval.db')); app.state.engine.registry.register(MemoryAdapter())
    h={'X-Tenant-ID':'t'}
    body={'title':'Risky','intent':'change','outcome':{'goal':'ready','required':[{'path':'x','operator':'equals','expected':1}]},'actions':[{'adapter':'test-memory','operation':'set','parameters':{'path':'x','value':1},'authorized_by':'agent','risk_level':'HIGH'}]}
    r=TestClient(app).post('/api/v1/cases',json=body,headers=h); assert r.status_code==200
    cid=r.json()['id']; aid=r.json()['actions'][0]['id']
    assert TestClient(app).post(f'/api/v1/cases/{cid}/plan',headers=h).status_code==200
    r=TestClient(app).post(f'/api/v1/cases/{cid}/actions/{aid}/approve',headers=h); assert r.status_code==200
