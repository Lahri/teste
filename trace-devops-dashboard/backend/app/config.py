import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Em dev local (docker-compose), aponta pro Oracle do container.
# Em producao, o NTI so precisa trocar estas tres variaveis de ambiente
# (ou o .env) pelas credenciais reais -- nenhum codigo muda.
ORACLE_DSN = os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1")
ORACLE_USER = os.environ.get("ORACLE_USER", "painel_demandas")
ORACLE_PASSWORD = os.environ.get("ORACLE_PASSWORD", "dev_local_only")

# CORS: em dev o front roda em outra porta/origem (file:// ou vite/live-server).
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
