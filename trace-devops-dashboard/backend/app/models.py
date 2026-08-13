from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class Item(BaseModel):
    id_demanda: str
    analista: Optional[str] = None
    sigla: Optional[str] = None
    descricao: Optional[str] = None
    status: str
    previsao_analise: Optional[date] = None
    prioridade: Optional[int] = None
    ciclo: Optional[int] = None


class ItemUpdate(BaseModel):
    status: Optional[str] = None
    previsao_analise: Optional[date] = None


class Observacao(BaseModel):
    id: int
    id_demanda: str
    texto: str
    autor: str
    criado_em: datetime
    is_compromisso: bool
    resolvido: bool
    resolvido_em: Optional[datetime] = None
    resolvido_por: Optional[str] = None


class ObservacaoCreate(BaseModel):
    texto: str
    autor: str
    is_compromisso: bool = False


class ResolverCompromisso(BaseModel):
    autor: str


class CompromissoAberto(BaseModel):
    observacao: Observacao
    id_demanda: str
    descricao: Optional[str] = None
    sigla: Optional[str] = None
