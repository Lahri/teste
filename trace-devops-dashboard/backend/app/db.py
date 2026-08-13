import oracledb

from . import config

# Modo "thin" do python-oracledb: fala o protocolo Oracle Net direto em
# Python puro, sem precisar instalar o Oracle Instant Client na maquina
# (nem local nem no servidor do SESC). E' o modo padrao do driver -- so
# muda pra "thick" se algum recurso especifico exigir (nao e' o caso aqui).
_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = oracledb.create_pool(
            user=config.ORACLE_USER,
            password=config.ORACLE_PASSWORD,
            dsn=config.ORACLE_DSN,
            min=1,
            max=8,
            increment=1,
        )
    return _pool


def get_connection():
    return get_pool().acquire()
