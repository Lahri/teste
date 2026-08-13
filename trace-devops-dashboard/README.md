# Dashboard Trace + Azure DevOps (SESC RS)

Pipeline para dar visibilidade à gestora sobre status das demandas,
gargalos por área e necessidade de recursos, cruzando dados do Trace
(gestão de demandas) com o Azure DevOps (execução técnica).

**Objetivo principal: medir lead time — quanto tempo demora do pedido até a
entrega.** Volume por área e alocação de recursos são indicadores de apoio;
o indicador central é "quanto tempo uma requisição leva".

## Modelo do fluxo (confirmado com a equipe)

```
TRACE (backlog completo)              ← início real da espera; muitas
   │                                    requisições nunca chegam a ser
   │                                    priorizadas
   ├── priorização do comitê ──► Prioridades_do_Comite.xlsx (planilha manual)
   │        │                          "entra na planilha" = saiu do backlog,
   │        │                          começou a fase de análise
   │        ▼
   │     Azure DevOps (atendimento iniciado)
   │        ▲
   └── incidente (pula o comitê) ──────┘   incidentes vão direto para o
                                            atendimento, sem passar pela
                                            planilha de priorização
```

Consequência prática: **o Azure DevOps não é o backlog completo** — só
contém o que já teve atendimento iniciado (via priorização do comitê OU
por ser incidente). O volume real de demanda represada só existe no Trace.

**Confirmado com o NTI: a API do Trace não está disponível por enquanto.**
Os dados do Trace vão chegar por **CSV exportado manualmente**, não por
integração automática — ver seção "Importação do Trace (CSV)" abaixo. O
export real já traz `Data/Hora de Criação` (quando a demanda entrou no
backlog) e `Tempo no Estado (Dias)` (quanto tempo está no status atual,
calculado pelo próprio Trace) — dá pra medir "há quanto tempo essa
demanda existe" e "está travada há quanto tempo", mas não o tempo de
**cada etapa** (backlog → priorização → análise → dev → publicação): pra
isso precisaríamos de histórico de mudanças de status, que um export
pontual em CSV não traz (é uma foto do estado atual, não um histórico).
Reavaliar se/quando a API for liberada.

## Status

- [x] Extração Azure DevOps (`extract/extract_azure_devops.py`)
- [x] Importação Trace via CSV (`extract/extract_trace.py`) — API não
      disponível (confirmado pelo NTI); mapeamento de colunas confirmado
      com um export real (376 demandas), inclui vínculo nativo com o
      Azure DevOps, ver seção abaixo
- [x] Cruzamento (`transform/cross_reference.py`) — funciona em modo parcial
      (só Azure DevOps) ou só-manual (sem nenhuma API) até a extração do
      Trace ficar pronta
- [x] Painel web dos analistas (Airtable + `extract/extract_airtable.py`) —
      previsão de análise e histórico de observações atualizados ao vivo,
      substitui a edição manual do Excel para quem usa o painel
- [x] Informações manuais legadas (`data/manual/informacoes_manuais.xlsx`) —
      usado só como fallback se o Airtable não estiver configurado
- [x] Indicador de chamados parados 30+ dias no mesmo status
- [x] Esboço das páginas do relatório (`powerbi/esboco_relatorio.html`)
- [ ] Métrica de lead time completa (por etapa) — precisaria de histórico
      de status, que a API não vai trazer nem o CSV traz; só dá pra medir
      tempo total (abertura → conclusão) com o que temos hoje
- [ ] Dashboard Power BI real (montar em cima do esboço, com dados de verdade)

## Estrutura

```
extract/       -> scripts que buscam dados brutos (Trace, Azure DevOps, Airtable)
transform/     -> cruza os dados e gera métricas (gargalos, SLA, alocação)
data/raw/      -> saída bruta de cada extração (não versionar dados reais)
data/manual/   -> planilha legada (fallback, ver seção "Painel dos analistas")
data/processed/-> dataset final e resumos, prontos para o Power BI
powerbi/       -> esboço (wireframe) das páginas do relatório — abrir
                   esboco_relatorio.html no navegador
painel-analistas.html -> painel web dos analistas (publicado como Artifact,
                   grava no Airtable — ver seção "Painel dos analistas")
```

## Como rodar

```bash
pip install -r requirements.txt
cp .env.example .env   # preencher com as credenciais reais
python extract/extract_azure_devops.py
python extract/extract_airtable.py     # itens + observações do painel dos analistas
python extract/extract_trace.py        # lê data/manual/trace_export.csv (ver seção abaixo)
python transform/cross_reference.py
```

Isso gera:
- `data/processed/dataset_final.csv` — dataset detalhado, já com as colunas
  `dias_no_status_atual` / `parado_30_dias` e os campos manuais anexados
  (quando o id bate com o item do painel)
- `data/processed/resumo_por_area.csv` — métricas agregadas por área
  (volume aberto/concluído, horas restantes/apropriadas, chamados parados
  30+ dias) para identificar gargalos
- `data/processed/resumo_por_sigla.csv` — volume de itens e previsões
  vencidas por sigla interna (NEF, NAD, GED, NUGE, GEL, GEC...)
- `data/processed/historico_observacoes.csv` — todas as observações
  registradas no painel, uma linha por observação (mais recente primeiro)
- `data/processed/observacoes_area.csv` / `pedidos_recurso.csv` — legado,
  só aparecem se vierem preenchidos no `.xlsx` antigo

## Segurança

- **Nunca commitar o `.env`** — é onde ficam os tokens reais
  (`AZDO_PAT`, `AIRTABLE_PAT`). O `.gitignore` já bloqueia isso, mas vale
  conferir antes do primeiro `git add`, principalmente se o projeto for
  copiado manualmente pra outro lugar.
- `data/raw/` e `data/processed/` também são ignorados pelo git — são
  saída do pipeline, não código, e podem conter dados internos.
- O `AIRTABLE_PAT` é **diferente** da conexão OAuth usada dentro do
  Claude — é uma credencial própria, gerada em airtable.com. Se alguém
  sair da equipe, revogar o token dela em airtable.com/create/tokens
  (a conexão OAuth do Claude não precisa de ação separada, já que não é
  compartilhada entre pessoas).

## Painel dos analistas (Airtable) — fonte ao vivo

Os analistas atualizam previsão de análise e registram observações por um
painel web (`painel-analistas.html`, publicado como Artifact),
que grava direto numa base do Airtable — não editam planilha nenhuma.

- **Base:** "Painel de Análises - Comitê SESC" (`app5DmsthrcOlJluK`)
  - Tabela **Itens**: Prioridade, Analista, ID, Sigla, Descrição, Ciclo,
    Status, Previsão de Análise — um registro por item (sem IDs múltiplos
    por célula, diferente da planilha antiga).
  - Tabela **Observacoes**: histórico de observações por item (`ID_Item`,
    Autor, Data, Texto) — várias linhas por item, nunca sobrescreve.
- **Extração:** `extract/extract_airtable.py` puxa as duas tabelas via API
  REST do Airtable (precisa de `AIRTABLE_PAT` — token pessoal gerado em
  airtable.com/create/tokens, **diferente** da conexão OAuth usada dentro
  do Claude; escopo `data.records:read` e acesso à base acima).
- **Prioridade da fonte:** `prepare_itens_refinados()` em
  `transform/cross_reference.py` usa o Airtable quando
  `data/raw/airtable_itens_latest.csv` existe; só cai para o
  `.xlsx` legado (`data/manual/informacoes_manuais.xlsx`) se esse CSV não
  existir. As abas `Observacoes_Area`/`Pedidos_Recurso` do `.xlsx` seguem
  sendo a única fonte para esses dois relatórios (sem equivalente no
  Airtable ainda).

**Confirmado com a equipe:** a coluna `Sigla` (NEF, NAD, GED, NUGE, GEL,
GEC, MKT) é uma classificação própria, não corresponde à área/destino do
Trace nem do Azure DevOps. Por isso é tratada como dimensão separada — não
é somada com `resumo_por_area.csv` — e tem seu próprio resumo em
`resumo_por_sigla.csv` (volume por sigla + quantos itens estão com a
previsão de análise vencida, ver regra abaixo).

**Regra de previsão vencida:** só conta como vencido quem ainda está
literalmente em `Em análise` / `A fazer` / `Em analise/Desenvolvimento`
depois do prazo — quem já avançou para desenvolvimento/teste/fila deixou a
análise pra trás, no prazo ou não, e não entra nessa conta (`ANALISE_EM_ANDAMENTO_STATES`
em `transform/cross_reference.py`).

## Importação do Trace (CSV)

Como a API não está disponível, `extract/extract_trace.py` lê um CSV
exportado manualmente do Trace (padrão: `data/manual/trace_export.csv`,
configurável via `TRACE_CSV_PATH`) em vez de chamar a API.

**Mapeamento confirmado com um export real** ("Demandas_20.csv", 376
linhas). A primeira linha do export é um título ("Demandas"), o cabeçalho
de verdade fica na segunda — por isso `SKIP_ROWS = 1` no topo do script.
Colunas mapeadas:

| Coluna no export do Trace | Campo normalizado |
|---|---|
| Id | `id_demanda` |
| Título | `titulo` |
| Módulo: | `area` |
| Unidade Organizacional | `unidade_organizacional` |
| Estado | `status` |
| Tipo | `tipo` (Backlog / Incidente NTI / Requisição NTI) |
| Responsável Atendimento | `responsavel` |
| Solicitante | `solicitante` |
| Data/Hora de Criação | `data_abertura` |
| Data da Alteração | `data_ultima_alteracao` |
| Tempo no Estado (Dias) | `dias_no_status_atual` |
| ID User Story: | `azdo_user_story_id` |
| Status User Story | `status_user_story` |

Esse export **não tem data de conclusão, SLA nem horas apropriadas** —
parece cobrir só demandas em aberto (nenhum valor de "Estado" observado
até agora indica concluído; `TRACE_DONE_STATES` em `cross_reference.py`
fica pronto pra quando um export com demandas finalizadas aparecer).

Se um export futuro vier com colunas diferentes, o script **para e
mostra** exatamente o que esperava vs. o que encontrou — não gera dado
errado silenciosamente.

## Chamados parados 30+ dias no mesmo status

**Não precisa mais calcular pro Trace** — o próprio export já traz
`Tempo no Estado (Dias)` pronto (coluna `dias_no_status_atual`), então
`parado_30_dias` é só comparar com o limite. Pro Azure DevOps continua
calculado a partir de `data_ultima_alteracao`. Limite configurável em
`DIAS_LIMITE_PARADO` no topo de `transform/cross_reference.py`.

**Números reais do primeiro export** (376 demandas): 55% estão paradas
30+ dias no status atual (mediana de 46 dias, média de 229 — bem puxada
por alguns casos extremos). Boa parte desse volume é `Backlog` (esperado
ficar parado enquanto aguarda priorização) — filtrando só quem está
`Atendendo`, cai pra 41 de 132 (31%), o que é uma leitura mais justa de
"gargalo de verdade" vs. fila normal.

## Vínculo Trace <-> Azure DevOps

**O vínculo real vem do lado do Trace**, não do Azure DevOps: a coluna
"ID User Story:" no export aponta pro id do work item — nativo do Trace,
não precisa criar campo customizado nenhum. Confirmado com um export real:
126 de 376 demandas (33%) já têm esse vínculo preenchido.

Esse campo às vezes vem "sujo" — mais de um id na mesma célula (vírgula
ou ponto e vírgula), às vezes com texto extra colado (ex:
`"36197 - PENDENTE DEFINIÇÕES - ALMOX VIRTUAL"`, `"Spike 613621"`). O
extrator lida com isso: extrai todos os números de 4 a 6 dígitos da
célula e gera uma linha por vínculo.

`dataset_final()` em `transform/cross_reference.py` tenta esse vínculo
primeiro (`trace["azdo_user_story_id"]` == `azdo["id"]`); só cai pro
método antigo (campo customizado `AZDO_TRACE_LINK_FIELD` do lado do Azure
DevOps) se o Trace não tiver o vínculo preenchido. Testado de ponta a
ponta com os dados reais dos dois exports — o cruzamento encontra os
mesmos itens dos dois lados corretamente.

## Backend Oracle (substitui o Airtable) — `backend/`

O SESC vai disponibilizar hospedagem própria (Oracle + servidor de
aplicação), então o painel dos analistas pode deixar de depender do
Airtable/Claude Artifact e virar uma aplicação web hospedada por eles,
falando direto com o banco deles.

**Arquitetura:**
- `backend/app/` — API FastAPI (`main.py` expõe os endpoints, `repo.py`
  tem as queries, `db.py` abre a conexão via `python-oracledb` em modo
  *thin* — não precisa instalar Oracle Instant Client nem local nem no
  servidor de produção).
- `backend/schema.sql` — DDL das tabelas `itens` e `observacoes`,
  equivalentes às duas tabelas do Airtable de hoje. Diferença importante:
  "compromisso" agora é campo de verdade (`is_compromisso`, `resolvido`,
  `resolvido_em`, `resolvido_por`), não a convenção de texto que o painel
  em Airtable precisou usar por falta de acesso pra alterar o schema.
- `docker-compose.yml` — sobe um Oracle local (imagem `gvenzl/oracle-free`,
  gratuita, comunidade) + a API, só pra desenvolvimento e teste.
- `backend/frontend/index.html` — o painel dos analistas reescrito pra
  falar com esta API via `fetch()` (mesmo visual/fluxo do
  `painel-analistas.html` da raiz do projeto, só troca a camada de dados:
  Airtable/`window.claude.mcp` → HTTP direto). O FastAPI serve este
  arquivo na mesma origem da API (`main.py`, mount no final), então não
  tem problema de CORS. **Este é o painel do futuro backend** — o
  `painel-analistas.html` na raiz do projeto continua sendo o que está
  publicado e em uso pelos analistas hoje (Airtable), até o backend Oracle
  ser validado e for a hora de migrar de verdade.

**Rodando local (zero setup, sem Docker/conta/nada — modo padrão):**
```
cd backend
pip install -r requirements.txt
python _dev_sqlite_server.py
```
Abre em `http://localhost:8000/` — já sobe com alguns itens de exemplo
(SQLite em `backend/data/painel.db`, criado automaticamente, dados
persistem entre execuções). Pra rodar só a API, sem os itens de exemplo:
`DB_BACKEND=sqlite uvicorn app.main:app --reload`.

**Rodando contra Oracle (produção, ou um Oracle de teste real):**
```
cd backend
cp .env.example .env
# editar .env: DB_BACKEND=oracle + ORACLE_DSN/ORACLE_USER/ORACLE_PASSWORD
cd ..
docker compose up --build   # ou aponte direto pra um Oracle já existente
```
A API sobe em `http://localhost:8000` (docs interativas em `/docs`). Com
Docker, o schema é criado automaticamente na primeira subida do container
Oracle; apontando pra um Oracle já existente, rodar `backend/schema.sql`
uma vez, manualmente, conectado no schema certo.

`repo.py` escolhe a implementação certa (`repo_sqlite.py` ou
`repo_oracle.py`) pela variável `DB_BACKEND` — o resto do backend
(`main.py`, o painel) não muda entre um modo e outro.

**Endpoints:**
| Rota | O que faz |
|---|---|
| `GET /api/itens?analista=Larissa` | lista as demandas do analista |
| `PATCH /api/itens/{id_demanda}` | atualiza status/previsão |
| `GET /api/itens/{id_demanda}/observacoes` | histórico do item |
| `POST /api/itens/{id_demanda}/observacoes` | nova observação (com `is_compromisso`) |
| `POST /api/observacoes/{id}/resolver` | marca compromisso como concluído |
| `GET /api/compromissos?analista=Larissa` | compromissos abertos do analista, já agregados |

**Testado nesta sessão (três camadas):**
1. `backend/test_api_smoke.py` — 12 checks das rotas/validação/serialização
   da API, contra um repositório mockado.
2. `backend/test_sql_logic_sqlite.py` — 19 checks executando o **SQL real**
   de `repo.py` (mesmas queries, só adaptando sintaxe Oracle→SQLite) contra
   um banco de verdade em memória. Pegou e corrigiu um bug real: o
   `resolver_compromisso` deixava resolver o mesmo compromisso duas vezes
   porque a query só checava `is_compromisso = 'S'`, faltava
   `AND resolvido = 'N'`.
3. `backend/test_frontend_e2e.py` — sobe o FastAPI de verdade (repositório
   fake, ver `backend/_dev_fake_server.py`) e dirige um navegador de
   verdade (Playwright) pelo fluxo completo do `backend/frontend/index.html`
   via `fetch()` real: selecionar analista, editar status inline,
   registrar observação com compromisso, resolver compromisso. Pegou e
   corrigiu 2 bugs reais do frontend: uma tag `<script>` duplicada e um
   comentário que continha o texto literal `</script>`, ambos fechando a
   tag de script mais cedo pro parser do navegador e quebrando a página
   inteira silenciosamente.
4. O mesmo fluxo do item 3, mas contra o `repo_sqlite.py` **real** (não
   mock) via `_dev_sqlite_server.py` — servidor real, banco real (arquivo),
   navegador real, `fetch()` real, ponta a ponta. Confirma que o modo
   "zero setup" funciona de verdade, hoje, sem depender de Docker, Oracle
   Cloud ou qualquer cadastro.

**O que não deu pra testar nesta sessão:** contra o Oracle de verdade.
Tentei subir `docker compose up` — o daemon Docker chegou a rodar, mas o
ambiente bloqueia por política de rede qualquer download de camada de
imagem de container (testado Docker Hub, GHCR, Quay, registro da Oracle:
todos batem em 403 no proxy da sandbox — é bloqueio categórico de CDN de
blob binário, não específico do Oracle). Sem conseguir rodar o container,
fiz o que dava pra fazer sem ele:
- Validação via SQLite (`test_sql_logic_sqlite.py`) — pega bugs de
  lógica/coluna/join, já achou e corrigiu um real (ver acima).
- Li a documentação oficial da imagem `gvenzl/oracle-free` (texto, não
  bloqueado) e achei um bug de infraestrutura que só apareceria rodando:
  os scripts em `/container-entrypoint-initdb.d/` executam conectados como
  **SYS** no banco raiz, não no schema da aplicação — se eu tivesse
  montado o `schema.sql` direto ali, as tabelas teriam sido criadas no
  lugar errado. Corrigido: `schema.sql` continua puro (sem credenciais,
  pra rodar em produção já conectado no schema certo) e criei
  `backend/docker-init.sql`, que só é usado pelo Docker local — ele
  conecta no schema `painel_demandas` e só depois inclui o `schema.sql`
  de verdade via `@`. Também confirmei que o usuário criado por
  `APP_USER` recebe `GRANT CONNECT, RESOURCE`, que cobre todos os
  privilégios que o `schema.sql` precisa (tabela, sequence, trigger,
  índice).

O que ainda não dá pra confirmar sem rodar de verdade: sintaxe específica
do Oracle no `RETURNING ... INTO` e nos tipos exatos (`CHAR(1) CHECK`).
**Antes de considerar isso pronto**, precisa validar contra um Oracle de
verdade, por um destes caminhos:
1. **Oracle Cloud Always Free** — criar uma conta gratuita em
   cloud.oracle.com e provisionar um banco Autonomous Database free tier.
   Não precisa de Docker nem de máquina própria: é só uma conexão de rede
   (`ORACLE_DSN`/usuário/senha), então dá pra validar direto de qualquer
   lugar com acesso à internet normal — inclusive de uma sessão como esta,
   sem o bloqueio de download de imagem que travou o Docker aqui.
2. Pedir ao NTI acesso a um Oracle de teste/homologação real desde já.
3. Rodar `docker compose up --build` numa máquina com Docker (sua ou do
   NTI).

**Migração pra produção:** só troca `ORACLE_DSN`, `ORACLE_USER` e
`ORACLE_PASSWORD` (no `.env` ou nas variáveis de ambiente do servidor)
pelas credenciais que o NTI passar — nenhum código muda. Rodar
`schema.sql` uma vez no schema/usuário de produção antes do primeiro
deploy.

**Ainda falta:** validar `backend/frontend/index.html` e o schema contra
um Oracle de verdade (ver acima — Docker bloqueado nesta sessão) antes de
promover ele a substituto do painel publicado hoje.

## Próximos passos

1. Confirmar com a equipe a frequência do export manual do Trace (diário?
   semanal?) já que não é mais uma API ao vivo.
2. Ligar o Azure DevOps de verdade (API — `extract_azure_devops.py`), já
   que o CSV recebido foi só uma amostra pra validar o vínculo.
3. Confirmar com o NTI: versão do Oracle, se dá pra criar tabelas novas,
   e se existe ambiente de homologação separado da produção — depois
   rodar `docker compose up` (ver seção "Backend Oracle") numa máquina
   com Docker pra validar o `schema.sql` contra um Oracle de verdade
   antes de ir pra produção.
4. Reescrever o painel (`painel-analistas-v3.html`) pra chamar a API do
   backend (`fetch`) em vez do Airtable via Claude Artifact, assim que o
   backend estiver validado.
5. Decidir a ferramenta de agendamento (cron / Task Scheduler / Azure
   Function) para rodar o pipeline periodicamente.
6. Conectar o Power BI à pasta `data/processed/` (ou direto ao Oracle,
   uma vez que os dados processados estejam lá).
