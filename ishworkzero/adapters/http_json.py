from __future__ import annotations
import json
from urllib.parse import urljoin, urlparse
from urllib.request import Request,build_opener,HTTPRedirectHandler
from ishworkzero.adapters.base import Adapter
from ishworkzero.domain.models import Evidence,VerificationStatus

class HttpJsonAdapter(Adapter):
    """Production adapter for explicitly configured JSON HTTP systems.

    The base URL is the trust boundary: requests cannot redirect the adapter to
    another host/scheme, credentials are supplied only as configured headers,
    and response bodies are size bounded.
    """
    def __init__(self,name:str,base_url:str,headers:dict[str,str]|None=None,timeout:float=10.0,max_response_bytes:int=2_000_000,max_request_bytes:int=2_000_000):
        parsed=urlparse(base_url)
        if parsed.scheme not in {'https','http'} or not parsed.hostname: raise ValueError('base_url must be HTTP(S) with a hostname')
        if timeout<=0 or timeout>120: raise ValueError('timeout must be >0 and <=120 seconds')
        if max_response_bytes<1024 or max_response_bytes>20_000_000: raise ValueError('max_response_bytes must be between 1024 and 20000000')
        if max_request_bytes<1024 or max_request_bytes>20_000_000: raise ValueError('max_request_bytes must be between 1024 and 20000000')
        self.name=name; self.trust_domain=name; self.base_url=base_url.rstrip('/')+'/'
        self._base_scheme=parsed.scheme; self._base_host=parsed.hostname.lower(); self.headers=dict(headers or {})
        if any(k.lower() in {'host','content-length','transfer-encoding','connection','proxy-authorization'} for k in self.headers): raise ValueError('restricted HTTP header configured')
        if any('\r' in str(k) or '\n' in str(k) or '\r' in str(v) or '\n' in str(v) for k,v in self.headers.items()): raise ValueError('invalid HTTP header characters')
        self.timeout=timeout; self.max_response_bytes=max_response_bytes; self.max_request_bytes=max_request_bytes
        self._opener=build_opener(NoRedirect())

    def _request(self,method,path,payload=None):
        if not isinstance(path,str) or not path or path.startswith('//') or '://' in path: raise ValueError('path must be relative to the configured base URL')
        url=urljoin(self.base_url,path.lstrip('/')); parsed=urlparse(url)
        if parsed.scheme != self._base_scheme or (parsed.hostname or '').lower()!=self._base_host: raise ValueError('request escaped adapter trust boundary')
        data=None; headers={'Accept':'application/json',**self.headers}
        if payload is not None:
            data=json.dumps(payload,separators=(',',':')).encode()
            if len(data)>self.max_request_bytes: raise ValueError('HTTP request payload exceeded configured size limit')
            headers['Content-Type']='application/json'
        req=Request(url,data=data,headers=headers,method=method)
        with self._opener.open(req,timeout=self.timeout) as resp:
            raw=resp.read(self.max_response_bytes+1)
            if len(raw)>self.max_response_bytes: raise RuntimeError('HTTP response exceeded configured size limit')
            return resp.status,json.loads(raw.decode()) if raw else None

    def execute(self,operation,parameters):
        if operation not in {'POST','PUT','PATCH'}: raise ValueError('HTTP JSON execute allows POST, PUT or PATCH only')
        if not isinstance(parameters,dict): raise ValueError('parameters must be an object')
        path=parameters.get('path'); payload=parameters.get('payload',{})
        status,result=self._request(operation,path,payload)
        if status<200 or status>=300: raise RuntimeError(f'HTTP execution returned {status}')
        return [Evidence(source=self.name,kind='execution-response',claim=f'HTTP {operation} {path}',value={'status':status,'body':result})]

    def observe(self,query):
        if not isinstance(query,dict): return VerificationStatus.UNKNOWN,[]
        path=query.get('path')
        try: status,result=self._request('GET',path)
        except Exception as exc: return VerificationStatus.UNKNOWN,[Evidence(source=self.name,kind='observation-error',claim=str(path),value={'error':type(exc).__name__})]
        if 200<=status<300: return VerificationStatus.VERIFIED,[Evidence(source=self.name,kind='observation',claim=path,value=result,independent=True)]
        return VerificationStatus.UNKNOWN,[]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('HTTP redirect rejected by adapter trust boundary')
