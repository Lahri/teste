import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# "sqlite" (padrao): zero setup, banco em arquivo local, nao precisa de
# Docker nem de conta em nada -- bom pra desenvolver/testar/demonstrar
# agora. "oracle": usa o banco de producao do SESC (ou um Oracle real de
# teste) -- so' trocar DB_BACKEND=oracle + as 3 variaveis ORACLE_* abaixo,
# nenhum outro codigo muda (ver repo.py).
DB_BACKEND = os.environ.get("DB_BACKEND", "sqlite")

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(_BACKEND_DIR, "data", "painel.db"))

ORACLE_DSN = os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1")
ORACLE_USER = os.environ.get("ORACLE_USER", "painel_demandas")
ORACLE_PASSWORD = os.environ.get("ORACLE_PASSWORD", "dev_local_only")

# CORS: em dev o front roda em outra porta/origem (file:// ou vite/live-server).
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
