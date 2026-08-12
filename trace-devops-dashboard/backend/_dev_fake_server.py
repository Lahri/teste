"""Servidor de desenvolvimento com repo fake, so' pra testar o front-end
real (fetch) contra um FastAPI real, sem precisar de Oracle."""
import datetime

import uvicorn

from app import repo

_ITENS = {
    "611742": {"id_demanda": "611742", "analista": "Larissa", "sigla": "NEF",
               "descricao": "APIs do BB no Contas a Receber", "status": "Em testes",
               "previsao_analise": datetime.date(2026, 6, 12), "prioridade": 1, "ciclo": 1},
    "600100": {"id_demanda": "600100", "analista": "Larissa", "sigla": "RH",
               "descricao": "Ajuste de folha de pagamento mensal", "status": "Em análise",
               "previsao_analise": datetime.date(2026, 1, 1), "prioridade": 1, "ciclo": 1},
}
_OBS = {}
_next_obs_id = [1]


def list_itens(analista=None):
    vals = list(_ITENS.values())
    return [v for v in vals if v["analista"] == analista] if analista else vals


def get_item(id_demanda):
    return _ITENS.get(id_demanda)


def update_item(id_demanda, status, previsao_analise):
    if status is not None:
        _ITENS[id_demanda]["status"] = status
    if previsao_analise is not None:
        _ITENS[id_demanda]["previsao_analise"] = previsao_analise


def list_observacoes(id_demanda):
    return sorted([o for o in _OBS.values() if o["id_demanda"] == id_demanda],
                  key=lambda o: o["criado_em"], reverse=True)


def create_observacao(id_demanda, texto, autor, is_compromisso):
    oid = _next_obs_id[0]
    _next_obs_id[0] += 1
    row = {"id": oid, "id_demanda": id_demanda, "texto": texto, "autor": autor,
           "criado_em": datetime.datetime.now(), "is_compromisso": is_compromisso,
           "resolvido": False, "resolvido_em": None, "resolvido_por": None}
    _OBS[oid] = row
    return row


def resolver_compromisso(obs_id, autor):
    row = _OBS.get(obs_id)
    if not row or not row["is_compromisso"] or row["resolvido"]:
        return None
    row["resolvido"] = True
    row["resolvido_em"] = datetime.datetime.now()
    row["resolvido_por"] = autor
    return row


def list_compromissos_abertos(analista):
    result = []
    for o in _OBS.values():
        if o["is_compromisso"] and not o["resolvido"]:
            item = _ITENS.get(o["id_demanda"])
            if item and item["analista"] == analista:
                result.append({"observacao": o, "id_demanda": o["id_demanda"],
                                "descricao": item["descricao"], "sigla": item["sigla"]})
    return result


repo.list_itens = list_itens
repo.get_item = get_item
repo.update_item = update_item
repo.list_observacoes = list_observacoes
repo.create_observacao = create_observacao
repo.resolver_compromisso = resolver_compromisso
repo.list_compromissos_abertos = list_compromissos_abertos

from app.main import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8129, log_level="warning")
