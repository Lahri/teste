"""
Importação do CSV do Trace pela gestora, direto pela tela web -- sem
precisar de ninguém rodar extract/extract_trace.py no terminal.

Reaproveita a MESMA lógica de validação/parsing do script de linha de
comando (extract_trace.process_trace_dataframe) em vez de duplicar --
uma lógica só, dois jeitos de chamar. Ver extract/extract_trace.py pro
mapeamento de colunas e o porquê de cada regra.
"""
import io
import os
import sys

import pandas as pd

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_APP_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
_EXTRACT_DIR = os.path.join(_PROJECT_ROOT, "extract")
_OUTPUT_PATH = os.path.join(_PROJECT_ROOT, "data", "raw", "trace_latest.csv")

if _EXTRACT_DIR not in sys.path:
    sys.path.insert(0, _EXTRACT_DIR)

import extract_trace  # noqa: E402


class CsvInvalidoError(Exception):
    """O arquivo enviado não é um CSV legível (formato errado, corrompido etc)."""


def importar(nome_arquivo: str, conteudo: bytes) -> dict:
    """Valida e processa o CSV do Trace enviado pela tela de upload.
    Levanta CsvInvalidoError (arquivo ilegível) ou
    extract_trace.ColunasFaltandoError (layout do export mudou) --
    quem chama decide como virar resposta HTTP. Em sucesso, salva no
    mesmo lugar que o CLI salvaria (data/raw/trace_latest.csv) e devolve
    um resumo pra mostrar na tela."""
    if not nome_arquivo.lower().endswith(".csv"):
        raise CsvInvalidoError(f"Esperado um arquivo .csv, recebi {nome_arquivo!r}.")

    try:
        df = pd.read_csv(io.BytesIO(conteudo), skiprows=extract_trace.SKIP_ROWS)
    except Exception as e:
        raise CsvInvalidoError(f"Não consegui ler o arquivo como CSV: {e}") from e

    if df.empty:
        raise CsvInvalidoError("O arquivo está vazio (ou só tem a linha de título).")

    processed = extract_trace.process_trace_dataframe(df)  # pode levantar ColunasFaltandoError

    os.makedirs(os.path.dirname(_OUTPUT_PATH), exist_ok=True)
    processed.to_csv(_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    demandas_unicas = int(processed["id_demanda"].nunique())
    com_vinculo = int(processed.loc[processed["azdo_user_story_id"].notna(), "id_demanda"].nunique())
    return {
        "linhas": int(len(processed)),
        "demandas_unicas": demandas_unicas,
        "com_vinculo_devops": com_vinculo,
        "salvo_em": _OUTPUT_PATH,
    }
