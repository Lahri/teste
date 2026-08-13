"""
Cruza os dados extraídos do Trace e do Azure DevOps e gera o dataset
final que o Power BI (ou qualquer outra ferramenta) vai consumir.

Lê:
    data/raw/azure_devops_latest.csv        (opcional — se não existir, roda em
                                              modo só-manual: pula dataset_final
                                              cruzado e resumo_por_area, gera só
                                              o que vem da planilha manual)
    data/raw/trace_latest.csv               (opcional — se ainda não existir,
                                              o script roda em modo parcial
                                              só com os dados do Azure DevOps)
    data/raw/airtable_itens_latest.csv       (preferencial — dado AO VIVO do
                                              painel web dos analistas; ver
                                              extract/extract_airtable.py)
    data/manual/informacoes_manuais.xlsx     (legado — usado só se o CSV do
                                              Airtable acima não existir;
                                              ver README > "Informações manuais")
    data/raw/airtable_observacoes_latest.csv (opcional — histórico de
                                              observações por item, gerado
                                              pelo mesmo extrator)

Gera:
    data/processed/dataset_final.csv        -> uma linha por item (join,
                                                quando houver vínculo), já
                                                com os dados manuais de
                                                Itens_Refinados anexados
    data/processed/resumo_por_area.csv      -> métricas agregadas por área,
                                                para identificar gargalos,
                                                incluindo chamados parados
                                                há 30+ dias no mesmo status
    data/processed/resumo_por_sigla.csv     -> volume de itens e previsões
                                                vencidas por sigla interna
                                                (manual_area), dimensão própria
                                                da equipe, separada da área do
                                                Trace/Azure DevOps
    data/processed/historico_observacoes.csv -> repasse do histórico de
                                                observações do Airtable
                                                (uma linha por observação)
    data/processed/observacoes_area.csv     -> repasse da aba Observacoes_Area
                                                (legado, só se vier do xlsx)
    data/processed/pedidos_recurso.csv      -> repasse da aba Pedidos_Recurso
                                                (legado, só se vier do xlsx)

Modo de vínculo:
    Se o CSV do Azure DevOps tiver a coluna "trace_demanda_id" preenchida
    (ver AZDO_TRACE_LINK_FIELD no extractor), o cruzamento é feito 1:1
    por essa chave. Caso contrário, os dados são combinados apenas por
    área/período (modo agregado, sem vínculo item a item) — ver função
    `resumo_por_area`.

Uso:
    python transform/cross_reference.py
"""

import os
from datetime import datetime, timezone

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
MANUAL_DIR = os.path.join(BASE_DIR, "data", "manual")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

AZDO_PATH = os.path.join(RAW_DIR, "azure_devops_latest.csv")
TRACE_PATH = os.path.join(RAW_DIR, "trace_latest.csv")
MANUAL_PATH = os.path.join(MANUAL_DIR, "informacoes_manuais.xlsx")
AIRTABLE_ITENS_PATH = os.path.join(RAW_DIR, "airtable_itens_latest.csv")
AIRTABLE_OBS_PATH = os.path.join(RAW_DIR, "airtable_observacoes_latest.csv")

# Estados considerados "concluído" em cada sistema — ajustar conforme
# os nomes reais de status usados no Trace e no processo do Azure DevOps.
AZDO_DONE_STATES = {"Done", "Closed", "Resolved", "Concluído", "Concluido"}
# Nenhum valor de "Estado" observado no export real do Trace corresponde a
# demanda concluída (o export parece cobrir só as demandas em aberto).
TRACE_DONE_STATES = {"Concluído", "Concluido", "Concluída", "Finalizado", "Encerrado"}

# Único status que conta como "concluído" nos itens do painel/planilha —
# ajustar se a equipe passar a usar outro nome pra fechar um item.
MANUAL_DONE_STATES = {"Publicado"}

# "Área"/"Sigla" nos itens do painel (NEF, NAD, GED, NUGE, GEL, GEC, MKT...)
# é classificação própria da equipe — dimensão distinta da área/destino do
# Trace e do Azure DevOps, não deve ser somada/misturada com elas.

# "Data Encerramento Análise" é o prazo da fase de ANÁLISE, não da entrega
# inteira. Uma vez que o item sai desses status (foi para desenvolvimento,
# teste, ou está aguardando próxima etapa), a análise já encerrou — no prazo
# ou não, deixa de fazer sentido marcar como "vencida". Só conta como
# vencida quem ainda está literalmente em análise (ou nem começou) depois
# do prazo.
ANALISE_EM_ANDAMENTO_STATES = {"Em análise", "A fazer", "Em analise/Desenvolvimento"}

# Ponto levantado pela coordenação: sinalizar chamados parados há muito
# tempo no mesmo status (mesmo critério cobrado nas reuniões de indicadores).
DIAS_LIMITE_PARADO = 30


def load_azdo() -> pd.DataFrame | None:
    if not os.path.exists(AZDO_PATH):
        print(f"Aviso: {AZDO_PATH} não encontrado. Rodando em modo só-manual (sem Azure DevOps/Trace).")
        return None
    df = pd.read_csv(AZDO_PATH, parse_dates=["data_criacao", "data_ultima_alteracao", "data_conclusao"])
    df["origem"] = "azure_devops"

    # A API sempre preenche data_ultima_alteracao; um CSV de amostra sem
    # essa coluna (ou totalmente vazia) não deve derrubar o pipeline —
    # só não dá pra calcular "parado 30+ dias" sem ela.
    if df["data_ultima_alteracao"].notna().any():
        agora = pd.Timestamp.now(tz="UTC")
        em_aberto = df["data_conclusao"].isna()
        df["dias_no_status_atual"] = ((agora - df["data_ultima_alteracao"]).dt.days).where(em_aberto)
        df["parado_30_dias"] = em_aberto & (df["dias_no_status_atual"] >= DIAS_LIMITE_PARADO)
    else:
        print(f"Aviso: {AZDO_PATH} sem data_ultima_alteracao preenchida — pulando cálculo de dias parado.")
        df["dias_no_status_atual"] = pd.NA
        df["parado_30_dias"] = False
    return df


def load_trace() -> pd.DataFrame | None:
    """Lê data/raw/trace_latest.csv (gerado por extract_trace.py a partir do
    CSV exportado do Trace). dias_no_status_atual e parado_30_dias já vêm
    calculados pelo extrator — o Trace informa isso nativamente, diferente
    do Azure DevOps."""
    if not os.path.exists(TRACE_PATH):
        print(f"Aviso: {TRACE_PATH} não encontrado. Rodando em modo parcial (só Azure DevOps).")
        return None
    df = pd.read_csv(TRACE_PATH, parse_dates=["data_abertura", "data_ultima_alteracao"])
    df["parado_30_dias"] = df["parado_30_dias"].astype(str).str.lower().eq("true")
    df["azdo_user_story_id"] = df["azdo_user_story_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    df.loc[df["azdo_user_story_id"].isin(["nan", "None", ""]), "azdo_user_story_id"] = None
    df["origem"] = "trace"
    return df


def load_manual_xlsx() -> dict[str, pd.DataFrame] | None:
    """Lê data/manual/informacoes_manuais.xlsx (legado). Usado como fallback
    só quando o CSV do Airtable (dado ao vivo do painel) não está disponível,
    e ainda serve como fonte das abas Observacoes_Area/Pedidos_Recurso, que
    não têm equivalente no Airtable."""
    if not os.path.exists(MANUAL_PATH):
        return None

    sheets = pd.read_excel(MANUAL_PATH, sheet_name=None, header=3)
    result = {}
    for name, df in sheets.items():
        df = df.dropna(how="all")
        result[name] = df
    return result


def _load_itens_from_airtable() -> pd.DataFrame | None:
    """Itens já vêm um-por-linha (sem IDs múltiplos por célula) e com
    Previsao_Analise em ISO — normaliza só os nomes de coluna."""
    if not os.path.exists(AIRTABLE_ITENS_PATH):
        return None
    df = pd.read_csv(AIRTABLE_ITENS_PATH)
    if df.empty:
        return None
    itens = df.rename(columns={
        "Prioridade": "manual_prioridade",
        "Analista": "manual_analista",
        "ID": "manual_ids",
        "Sigla": "manual_area",
        "Descricao": "manual_descricao",
        "Ciclo": "manual_ciclo",
        "Status": "manual_status",
        "Previsao_Analise": "manual_previsao_conclusao_analise",
    })
    itens = itens.dropna(subset=["manual_ids"])
    itens["manual_ids"] = itens["manual_ids"].astype(str).str.strip()
    print(f"Informações manuais: lendo do Airtable ({AIRTABLE_ITENS_PATH}), {len(itens)} itens.")
    return itens


def _load_itens_from_xlsx(manual: dict[str, pd.DataFrame] | None) -> pd.DataFrame | None:
    if not manual or "Itens_Refinados" not in manual or manual["Itens_Refinados"].empty:
        return None

    itens = manual["Itens_Refinados"].rename(columns={
        "Prioridade": "manual_prioridade",
        "Analista": "manual_analista",
        "ID(s)": "manual_ids",
        "Área": "manual_area",
        "Descrição resumida": "manual_descricao",
        "Ciclo": "manual_ciclo",
        "Status": "manual_status",
        "Observação": "manual_observacao",
        "Data Encerramento Análise": "manual_previsao_conclusao_analise",
    })
    itens = itens.dropna(subset=["manual_ids"])

    # A coluna ID(s) pode ter mais de um id na mesma linha, ex:
    # "614776 / 532227" — explode em uma linha por id para o cruzamento.
    itens["manual_ids"] = itens["manual_ids"].astype(str).str.split("/")
    itens = itens.explode("manual_ids")
    itens["manual_ids"] = itens["manual_ids"].str.strip()
    itens = itens[itens["manual_ids"] != ""]
    print(f"Informações manuais: lendo da planilha legada ({MANUAL_PATH}), {len(itens)} itens.")
    return itens


def prepare_itens_refinados(manual: dict[str, pd.DataFrame] | None) -> pd.DataFrame | None:
    """Carrega os itens priorizados pelo comitê — preferindo o Airtable
    (dado ao vivo, atualizado pelos analistas no painel web) e caindo para a
    planilha Excel legada só se o Airtable não estiver disponível. Depois
    calcula se a previsão de encerramento da análise já venceu sem o item
    estar publicado."""
    itens = _load_itens_from_airtable()
    if itens is None:
        itens = _load_itens_from_xlsx(manual)
    if itens is None:
        return None

    # format="mixed": Airtable já manda ISO (YYYY-MM-DD); a planilha legada
    # manda dd/mm/yyyy — dayfirst resolve a ambiguidade só para esta última.
    previsao = pd.to_datetime(itens["manual_previsao_conclusao_analise"], format="mixed", dayfirst=True, errors="coerce")
    em_analise = itens["manual_status"].isin(ANALISE_EM_ANDAMENTO_STATES)
    # Compara só a data (não a hora): um item com previsão para hoje ainda
    # não está vencido, só passa a contar a partir de amanhã. E só conta
    # como vencido quem ainda está em análise — quem já foi para
    # desenvolvimento/teste/fila deixou a análise pra trás, no prazo ou não.
    hoje = pd.Timestamp.now().normalize()
    itens["manual_previsao_vencida"] = (previsao < hoje) & em_analise
    itens = itens.drop_duplicates(subset="manual_ids", keep="last")
    return itens


def load_historico_observacoes() -> pd.DataFrame | None:
    """Histórico de observações por item, vindo do Airtable (uma linha por
    observação, mais recente primeiro) — ver extract/extract_airtable.py."""
    if not os.path.exists(AIRTABLE_OBS_PATH):
        return None
    df = pd.read_csv(AIRTABLE_OBS_PATH)
    return df if not df.empty else None


def resumo_por_sigla(manual: dict[str, pd.DataFrame] | None) -> pd.DataFrame | None:
    """Volume de itens por sigla interna (manual_area), com quantos estão
    com previsão de análise vencida — visão de gargalo pela classificação
    própria da equipe, separada da área do Trace/Azure DevOps."""
    itens = prepare_itens_refinados(manual)
    if itens is None:
        return None

    resumo = (
        itens.assign(concluido=itens["manual_status"].isin(MANUAL_DONE_STATES))
        .groupby("manual_area")
        .agg(
            total_itens=("manual_ids", "count"),
            concluidos=("concluido", "sum"),
            previsao_vencida=("manual_previsao_vencida", "sum"),
        )
    )
    resumo["em_andamento"] = resumo["total_itens"] - resumo["concluidos"]
    return resumo.reset_index()


def resumo_por_area(azdo: pd.DataFrame, trace: pd.DataFrame | None) -> pd.DataFrame:
    """Métricas agregadas por área, para identificar gargalos e necessidade de recursos."""
    azdo_agg = (
        azdo.assign(concluido=azdo["status"].isin(AZDO_DONE_STATES))
        .groupby("area")
        .agg(
            azdo_total=("id", "count"),
            azdo_concluidos=("concluido", "sum"),
            azdo_horas_restantes=("horas_restantes", "sum"),
            azdo_parados_30_dias=("parado_30_dias", "sum"),
        )
    )
    azdo_agg["azdo_abertos"] = azdo_agg["azdo_total"] - azdo_agg["azdo_concluidos"]

    if trace is None:
        return azdo_agg.reset_index()

    # trace pode ter mais de uma linha por id_demanda (uma demanda vinculada
    # a vários work items do Azure DevOps) — usar nunique, não count, pra
    # não contar a mesma demanda duas vezes.
    trace_dedup = trace.drop_duplicates(subset="id_demanda")
    trace_agg = (
        trace_dedup.assign(concluido=trace_dedup["status"].isin(TRACE_DONE_STATES))
        .groupby("area")
        .agg(
            trace_total=("id_demanda", "nunique"),
            trace_concluidas=("concluido", "sum"),
            trace_parados_30_dias=("parado_30_dias", "sum"),
        )
    )
    trace_agg["trace_abertas"] = trace_agg["trace_total"] - trace_agg["trace_concluidas"]

    resumo = azdo_agg.join(trace_agg, how="outer").fillna(0).reset_index()
    return resumo


def dataset_final(azdo: pd.DataFrame | None, trace: pd.DataFrame | None, manual: dict[str, pd.DataFrame] | None) -> pd.DataFrame:
    """Join com o Trace, quando disponível; senão retorna só o Azure DevOps.
    Em seguida, anexa a aba Itens_Refinados (informações manuais) por id_item.

    Duas formas de vínculo com o Trace, nessa ordem de preferência:
      1. Lado do Trace: coluna "azdo_user_story_id" (campo nativo do Trace,
         "ID User Story:") apontando pro id do work item — é o vínculo real
         confirmado num export de produção.
      2. Lado do Azure DevOps: campo customizado configurável via
         AZDO_TRACE_LINK_FIELD no extrator — usado só se o primeiro não
         existir (ex: campo ainda não foi criado no processo do DevOps).

    Modo só-manual: se não houver dados do Azure DevOps, retorna só os itens
    da planilha manual (sem cruzamento com sistema nenhum)."""
    if azdo is None:
        itens = prepare_itens_refinados(manual)
        return itens if itens is not None else pd.DataFrame()

    trace_side_link = (
        trace is not None
        and "azdo_user_story_id" in trace.columns
        and trace["azdo_user_story_id"].notna().any()
    )
    azdo_side_link = (
        trace is not None
        and "trace_demanda_id" in azdo.columns
        and azdo["trace_demanda_id"].notna().any()
    )

    if trace_side_link:
        df = azdo.merge(
            trace,
            left_on=azdo["id"].astype(str),
            right_on=trace["azdo_user_story_id"].astype(str),
            how="left",
            suffixes=("_azdo", "_trace"),
        )
    elif azdo_side_link:
        df = azdo.merge(
            trace,
            left_on="trace_demanda_id",
            right_on="id_demanda",
            how="left",
            suffixes=("_azdo", "_trace"),
        )
    else:
        df = azdo

    itens = prepare_itens_refinados(manual)
    if itens is not None:
        # Itens do painel/planilha são indexados pelo nº da demanda do
        # Trace — monta uma única chave de busca por linha, priorizando
        # "id_demanda" (vem do Trace quando o cruzamento deu certo, é o
        # mesmo número usado no painel), depois "trace_demanda_id" (campo
        # customizado legado do lado do Azure DevOps), e só por último o
        # id do work item (útil quando não há Trace envolvido).
        chave = df["id"].astype(str)
        if "trace_demanda_id" in df.columns:
            chave = df["trace_demanda_id"].astype(str).where(df["trace_demanda_id"].notna(), chave)
        if "id_demanda" in df.columns:
            # id_demanda vira float (ex: 610219.0) quando o merge com o
            # Trace deixa NaN em algumas linhas — remove o ".0" antes de
            # comparar como texto com manual_ids.
            id_demanda_str = df["id_demanda"].astype(str).str.replace(r"\.0$", "", regex=True)
            chave = id_demanda_str.where(df["id_demanda"].notna(), chave)
        df["_chave_manual"] = chave

        df = df.merge(itens, left_on="_chave_manual", right_on="manual_ids", how="left")
        df = df.drop(columns=["_chave_manual"])

    return df


def main():
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    azdo = load_azdo()
    trace = load_trace()
    manual = load_manual_xlsx()

    final = dataset_final(azdo, trace, manual)
    if not final.empty:
        final_path = os.path.join(PROCESSED_DIR, "dataset_final.csv")
        final.to_csv(final_path, index=False, encoding="utf-8-sig")
        print(f"Gerado: {final_path} ({len(final)} linhas)")

    if azdo is not None:
        resumo = resumo_por_area(azdo, trace)
        resumo_path = os.path.join(PROCESSED_DIR, "resumo_por_area.csv")
        resumo.to_csv(resumo_path, index=False, encoding="utf-8-sig")
        print(f"Gerado: {resumo_path} ({len(resumo)} áreas)")
    else:
        print("Pulando resumo_por_area.csv (precisa dos dados do Azure DevOps).")

    resumo_sigla = resumo_por_sigla(manual)
    if resumo_sigla is not None:
        resumo_sigla_path = os.path.join(PROCESSED_DIR, "resumo_por_sigla.csv")
        resumo_sigla.to_csv(resumo_sigla_path, index=False, encoding="utf-8-sig")
        print(f"Gerado: {resumo_sigla_path} ({len(resumo_sigla)} siglas)")

    historico = load_historico_observacoes()
    if historico is not None:
        historico_path = os.path.join(PROCESSED_DIR, "historico_observacoes.csv")
        historico.to_csv(historico_path, index=False, encoding="utf-8-sig")
        print(f"Gerado: {historico_path} ({len(historico)} observações)")

    if manual:
        for sheet_name, out_name in [
            ("Observacoes_Area", "observacoes_area.csv"),
            ("Pedidos_Recurso", "pedidos_recurso.csv"),
        ]:
            df = manual.get(sheet_name)
            if df is not None and not df.empty:
                out_path = os.path.join(PROCESSED_DIR, out_name)
                df.to_csv(out_path, index=False, encoding="utf-8-sig")
                print(f"Gerado: {out_path} ({len(df)} linhas)")


if __name__ == "__main__":
    main()
