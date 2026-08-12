-- Usado SOMENTE pelo docker-compose local (montado em
-- /container-entrypoint-initdb.d/, que a imagem gvenzl/oracle-free roda
-- automaticamente conectada como SYS no banco raiz -- ver
-- https://github.com/gvenzl/oci-oracle-free, secao "Initialization
-- scripts": "If you want to initialize your application schema, you
-- first have to connect to that schema inside your initialization
-- script." Por isso este arquivo so' faz o CONNECT e inclui o schema.sql
-- de verdade -- schema.sql em si fica limpo (sem CONNECT/credenciais),
-- porque em producao o NTI vai rodar ele ja conectado no schema certo.
CONNECT painel_demandas/dev_local_only@localhost:1521/FREEPDB1
@/opt/schema/schema.sql
