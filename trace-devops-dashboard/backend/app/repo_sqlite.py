"""
Implementacao SQLite do mesmo contrato de repo_oracle.py -- mesma
assinatura de funcoes, mesmo formato de retorno (dicts com os mesmos
campos). Existe pra zero-setup local: nao precisa de Docker, conta na
nuvem nem instalar nada (sqlite3 e' modulo padrao do Python). Uso
pretendido: desenvolvimento e demonstracao ate' o Oracle de producao (ou
um ambiente de teste real) estar disponivel -- ver README, secao
"Backend Oracle", para o que ainda falta confirmar especificamente contra
Oracle antes de ir pra producao (RETURNING INTO, trigger de sequence,
tipos exatos).
"""
import datetime
import os
import sqlite3
from typing import Optional

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS itens (
    id_demanda        TEXT PRIMARY KEY,
    analista          TEXT,
    sigla             TEXT,
    descricao         TEXT,
    status            TEXT DEFAULT 'A fazer' NOT NULL,
    previsao_analise  TEXT,
    prioridade        INTEGER,
    ciclo             INTEGER,
    atualizado_em     TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS observacoes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    id_demanda        TEXT NOT NULL REFERENCES itens (id_demanda),
    texto             TEXT NOT NULL,
    autor             TEXT NOT NULL,
    criado_em         TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_compromisso    TEXT DEFAULT 'N' NOT NULL CHECK (is_compromisso IN ('S','N')),
    resolvido         TEXT DEFAULT 'N' NOT NULL CHECK (resolvido IN ('S','N')),
    resolvido_em      TEXT,
    resolvido_por     TEXT
);

CREATE INDEX IF NOT EXISTS idx_observacoes_item ON observacoes (id_demanda);
CREATE INDEX IF NOT EXISTS idx_itens_analista ON itens (analista);
"""


def _connect():
    os.makedirs(os.path.dirname(config.SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(config.SQLITE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _iso(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def _rows_as_dicts(cur):
    return [dict(row) for row in cur.fetchall()]


def _obs_row(d):
    d["is_compromisso"] = d["is_compromisso"] == "S"
    d["resolvido"] = d["resolvido"] == "S"
    return d


_OBS_COLS = """id, id_demanda, texto, autor, criado_em,
               is_compromisso, resolvido, resolvido_em, resolvido_por"""


def list_itens(analista: Optional[str] = None):
    with _connect() as conn:
        cur = conn.cursor()
        if analista:
            cur.execute(
                """SELECT id_demanda, analista, sigla, descricao, status,
                          previsao_analise, prioridade, ciclo
                     FROM itens
                    WHERE analista = :analista
                    ORDER BY id_demanda""",
                {"analista": analista},
            )
        else:
            cur.execute(
                """SELECT id_demanda, analista, sigla, descricao, status,
                          previsao_analise, prioridade, ciclo
                     FROM itens
                    ORDER BY id_demanda"""
            )
        return _rows_as_dicts(cur)


def update_item(id_demanda: str, status: Optional[str], previsao_analise):
    sets, params = [], {"id_demanda": id_demanda}
    if status is not None:
        sets.append("status = :status")
        params["status"] = status
    if previsao_analise is not None:
        sets.append("previsao_analise = :previsao_analise")
        params["previsao_analise"] = _iso(previsao_analise)
    if not sets:
        return
    sets.append("atualizado_em = CURRENT_TIMESTAMP")
    with _connect() as conn:
        conn.execute(f"UPDATE itens SET {', '.join(sets)} WHERE id_demanda = :id_demanda", params)
        conn.commit()


def get_item(id_demanda: str):
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id_demanda, analista, sigla, descricao, status,
                      previsao_analise, prioridade, ciclo
                 FROM itens WHERE id_demanda = :id_demanda""",
            {"id_demanda": id_demanda},
        )
        rows = _rows_as_dicts(cur)
        return rows[0] if rows else None


def list_observacoes(id_demanda: str):
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT {_OBS_COLS} FROM observacoes WHERE id_demanda = :id_demanda ORDER BY criado_em DESC",
            {"id_demanda": id_demanda},
        )
        return [_obs_row(r) for r in _rows_as_dicts(cur)]


def create_observacao(id_demanda: str, texto: str, autor: str, is_compromisso: bool):
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO observacoes (id_demanda, texto, autor, is_compromisso)
               VALUES (:id_demanda, :texto, :autor, :is_compromisso)""",
            {"id_demanda": id_demanda, "texto": texto, "autor": autor,
             "is_compromisso": "S" if is_compromisso else "N"},
        )
        new_id = cur.lastrowid
        conn.commit()
        cur.execute(f"SELECT {_OBS_COLS} FROM observacoes WHERE id = :id", {"id": new_id})
        return _obs_row(_rows_as_dicts(cur)[0])


def resolver_compromisso(obs_id: int, autor: str):
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """UPDATE observacoes
                  SET resolvido = 'S', resolvido_em = CURRENT_TIMESTAMP, resolvido_por = :autor
                WHERE id = :id AND is_compromisso = 'S' AND resolvido = 'N'""",
            {"id": obs_id, "autor": autor},
        )
        updated = cur.rowcount
        conn.commit()
        if not updated:
            return None
        cur.execute(f"SELECT {_OBS_COLS} FROM observacoes WHERE id = :id", {"id": obs_id})
        return _obs_row(_rows_as_dicts(cur)[0])


def list_compromissos_abertos(analista: str):
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT {', '.join('o.' + c.strip() for c in _OBS_COLS.split(','))},
                       i.descricao AS item_descricao, i.sigla AS item_sigla
                  FROM observacoes o
                  JOIN itens i ON i.id_demanda = o.id_demanda
                 WHERE o.is_compromisso = 'S' AND o.resolvido = 'N'
                   AND i.analista = :analista
                 ORDER BY o.criado_em DESC""",
            {"analista": analista},
        )
        rows = _rows_as_dicts(cur)
        result = []
        for r in rows:
            item_descricao = r.pop("item_descricao")
            item_sigla = r.pop("item_sigla")
            obs = _obs_row(r)
            result.append({"observacao": obs, "id_demanda": obs["id_demanda"],
                            "descricao": item_descricao, "sigla": item_sigla})
        return result
