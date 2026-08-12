from datetime import datetime
from typing import Optional

from . import db


def _rows_as_dicts(cursor):
    cols = [c[0].lower() for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def list_itens(analista: Optional[str] = None):
    with db.get_connection() as conn:
        cur = conn.cursor()
        if analista:
            cur.execute(
                """SELECT id_demanda, analista, sigla, descricao, status,
                          previsao_analise, prioridade, ciclo
                     FROM itens
                    WHERE analista = :analista
                    ORDER BY id_demanda""",
                analista=analista,
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
        params["previsao_analise"] = previsao_analise
    if not sets:
        return
    sets.append("atualizado_em = SYSTIMESTAMP")
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE itens SET {', '.join(sets)} WHERE id_demanda = :id_demanda",
            params,
        )
        conn.commit()


def get_item(id_demanda: str):
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id_demanda, analista, sigla, descricao, status,
                      previsao_analise, prioridade, ciclo
                 FROM itens WHERE id_demanda = :id_demanda""",
            id_demanda=id_demanda,
        )
        rows = _rows_as_dicts(cur)
        return rows[0] if rows else None


_OBS_COLS = """id, id_demanda, texto, autor, criado_em,
               is_compromisso, resolvido, resolvido_em, resolvido_por"""


def _obs_row_to_dict(row):
    d = row
    d["is_compromisso"] = d["is_compromisso"] == "S"
    d["resolvido"] = d["resolvido"] == "S"
    return d


def list_observacoes(id_demanda: str):
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT {_OBS_COLS} FROM observacoes WHERE id_demanda = :id_demanda ORDER BY criado_em DESC",
            id_demanda=id_demanda,
        )
        return [_obs_row_to_dict(r) for r in _rows_as_dicts(cur)]


def create_observacao(id_demanda: str, texto: str, autor: str, is_compromisso: bool):
    with db.get_connection() as conn:
        cur = conn.cursor()
        out_id = cur.var(int)
        cur.execute(
            """INSERT INTO observacoes (id_demanda, texto, autor, is_compromisso)
               VALUES (:id_demanda, :texto, :autor, :is_compromisso)
               RETURNING id INTO :out_id""",
            id_demanda=id_demanda,
            texto=texto,
            autor=autor,
            is_compromisso="S" if is_compromisso else "N",
            out_id=out_id,
        )
        conn.commit()
        new_id = out_id.getvalue()[0]
        cur.execute(
            f"SELECT {_OBS_COLS} FROM observacoes WHERE id = :id", id=new_id
        )
        return _obs_row_to_dict(_rows_as_dicts(cur)[0])


def resolver_compromisso(obs_id: int, autor: str):
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """UPDATE observacoes
                  SET resolvido = 'S', resolvido_em = SYSTIMESTAMP, resolvido_por = :autor
                WHERE id = :id AND is_compromisso = 'S' AND resolvido = 'N'""",
            id=obs_id,
            autor=autor,
        )
        updated = cur.rowcount
        conn.commit()
        if not updated:
            return None
        cur.execute(f"SELECT {_OBS_COLS} FROM observacoes WHERE id = :id", id=obs_id)
        return _obs_row_to_dict(_rows_as_dicts(cur)[0])


def list_compromissos_abertos(analista: str):
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT {', '.join('o.' + c.strip() for c in _OBS_COLS.split(','))},
                       i.descricao AS item_descricao, i.sigla AS item_sigla
                  FROM observacoes o
                  JOIN itens i ON i.id_demanda = o.id_demanda
                 WHERE o.is_compromisso = 'S' AND o.resolvido = 'N'
                   AND i.analista = :analista
                 ORDER BY o.criado_em DESC""",
            analista=analista,
        )
        rows = _rows_as_dicts(cur)
        result = []
        for r in rows:
            item_descricao = r.pop("item_descricao")
            item_sigla = r.pop("item_sigla")
            obs = _obs_row_to_dict(r)
            result.append({"observacao": obs, "id_demanda": obs["id_demanda"],
                            "descricao": item_descricao, "sigla": item_sigla})
        return result
