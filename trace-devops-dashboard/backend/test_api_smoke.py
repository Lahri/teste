"""
Smoke test da API sem Oracle real: substitui as funcoes de app.repo por
fakes em memoria e bate nos endpoints via TestClient. Nao valida SQL nem
o schema.sql contra um Oracle de verdade -- isso so da pra confirmar
rodando o docker-compose (precisa de Docker, que nao tem neste sandbox).
Roda: python test_api_smoke.py
"""
import datetime
import sys

from fastapi.testclient import TestClient

from app import repo

_ITENS = {
    "611742": {"id_demanda": "611742", "analista": "Larissa", "sigla": "NEF",
               "descricao": "APIs do BB", "status": "Em testes",
               "previsao_analise": datetime.date(2026, 6, 12), "prioridade": 1, "ciclo": 1},
}
_OBS = {}
_next_obs_id = [1]


def fake_list_itens(analista=None):
    vals = list(_ITENS.values())
    if analista:
        vals = [v for v in vals if v["analista"] == analista]
    return vals


def fake_get_item(id_demanda):
    return _ITENS.get(id_demanda)


def fake_update_item(id_demanda, status, previsao_analise):
    if status is not None:
        _ITENS[id_demanda]["status"] = status
    if previsao_analise is not None:
        _ITENS[id_demanda]["previsao_analise"] = previsao_analise


def fake_list_observacoes(id_demanda):
    return [o for o in _OBS.values() if o["id_demanda"] == id_demanda]


def fake_create_observacao(id_demanda, texto, autor, is_compromisso):
    oid = _next_obs_id[0]; _next_obs_id[0] += 1
    row = {"id": oid, "id_demanda": id_demanda, "texto": texto, "autor": autor,
           "criado_em": datetime.datetime.now(), "is_compromisso": is_compromisso,
           "resolvido": False, "resolvido_em": None, "resolvido_por": None}
    _OBS[oid] = row
    return row


def fake_resolver_compromisso(obs_id, autor):
    row = _OBS.get(obs_id)
    if not row or not row["is_compromisso"] or row["resolvido"]:
        return None
    row["resolvido"] = True
    row["resolvido_em"] = datetime.datetime.now()
    row["resolvido_por"] = autor
    return row


def fake_list_compromissos_abertos(analista):
    result = []
    for o in _OBS.values():
        if o["is_compromisso"] and not o["resolvido"]:
            item = _ITENS.get(o["id_demanda"])
            if item and item["analista"] == analista:
                result.append({"observacao": o, "id_demanda": o["id_demanda"],
                                "descricao": item["descricao"], "sigla": item["sigla"]})
    return result


repo.list_itens = fake_list_itens
repo.get_item = fake_get_item
repo.update_item = fake_update_item
repo.list_observacoes = fake_list_observacoes
repo.create_observacao = fake_create_observacao
repo.resolver_compromisso = fake_resolver_compromisso
repo.list_compromissos_abertos = fake_list_compromissos_abertos

from app.main import app  # noqa: E402

client = TestClient(app)
fails = []


def check(name, cond):
    print(("OK  " if cond else "FAIL") + " " + name)
    if not cond:
        fails.append(name)


r = client.get("/api/itens", params={"analista": "Larissa"})
check("GET /api/itens 200", r.status_code == 200)
check("GET /api/itens returns 1 item", len(r.json()) == 1)

r = client.get("/api/itens/611742/observacoes")
check("GET observacoes 200 empty", r.status_code == 200 and r.json() == [])

r = client.post("/api/itens/611742/observacoes", json={
    "texto": "falar com Rosangela sobre retorno", "autor": "Larissa", "is_compromisso": True,
})
check("POST observacao 200", r.status_code == 200)
obs_id = r.json()["id"]
check("POST observacao is_compromisso true", r.json()["is_compromisso"] is True)

r = client.get("/api/compromissos", params={"analista": "Larissa"})
check("GET compromissos shows 1 open", r.status_code == 200 and len(r.json()) == 1)

r = client.post(f"/api/observacoes/{obs_id}/resolver", json={"autor": "Larissa"})
check("POST resolver 200", r.status_code == 200)
check("resolver marks resolvido true", r.json()["resolvido"] is True)

r = client.get("/api/compromissos", params={"analista": "Larissa"})
check("GET compromissos empty after resolve", r.status_code == 200 and len(r.json()) == 0)

r = client.patch("/api/itens/611742", json={"status": "Publicado"})
check("PATCH item 200", r.status_code == 200)
check("PATCH item updates status", r.json()["status"] == "Publicado")

r = client.get("/api/itens/999999/observacoes")
check("GET observacoes 404 for unknown item", r.status_code == 404)

print()
if fails:
    print(f"{len(fails)} FALHA(S):", fails)
    sys.exit(1)
print("Todos os checks passaram.")
