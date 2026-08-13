"""
Dispatcher: escolhe a implementacao (SQLite pra dev local sem setup, ou
Oracle pra producao) conforme DB_BACKEND. Mesma assinatura de funcoes nos
dois lados -- ver repo_sqlite.py e repo_oracle.py.
"""
from . import config

if config.DB_BACKEND == "oracle":
    from . import repo_oracle as _impl
else:
    from . import repo_sqlite as _impl

list_itens = _impl.list_itens
get_item = _impl.get_item
update_item = _impl.update_item
list_observacoes = _impl.list_observacoes
create_observacao = _impl.create_observacao
resolver_compromisso = _impl.resolver_compromisso
list_compromissos_abertos = _impl.list_compromissos_abertos
