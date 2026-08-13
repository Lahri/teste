import os
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, repo, trace_import
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


@app.post("/api/importar-trace")
async def importar_trace(file: UploadFile):
    conteudo = await file.read()
    try:
        resumo = trace_import.importar(file.filename or "arquivo.csv", conteudo)
    except trace_import.CsvInvalidoError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except trace_import.extract_trace.ColunasFaltandoError as e:
        raise HTTPException(status_code=422, detail={
            "mensagem": "O arquivo não tem o formato esperado do export do Trace.",
            "colunas_faltando": e.faltando,
            "colunas_encontradas": e.encontradas,
        })
    return {"ok": True, **resumo}


# Serve o painel (frontend/painel-analistas.html) na mesma origem da API,
# assim o front pode chamar /api/... sem CORS. Registrado por último: as
# rotas /api/* acima têm prioridade, o mount só pega o que sobrar.
_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(_FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
