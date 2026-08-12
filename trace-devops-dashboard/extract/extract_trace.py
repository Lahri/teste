"""
Importa o export em CSV das demandas do Trace (a API não está disponível
por enquanto — confirmado pelo NTI) e gera data/raw/trace_latest.csv no
formato esperado por transform/cross_reference.py.

Mapeamento de colunas confirmado com um export real ("Demandas_20.csv",
376 linhas). Estrutura observada:
    Id, Data/Hora de Criação, Título, Solicitante, Unidade Organizacional,
    Módulo:, Responsável Atendimento, Tipo, Estado, Descrição,
    Descrição da Necessidade, Data da Alteração, ID User Story:,
    Status User Story, Tempo no Estado (Dias)

O export é uma exportação da grade de demandas do Trace (primeira linha
é um título "Demandas", cabeçalho real fica na segunda linha — por isso
SKIP_ROWS=1 abaixo). Se o layout mudar, o script para e mostra o que
esperava vs. o que encontrou (ver main()).

Pontos importantes desse export:
    - Não tem data de conclusão nem horas apropriadas/SLA — parece ser um
      recorte só das demandas em aberto (nenhum "Estado" observado até
      agora indica concluído). Se um export futuro trouxer demandas
      concluídas, ajustar TRACE_DONE_STATES abaixo.
    - "Tempo no Estado (Dias)" já vem calculado pelo Trace — não
      precisamos recalcular como fizemos para o Azure DevOps.
    - "ID User Story:" é o vínculo nativo com o Azure DevOps (o Trace
      aponta pra lá, não o contrário). Vem "sujo" às vezes — mais de um
      id na mesma célula, separado por vírgula/ponto e vírgula, às vezes
      com texto extra colado (ex: "36197 - PENDENTE DEFINIÇÕES...",
      "Spike 613621"). O parser abaixo extrai todos os números de 4+
      dígitos e explode em uma linha por vínculo.

Configuração (variável de ambiente ou .env):
    TRACE_CSV_PATH -> caminho do CSV exportado do Trace
                       (padrão: data/manual/trace_export.csv)

Uso:
    python extract_trace.py
"""

import os
import re
import sys

import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_PATH = os.environ.get("TRACE_CSV_PATH", os.path.join(BASE_DIR, "data", "manual", "trace_export.csv"))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "raw")

# O export do Trace tem uma linha de título ("Demandas") antes do cabeçalho
# de verdade. Ajustar se um export futuro vier sem essa linha extra.
SKIP_ROWS = 1

TRACE_COLUMN_MAP = {
    "Id": "id_demanda",
    "Título": "titulo",
    "Módulo:": "area",
    "Unidade Organizacional": "unidade_organizacional",
    "Estado": "status",
    "Tipo": "tipo",
    "Responsável Atendimento": "responsavel",
    "Solicitante": "solicitante",
    "Data/Hora de Criação": "data_abertura",
    "Data da Alteração": "data_ultima_alteracao",
    "Tempo no Estado (Dias)": "dias_no_status_atual",
    "ID User Story:": "azdo_user_story_id_raw",
    "Status User Story": "status_user_story",
}

REQUIRED_OUTPUT_COLS = [
    "id_demanda", "titulo", "area", "unidade_organizacional", "status",
    "tipo", "responsavel", "solicitante", "data_abertura",
    "data_ultima_alteracao", "dias_no_status_atual", "parado_30_dias",
    "azdo_user_story_id", "status_user_story",
]

# Nenhum valor de "Estado" observado no export real corresponde a demanda
# concluída (o export parece cobrir só as demandas em aberto). Mantido
# configurável para quando um export com demandas finalizadas aparecer.
TRACE_DONE_STATES = {"Concluído", "Concluido", "Concluída", "Finalizado", "Encerrado"}
DIAS_LIMITE_PARADO = 30

_ID_RE = re.compile(r"\d{4,6}")


def _parse_user_story_ids(raw) -> list[str]:
    """'ID User Story:' pode ter mais de um id, separado por vírgula/ponto
    e vírgula, às vezes com texto extra colado (ex: "36197 - PENDENTE...",
    "Spike 613621"). Extrai todos os números de 4 a 6 dígitos."""
    if pd.isna(raw):
        return []
    return _ID_RE.findall(str(raw))


def main():
    if not os.path.exists(INPUT_PATH):
        print(
            f"Erro: não encontrei {INPUT_PATH}.\n"
            "Exporte as demandas do Trace em CSV e salve nesse caminho\n"
            "(ou aponte a variável TRACE_CSV_PATH pra outro lugar).",
            file=sys.stderr,
        )
        sys.exit(1)

    df = pd.read_csv(INPUT_PATH, skiprows=SKIP_ROWS)

    missing = [col for col in TRACE_COLUMN_MAP if col not in df.columns]
    if missing:
        print(
            "Erro: as colunas abaixo eram esperadas mas não foram encontradas no CSV.\n"
            "Ajuste o dicionário TRACE_COLUMN_MAP (e/ou SKIP_ROWS) no topo de\n"
            "extract_trace.py com os nomes reais que aparecem no seu export.\n",
            file=sys.stderr,
        )
        for col in missing:
            print(f"  esperado, não encontrado: {col!r}", file=sys.stderr)
        print(f"\nColunas que o arquivo realmente tem: {list(df.columns)}", file=sys.stderr)
        sys.exit(1)

    df = df.rename(columns=TRACE_COLUMN_MAP)

    df["dias_no_status_atual"] = pd.to_numeric(df["dias_no_status_atual"], errors="coerce")
    concluido = df["status"].isin(TRACE_DONE_STATES)
    df["parado_30_dias"] = (df["dias_no_status_atual"] >= DIAS_LIMITE_PARADO) & ~concluido

    df["azdo_user_story_id"] = df["azdo_user_story_id_raw"].apply(_parse_user_story_ids)
    df = df.explode("azdo_user_story_id")

    df = df[[c for c in REQUIRED_OUTPUT_COLS if c in df.columns]]

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, "trace_latest.csv")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    linhas_originais = df["id_demanda"].nunique()
    com_vinculo = df.loc[df["azdo_user_story_id"].notna(), "id_demanda"].nunique()
    print(f"Gerado: {out_path} ({len(df)} linhas, {linhas_originais} demandas únicas, {com_vinculo} com vínculo ao Azure DevOps)")


if __name__ == "__main__":
    main()
