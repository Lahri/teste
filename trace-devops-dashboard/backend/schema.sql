-- Schema Oracle do painel de demandas.
-- Substitui as duas tabelas do Airtable (Itens / Observacoes) por tabelas
-- reais, permitindo campos proprios pra status de compromisso (o painel em
-- cima do Airtable tinha que simular isso com um prefixo de texto porque
-- nao dava pra alterar o schema do Airtable nesta sessao).
--
-- Rodar uma vez contra o schema/usuario que o NTI disponibilizar. Em dev
-- local, o docker-compose.yml ja roda este script automaticamente na
-- primeira subida do container Oracle.

CREATE TABLE itens (
    id_demanda        VARCHAR2(20)   NOT NULL PRIMARY KEY, -- id do Trace/Azure DevOps (ex: "611742")
    analista          VARCHAR2(120),
    sigla             VARCHAR2(30),
    descricao         VARCHAR2(4000),
    status            VARCHAR2(60)   DEFAULT 'A fazer' NOT NULL,
    previsao_analise  DATE,
    prioridade        NUMBER,
    ciclo             NUMBER,
    atualizado_em     TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL
);

CREATE SEQUENCE seq_observacoes START WITH 1 INCREMENT BY 1;

CREATE TABLE observacoes (
    id                NUMBER         NOT NULL PRIMARY KEY,
    id_demanda        VARCHAR2(20)   NOT NULL,
    texto             VARCHAR2(4000) NOT NULL,
    autor             VARCHAR2(120)  NOT NULL,
    criado_em         TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    -- compromisso: campo real, sem precisar de convencao de texto
    is_compromisso    CHAR(1)        DEFAULT 'N' NOT NULL CHECK (is_compromisso IN ('S','N')),
    resolvido         CHAR(1)        DEFAULT 'N' NOT NULL CHECK (resolvido IN ('S','N')),
    resolvido_em      TIMESTAMP,
    resolvido_por     VARCHAR2(120),
    CONSTRAINT fk_observacoes_item FOREIGN KEY (id_demanda) REFERENCES itens (id_demanda)
);

CREATE OR REPLACE TRIGGER trg_observacoes_id
BEFORE INSERT ON observacoes
FOR EACH ROW
WHEN (NEW.id IS NULL)
BEGIN
    :NEW.id := seq_observacoes.NEXTVAL;
END;
/

CREATE INDEX idx_observacoes_item ON observacoes (id_demanda);
CREATE INDEX idx_itens_analista ON itens (analista);

-- compromissos em aberto de um analista, sem esperar o front-end agregar:
-- SELECT o.*, i.descricao, i.sigla
--   FROM observacoes o JOIN itens i ON i.id_demanda = o.id_demanda
--  WHERE o.is_compromisso = 'S' AND o.resolvido = 'N' AND i.analista = :analista
--  ORDER BY o.criado_em DESC;
