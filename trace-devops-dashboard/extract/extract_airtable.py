"""
Extrai os itens e o histórico de observações do Airtable (base do Painel de
Análises que os analistas usam para atualizar previsão de análise e
observações) e gera CSVs padronizados em data/raw/, no formato esperado
pelo transform/cross_reference.py.

Esse Airtable é agora a fonte AO VIVO das informações que antes viviam só
na planilha manual (data/manual/informacoes_manuais.xlsx) — os analistas
atualizam pelo painel web, não editando Excel.

Configuração (variáveis de ambiente ou .env):
    AIRTABLE_PAT        -> Personal Access Token do Airtable (não é o mesmo
                            login usado pelo Claude — gerar em
                            airtable.com/create/tokens, escopo mínimo:
                            data.records:read, acesso à base do painel)
    AIRTABLE_BASE_ID    -> ID da base (padrão: a base "Painel de Análises -
                            Comitê SESC" já criada: app5DmsthrcOlJluK)
    AIRTABLE_ITENS_TABLE       -> nome/][id da tabela de itens (padrão: "Itens")
    AIRTABLE_OBSERVACOES_TABLE -> nome/id da tabela de observações (padrão:
                                   "Observacoes")

Uso:
    pip install requests python-dotenv pandas
    python extract_airtable.py
"""

import os
import sys

import pandas as pd
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PAT = os.environ.get("AIRTABLE_PAT")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "app5DmsthrcOlJluK")
ITENS_TABLE = os.environ.get("AIRTABLE_ITENS_TABLE", "Itens")
OBS_TABLE = os.environ.get("AIRTABLE_OBSERVACOES_TABLE", "Observacoes")

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")


def _check_config():
    if not PAT:
        print("Erro: variável de ambiente AIRTABLE_PAT ausente.", file=sys.stderr)
        sys.exit(1)


def _fetch_all_records(table: str) -> list[dict]:
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table}"
    headers = {"Authorization": f"Bearer {PAT}"}
    records = []
    params = {"pageSize": 100}
    while True:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
        params["offset"] = offset
    return records


def itens_to_dataframe(records: list[dict]) -> pd.DataFrame:
    rows = []
    for r in records:
        f = r.get("fields", {})
        rows.append({
            "airtable_record_id": r["id"],
            "ID": f.get("ID"),
            "Analista": f.get("Analista"),
            "Sigla": f.get("Sigla"),
            "Descricao": f.get("Descricao"),
            "Status": f.get("Status"),
            "Previsao_Analise": f.get("Previsao_Analise"),
            "Prioridade": f.get("Prioridade"),
            "Ciclo": f.get("Ciclo"),
        })
    return pd.DataFrame(rows)


def observacoes_to_dataframe(records: list[dict]) -> pd.DataFrame:
    rows = []
    for r in records:
        f = r.get("fields", {})
        rows.append({
            "airtable_record_id": r["id"],
            "ID_Item": f.get("ID_Item"),
            "Autor": f.get("Autor"),
            "Data": f.get("Data"),
            "Texto": f.get("Texto"),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce", utc=True)
        df = df.sort_values("Data", ascending=False)
    return df


def main():
    _check_config()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Consultando tabela '{ITENS_TABLE}' na base {BASE_ID}...")
    itens_records = _fetch_all_records(ITENS_TABLE)
    itens_df = itens_to_dataframe(itens_records)
    itens_path = os.path.join(OUTPUT_DIR, "airtable_itens_latest.csv")
    itens_df.to_csv(itens_path, index=False, encoding="utf-8-sig")
    print(f"Gerado: {itens_path} ({len(itens_df)} itens)")

    print(f"Consultando tabela '{OBS_TABLE}' na base {BASE_ID}...")
    obs_records = _fetch_all_records(OBS_TABLE)
    obs_df = observacoes_to_dataframe(obs_records)
    obs_path = os.path.join(OUTPUT_DIR, "airtable_observacoes_latest.csv")
    obs_df.to_csv(obs_path, index=False, encoding="utf-8-sig")
    print(f"Gerado: {obs_path} ({len(obs_df)} observações)")


if __name__ == "__main__":
    main()
