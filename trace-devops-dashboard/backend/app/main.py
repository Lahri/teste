from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import config, repo
from .models import (
    CompromissoAberto,
    Item,
    ItemUpdate,
    Observacao,
    ObservacaoCreate,
    ResolverCompromisso,
)

app = FastAPI(title="Painel de Demandas — API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/itens", response_model=list[Item])
def get_itens(analista: Optional[str] = None):
    return repo.list_itens(analista)


@app.patch("/api/itens/{id_demanda}", response_model=Item)
def patch_item(id_demanda: str, body: ItemUpdate):
    if repo.get_item(id_demanda) is None:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    repo.update_item(id_demanda, body.status, body.previsao_analise)
    return repo.get_item(id_demanda)


@app.get("/api/itens/{id_demanda}/observacoes", response_model=list[Observacao])
def get_observacoes(id_demanda: str):
    if repo.get_item(id_demanda) is None:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    return repo.list_observacoes(id_demanda)


@app.post("/api/itens/{id_demanda}/observacoes", response_model=Observacao)
def post_observacao(id_demanda: str, body: ObservacaoCreate):
    if repo.get_item(id_demanda) is None:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    return repo.create_observacao(id_demanda, body.texto, body.autor, body.is_compromisso)


@app.post("/api/observacoes/{obs_id}/resolver", response_model=Observacao)
def post_resolver(obs_id: int, body: ResolverCompromisso):
    result = repo.resolver_compromisso(obs_id, body.autor)
    if result is None:
        raise HTTPException(status_code=404, detail="Compromisso não encontrado ou já resolvido.")
    return result


@app.get("/api/compromissos", response_model=list[CompromissoAberto])
def get_compromissos(analista: str):
    return repo.list_compromissos_abertos(analista)


@app.get("/api/health")
def health():
    return {"status": "ok"}
