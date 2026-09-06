from __future__ import annotations
from abc import ABC,abstractmethod
from typing import Any
from ishworkzero.domain.models import Evidence,VerificationStatus

class Adapter(ABC):
    name:str
    trust_domain:str
    @abstractmethod
    def execute(self,operation:str,parameters:dict[str,Any])->list[Evidence]: ...
    @abstractmethod
    def observe(self,query:dict[str,Any])->tuple[VerificationStatus,list[Evidence]]: ...
