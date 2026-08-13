"""
Extrai work items do Azure DevOps (via API REST) e gera um CSV tratado
para cruzamento com dados do Trace.

Configuração (variáveis de ambiente ou .env):
    AZDO_ORG          -> nome da organização (ex: "sescrs")
    AZDO_PROJECT       -> nome do projeto (ex: "TI")
    AZDO_PAT           -> Personal Access Token com escopo "Work Items (Read)"

Como gerar o PAT:
    Azure DevOps > ícone de usuário > Personal Access Tokens > New Token
    Escopo mínimo necessário: Work Items -> Read

Uso:
    pip install requests python-dotenv pandas
    python extract_azure_devops.py
"""

import os
import sys
from datetime import datetime, timezone

import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ORG = os.environ.get("AZDO_ORG")
PROJECT = os.environ.get("AZDO_PROJECT")
PAT = os.environ.get("AZDO_PAT")
API_VERSION = "7.1"

# Campo customizado (opcional) usado para vincular o work item à demanda
# do Trace, ex: "Custom.TraceDemandaId". Deixe em branco se ainda não
# existir esse campo no processo do Azure DevOps.
TRACE_LINK_FIELD = os.environ.get("AZDO_TRACE_LINK_FIELD", "").strip()

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")

# Campos que trazemos de cada work item. Ajuste conforme o processo
# (Agile/Scrum/CMMI) usado no projeto do Azure DevOps.
FIELDS = [
    "System.Id",
    "System.Title",
    "System.WorkItemType",
    "System.State",
    "System.AreaPath",
    "System.TeamProject",
    "System.AssignedTo",
    "System.CreatedDate",
    "System.ChangedDate",
    "Microsoft.VSTS.Common.ClosedDate",
    "Microsoft.VSTS.Scheduling.OriginalEstimate",
    "Microsoft.VSTS.Scheduling.RemainingWork",
    "Microsoft.VSTS.Scheduling.CompletedWork",
    "Microsoft.VSTS.Common.Priority",
]
if TRACE_LINK_FIELD:
    FIELDS.append(TRACE_LINK_FIELD)


def _check_config():
    missing = [name for name, val in [("AZDO_ORG", ORG), ("AZDO_PROJECT", PROJECT), ("AZDO_PAT", PAT)] if not val]
    if missing:
        print(f"Erro: variáveis de ambiente ausentes: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)


def _auth():
    # PAT vai como senha, usuário fica vazio (autenticação básica do Azure DevOps)
    return HTTPBasicAuth("", PAT)


def get_work_item_ids() -> list[int]:
    """Roda uma query WIQL trazendo todos os work items do projeto (exceto removidos)."""
    url = f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/wiql?api-version={API_VERSION}"
    wiql = {
        "query": (
            "SELECT [System.Id] FROM WorkItems "
            "WHERE [System.TeamProject] = @project "
            "AND [System.State] <> 'Removed' "
            "ORDER BY [System.ChangedDate] DESC"
        )
    }
    resp = requests.post(url, json=wiql, auth=_auth())
    resp.raise_for_status()
    data = resp.json()
    return [item["id"] for item in data.get("workItems", [])]


def get_work_items_batch(ids: list[int]) -> list[dict]:
    """Busca os detalhes dos work items em lotes de 200 (limite da API)."""
    url = f"https://dev.azure.com/{ORG}/_apis/wit/workitemsbatch?api-version={API_VERSION}"
    all_items = []
    batch_size = 200
    for i in range(0, len(ids), batch_size):
        chunk = ids[i:i + batch_size]
        payload = {"ids": chunk, "fields": FIELDS}
        resp = requests.post(url, json=payload, auth=_auth())
        resp.raise_for_status()
        all_items.extend(resp.json().get("value", []))
        print(f"  -> {min(i + batch_size, len(ids))}/{len(ids)} work items carregados")
    return all_items


def to_dataframe(items: list[dict]) -> pd.DataFrame:
    rows = []
    for item in items:
        f = item.get("fields", {})
        assigned_to = f.get("System.AssignedTo")
        rows.append({
            "id": item["id"],
            "titulo": f.get("System.Title"),
            "tipo": f.get("System.WorkItemType"),
            "status": f.get("System.State"),
            "area": f.get("System.AreaPath"),
            "projeto": f.get("System.TeamProject"),
            "responsavel": assigned_to.get("displayName") if isinstance(assigned_to, dict) else assigned_to,
            "data_criacao": f.get("System.CreatedDate"),
            "data_ultima_alteracao": f.get("System.ChangedDate"),
            "data_conclusao": f.get("Microsoft.VSTS.Common.ClosedDate"),
            "estimativa_horas": f.get("Microsoft.VSTS.Scheduling.OriginalEstimate"),
            "horas_restantes": f.get("Microsoft.VSTS.Scheduling.RemainingWork"),
            "horas_concluidas": f.get("Microsoft.VSTS.Scheduling.CompletedWork"),
            "prioridade": f.get("Microsoft.VSTS.Common.Priority"),
            "trace_demanda_id": f.get(TRACE_LINK_FIELD) if TRACE_LINK_FIELD else None,
        })
    df = pd.DataFrame(rows)
    for col in ["data_criacao", "data_ultima_alteracao", "data_conclusao"]:
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
    return df


def main():
    _check_config()
    print(f"Consultando work items de {ORG}/{PROJECT}...")
    ids = get_work_item_ids()
    print(f"{len(ids)} work items encontrados. Buscando detalhes...")
    items = get_work_items_batch(ids)
    df = to_dataframe(items)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Arquivo com timestamp (histórico) + arquivo "latest" fixo (o que o
    # transform/cross_reference.py sempre lê).
    dated_path = os.path.join(OUTPUT_DIR, f"azure_devops_{timestamp}.csv")
    latest_path = os.path.join(OUTPUT_DIR, "azure_devops_latest.csv")
    df.to_csv(dated_path, index=False, encoding="utf-8-sig")
    df.to_csv(latest_path, index=False, encoding="utf-8-sig")
    print(f"\nArquivo gerado: {dated_path} ({len(df)} linhas)")
    print(f"Atualizado: {latest_path}")


if __name__ == "__main__":
    main()
