"""
Validacao extra do SQL de repo.py contra um banco de verdade, ja que este
sandbox nao consegue baixar a imagem do Oracle (bloqueio categorico de
CDN de blob binario -- Docker Hub, GHCR e Quay todos batem em 403 na
politica de rede do ambiente, nao e' um problema do schema/compose).

Usa SQLite (embutido no Python, nao precisa baixar nada) com o MESMO
texto de SQL de app/repo.py, so trocando o que e' sintaxe especifica do
Oracle:
  - SYSTIMESTAMP          -> CURRENT_TIMESTAMP
  - sequence + trigger    -> INTEGER PRIMARY KEY AUTOINCREMENT
  - RETURNING ... INTO    -> cursor.lastrowid
  - bind por **kwargs (estilo oracledb) -> dict (estilo sqlite3)

Isso PEGA bugs reais de coluna/join/alias que o teste mockado
(test_api_smoke.py) nao pega, porque aquele nunca executa o SQL de
verdade. NAO substitui validar contra Oracle (tipos, CHAR CHECK,
trigger de sequence, RETURNING INTO precisam ser confirmados la).

Roda: python test_sql_logic_sqlite.py
"""
import datetime
import sqlite3
import sys

SCHEMA = """
CREATE TABLE itens (
    id_demanda        TEXT PRIMARY KEY,
    analista          TEXT,
    sigla             TEXT,
    descricao         TEXT,
    status            TEXT DEFAULT 'A fazer' NOT NULL,
    previsao_analise  DATE,
    prioridade        INTEGER,
    ciclo             INTEGER,
    atualizado_em     TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE observacoes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    id_demanda        TEXT NOT NULL REFERENCES itens (id_demanda),
    texto             TEXT NOT NULL,
    autor             TEXT NOT NULL,
    criado_em         TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_compromisso    TEXT DEFAULT 'N' NOT NULL CHECK (is_compromisso IN ('S','N')),
    resolvido         TEXT DEFAULT 'N' NOT NULL CHECK (resolvido IN ('S','N')),
    resolvido_em      TIMESTAMP,
    resolvido_por     TEXT
);
"""

_OBS_COLS = """id, id_demanda, texto, autor, criado_em,
               is_compromisso, resolvido, resolvido_em, resolvido_por"""


def rows_as_dicts(cur):
    cols = [c[0].lower() for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def list_itens(conn, analista=None):
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
    return rows_as_dicts(cur)


def update_item(conn, id_demanda, status=None, previsao_analise=None):
    sets, params = [], {"id_demanda": id_demanda}
    if status is not None:
        sets.append("status = :status")
        params["status"] = status
    if previsao_analise is not None:
        sets.append("previsao_analise = :previsao_analise")
        params["previsao_analise"] = previsao_analise
    if not sets:
        return
    sets.append("atualizado_em = CURRENT_TIMESTAMP")
    conn.execute(f"UPDATE itens SET {', '.join(sets)} WHERE id_demanda = :id_demanda", params)
    conn.commit()


def get_item(conn, id_demanda):
    cur = conn.cursor()
    cur.execute(
        """SELECT id_demanda, analista, sigla, descricao, status,
                  previsao_analise, prioridade, ciclo
             FROM itens WHERE id_demanda = :id_demanda""",
        {"id_demanda": id_demanda},
    )
    rows = rows_as_dicts(cur)
    return rows[0] if rows else None


def obs_row(d):
    d["is_compromisso"] = d["is_compromisso"] == "S"
    d["resolvido"] = d["resolvido"] == "S"
    return d


def list_observacoes(conn, id_demanda):
    cur = conn.cursor()
    cur.execute(
        f"SELECT {_OBS_COLS} FROM observacoes WHERE id_demanda = :id_demanda ORDER BY criado_em DESC",
        {"id_demanda": id_demanda},
    )
    return [obs_row(r) for r in rows_as_dicts(cur)]


def create_observacao(conn, id_demanda, texto, autor, is_compromisso):
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
    return obs_row(rows_as_dicts(cur)[0])


def resolver_compromisso(conn, obs_id, autor):
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
    return obs_row(rows_as_dicts(cur)[0])


def list_compromissos_abertos(conn, analista):
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
    rows = rows_as_dicts(cur)
    result = []
    for r in rows:
        item_descricao = r.pop("item_descricao")
        item_sigla = r.pop("item_sigla")
        result.append({"observacao": obs_row(r), "id_demanda": r["id_demanda"],
                        "descricao": item_descricao, "sigla": item_sigla})
    return result


fails = []


def check(name, cond):
    print(("OK  " if cond else "FAIL") + " " + name)
    if not cond:
        fails.append(name)


conn = sqlite3.connect(":memory:")
conn.executescript(SCHEMA)
conn.execute(
    """INSERT INTO itens (id_demanda, analista, sigla, descricao, status, previsao_analise, prioridade, ciclo)
       VALUES ('611742', 'Larissa', 'NEF', 'APIs do BB no Contas a Receber', 'Em testes', '2026-06-12', 1, 1)"""
)
conn.execute(
    """INSERT INTO itens (id_demanda, analista, sigla, descricao, status)
       VALUES ('600100', 'Larissa', 'RH', 'Ajuste de folha de pagamento mensal', 'Em análise')"""
)
conn.execute(
    """INSERT INTO itens (id_demanda, analista, sigla, descricao, status)
       VALUES ('999999', 'Mauricio', 'NEF', 'Item de outro analista', 'Em análise')"""
)
conn.commit()

check("list_itens filtra por analista", len(list_itens(conn, "Larissa")) == 2)
check("list_itens sem filtro traz tudo", len(list_itens(conn, None)) == 3)
check("get_item traz item certo", get_item(conn, "611742")["descricao"] == "APIs do BB no Contas a Receber")
check("get_item retorna None pra id inexistente", get_item(conn, "000000") is None)

update_item(conn, "611742", status="Publicado", previsao_analise=None)
check("update_item so muda status quando previsao=None", get_item(conn, "611742")["status"] == "Publicado")
update_item(conn, "611742", status=None, previsao_analise="2026-09-01")
check("update_item so muda previsao quando status=None", get_item(conn, "611742")["previsao_analise"] == "2026-09-01")

check("list_observacoes vazio antes de criar", list_observacoes(conn, "611742") == [])

obs1 = create_observacao(conn, "611742", "falar com Rosangela sobre retorno", "Larissa", True)
check("create_observacao seta is_compromisso True", obs1["is_compromisso"] is True)
check("create_observacao seta resolvido False", obs1["resolvido"] is False)
obs2 = create_observacao(conn, "600100", "retornar pra Fabiano com status", "Larissa", True)
create_observacao(conn, "611742", "observação comum, sem compromisso", "Larissa", False)

check("list_observacoes traz as 2 do item 611742", len(list_observacoes(conn, "611742")) == 2)

abertos = list_compromissos_abertos(conn, "Larissa")
check("list_compromissos_abertos traz os 2 compromissos abertos", len(abertos) == 2)
check("list_compromissos_abertos traz descricao do item via join", any(a["descricao"] == "APIs do BB no Contas a Receber" for a in abertos))
check("list_compromissos_abertos NAO traz item de outro analista", all(a["descricao"] != "Item de outro analista" for a in abertos))

resolved = resolver_compromisso(conn, obs1["id"], "Larissa")
check("resolver_compromisso marca resolvido True", resolved is not None and resolved["resolvido"] is True)
check("resolver_compromisso seta resolvido_por", resolved["resolvido_por"] == "Larissa")

abertos_depois = list_compromissos_abertos(conn, "Larissa")
check("compromisso some da lista de abertos apos resolver", len(abertos_depois) == 1)
check("o compromisso restante e' o certo (600100)", abertos_depois[0]["id_demanda"] == "600100")

resolved_again = resolver_compromisso(conn, obs1["id"], "Larissa")
check("resolver_compromisso ja resolvido retorna None (nao resolve 2x)", resolved_again is None)

resolved_non_compromisso = resolver_compromisso(conn, 9999, "Larissa")
check("resolver_compromisso id inexistente retorna None", resolved_non_compromisso is None)

print()
if fails:
    print(f"{len(fails)} FALHA(S):", fails)
    sys.exit(1)
print("Todos os checks de SQL passaram (via SQLite -- ainda falta confirmar contra Oracle real).")
