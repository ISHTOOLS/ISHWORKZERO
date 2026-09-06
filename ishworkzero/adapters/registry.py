from ishworkzero.adapters.base import Adapter
class AdapterRegistry:
    def __init__(self): self._items={}
    def register(self,adapter:Adapter):
        if not getattr(adapter,'name',None): raise ValueError('Adapter name required')
        self._items[adapter.name]=adapter
    def get(self,name):
        if name not in self._items: raise KeyError(f'Adapter not configured: {name}')
        return self._items[name]
    def all(self): return tuple(self._items.values())
