# Execução do desenvolvimento SDD

Data inicial: 01/11/2026. Contrato: SDD 1.2.0. Esta área de trabalho não tem
commit da entrega; comandos, testes, versões de dados e hashes dos artefatos
identificam as execuções. Metabase permanece com os demais integrantes.

## T01 — proteção do desenvolvimento público

Tentativa 1. Implementados registro de fontes, verificação de proveniência
completa e comando `validate-public-data`, executado sem abrir conexão com o
banco da aquisição. A origem declarada é confrontada com o registro controlado
e a linhagem deve ser completa e acíclica. Ausência de origem, fonte externa,
fonte sintética, falta de licença, ancestrais ausentes e origem divergente são
recusados. A verificação não afirma descobrir forensicamente a origem de um
arquivo deliberadamente falsificado; a ingestão também deve verificar hashes.

Uma fixture externa renomeada para `data/public/renamed.json` foi recusada.
Outra fixture declarou origem pública para a fonte registrada como telemetria local e
também foi recusada. Descendentes de dados externos não podem entrar no caminho
público. Fontes reservadas podem constar do inventário sem que seus dados sejam
lidos ou usados no desenvolvimento.

`data/` e `reports/private/` estão ignorados, além de `.env`, brutos de referência
e binários já excluídos anteriormente. A exposição histórica ao backup continua
documentada em `spec.md` e nos relatórios antigos. Nenhum histórico local foi
consultado nesta execução de desenvolvimento público.

Verificação executada:

```powershell
python -m pytest tests/test_provenance.py tests/test_cli.py -q --basetemp=.pytest_cache/provenance-check
```

Resultado: **21 testes aprovados**. Ruff passou nos módulos e testes envolvidos.

## T26 — escritores relacionais

Implementado `ResearchRepository` para gravar entidades de pesquisa sem DDL.
Cada lote usa transação única e identidades estáveis. Uma versão igual é
reconhecida sem duplicação; alteração de conteúdo na mesma versão é recusada.
Rótulos e estatísticas usam chaves lógicas explícitas; gravações incompletas
sofrem rollback. Campos numéricos e JSON rejeitam valores não finitos.

O escopo é obrigatório por transação. Observações, valores, rótulos, grupos e
datasets públicos são verificados contra sua origem e execução. Manifestos de
observações e datasets requerem a proveniência de T01. Dados externos possuem
um caminho separado. A integração de cada etapa produtora permanece parte do
aceite da tarefa correspondente.

Verificação: cinco testes reais de roundtrip, idempotência, conflitos, rollback,
origem e terminalização passaram em bancos temporários locais. A fixture inicial
foi corrigida para obter o banco selecionado por `SELECT DATABASE()`.

## Infraestrutura e estrutura v2

T25/T27/T28 já estavam concluídas. A ingestão revelou que referências bibliográficas
precisavam de categoria distinta de dados medidos. Aplicada migração explícita
`004_reference_sources.sql`, exclusivamente em `compressor_ml_dev`.
Versão registrada: `002-reference-sources`. O CHECK inicial para novas instalações
também foi atualizado. Nenhuma leitura local foi importada.

Dump atual: 48.725 bytes, SHA-256
`f9bece5a7bff02ba13ea09c9775408c6afab92ad0d3b4e11221c4db579310037`.
Nova restauração real confirmou 23 tabelas, 9 views, colunas, índices, FKs e
CHECKs equivalentes, tabelas vazias e remoção somente da base temporária própria.
O dump inicial de 48.696 bytes permanece identificado na auditoria histórica;
o arquivo entregue atualmente é a versão acima.

## T02/T03/T05/T06 — aquisição, preparação e triagem

Execução de aquisição: `public-acquisition-20261101T130629769879`.
Identidade e versão de quatro provedores foram confrontadas com o registro.
Dez testes de aquisição cobrem limites, checksum, Range exato e ZIP seguro;
nove testes de importação cobrem chaves, valores e associações.

| Preparação concluída | Observações | Valores numéricos | Rótulos e limite |
| --- | ---: | ---: | --- |
| SMART-PDM `smart_pdm-prepare-3f5bc63bfd8ddbeb6c49` | 1.111 | 111.100 | 1.087 normais, 24 Malfunction, referência de manutenção do eletrodoméstico |
| RWTH `rwth_r290-prepare-2daf6e3f19b339730efc` | 195 | 9.360 | Indeterminados; carga experimental não é diagnóstico binário |
| ULT `ult_freezers-audit-20261101T132649030270` | 1.531 | 16.841 | Indeterminados; data de solicitação de reparo não é início da falha |

Os relatórios estão em `reports/research/<run_id>/`. Os arquivos originais,
licenças, URLs, tamanhos, CRCs e hashes estão em `study_artifacts` e nos manifestos.
Não se afirma ter conferido o hash do ZIP completo quando foram obtidos apenas
membros por Range. A leitura repetida da auditoria ULT retornou a versão concluída,
sem repetir inserções. Alterar seu significado exige revisão semântica nova.

A inspeção ULT confirmou licença CC0 nos dados, 46 eventos na planilha, quatro
eventos sem dados e modelos de compressores no CSV do provedor. Três logs foram
importados; não se inventou referência minuto a minuto. Artigos e catálogos
continuam `public_reference`. A [triagem](public-source-audit.md) e a
[atribuição](source-attribution.md) documentam contribuições e limites.

O cadastro possuía três sequências de mojibake escapadas em JSON. O diagnóstico
foi separado da exibição do terminal. Corrigidos apenas título/descrição das duas
fontes afetadas, no arquivo controlado e no banco local. O registro antes/depois
está em `reports/research/source-registry-encoding-correction.json`; medidas e
rótulos não mudaram. Esse relatório preserva propositalmente a grafia anterior.

## Verificações intermediárias

Regressão inicial: 263 aprovados, um ignorado e uma falha. A falha era um teste
de permissão que ainda esperava inventário vazio após a ingestão; a expectativa
foi corrigida para verificar a consulta sem exigir banco vazio.
Após corrigir o leitor para o MAT nativo e a fixture de permissão, os 24 testes
afetados passaram, incluindo testes reais do MariaDB.

O primeiro MAT real revelou um `Signal` struct, não a matriz ilustrativa inicial.
O parser foi corrigido e a fixture passou a reproduzir o layout encontrado.
Taxa de vibração medida no arquivo: 25.600 Hz. Exportação MKS, rótulo de exibição
`g` e fator de unidade são preservados; a escala absoluta fica não confirmada.
As estatísticas de forma testadas são invariantes a escala positiva e offset.

Build Python executado com sucesso, gerando wheel e sdist em `dist/`, ignorados
pelo Git. Os utilitários de pesquisa/provisionamento são executados a partir da
raiz do repositório e dependem de seus arquivos de configuração/SQL; o wheel
não é anunciado como distribuição autônoma das bases ou da infraestrutura.

A verificação do contrato local leu apenas o código da API. SHA-256 de
`main.py` do repositório da API:
`2fa9eae735de50e4dc9dc82223a9a1e2a1b7d3366586b817a72ef6e6c2c47e87`.
Não houve importação do módulo da API, conexão com o servidor hospedado ou
leitura da campanha externa para escolher características.

## T04 — amostra KAIST concluída

Aquisição `kaist-samples-20261101T131729739308`: quatro TDMS e quatro MAT,
duas cargas (2/4 Nm), condições Normal e BPFO_03. Auditoria concluída em
`kaist-audit-20261101T135438005363`: 288 janelas por canal e 2.304 valores.
O ensaio inicial detectou canais declarados sem amostras nos TDMS BPFO. A regra
foi corrigida para registrar ausência e manter os outros canais, sem criar zeros.
Oito testes do leitor passaram. Os quatro canais de corrente vazios permanecem
explicitamente ausentes; os modelos comparativos usam apenas vibração.

## T07–T14 — pesquisa pública concluída e impedimento registrado

Snapshot `public-study-87d04baa2e265aeb`; seed de split selecionado 2029, segundo
regra de suporte predefinida, sem consultar métricas. Partições persistidas por
grupo e rótulo escolhido. SMART possui 511/307/293 ciclos em treino/validação/teste.
Os 293 de teste ficaram reservados. KAIST mantém todos os canais/janelas de uma
carga juntos. Os mínimos por grupo foram definidos antes da modelagem, levando
em conta somente quatro blocos positivos SMART.

As duas primeiras execuções da EDA falharam antes de completar os experimentos:

1. A reflexão SQLAlchemy de DOUBLE do MariaDB usava `asdecimal=True`, devolvendo
   Decimal e podendo arredondar valores pequenos. Corrigido uma única vez no
   `ResearchRepository`, com roundtrip de `1/3` e `1e-14` e verificação de idempotência.
   Nenhuma alteração dos valores DOUBLE armazenados foi necessária.
2. O pandas materializou unidade ausente como NaN. Corrigida a apresentação para
   manter “unit unconfirmed”, com teste explícito para None, NaN e pd.NA.

Execução concluída: `public-study-87d04baa2e265aeb-eda-737cd888`.
Protocolo, entradas e parâmetros de modelagem foram mantidos nas correções.
Foram persistidas estatísticas, 24 execuções de métodos não supervisionados,
atribuições/escores e as saídas dos três modelos experimentais. O
[relatório de viabilidade](public-feasibility-report.md) contém as comparações
por origem e os limites do suporte.

Resultado do combinado: 45/48 janelas anômalas KAIST detectadas, com um falso
positivo; na SMART, o único ciclo anômalo de validação foi perdido, sem falsos
positivos. Os mínimos públicos falharam na SMART. A distinção de origem entre
as duas bases atingiu 99,78%. RWTH/ULT permaneceram sem pseudorrótulos aceitos.
Não foi autorizada a consolidação/modelagem final nem aberto o teste externo.

Os oito gráficos exportados foram inspecionados por amostragem. O gráfico SMART
de evolução tinha rótulo cortado; sua revisão `figures-v2` usa os mesmos IDs e
valores, com assert de associação à partição train. Foram preservados o gráfico
original, os hashes e todos os resultados científicos, sem repetir os modelos.

A repetição de `public_experiments` retornou a execução concluída, sem duplicar
resultados. Cadastro de fontes atualizado para `inspected` após as inspeções;
artigos continuam `public_reference`. O CHECK recusou uma tentativa de estado
não previsto, com rollback; a repetição usou o estado existente e registrou
antes/depois em `reports/research/source-inspection-completion.json`.

## Entrega dos dados e verificações finais

Estado do banco após execução: 3.125 observações, 142.311 valores, 3.125 rótulos,
3.125 membros de snapshot, 2.360 estatísticas e 10.986 atribuições/escores.
São 139.605 características preparadas e 2.706 valores de saídas experimentais.
Existem 34 execuções concluídas e quatro falhas preservadas; nenhuma permanece
em execução. [Conferência da conta leitora](../reports/research/public-study-87d04baa2e265aeb/database-handoff.json).

As sete consultas de `research_queries.sql` passaram com a conta leitora. O campo
de relógio local ULT é exposto pela consulta como DATETIME com semântica de zona
desconhecida, sem apresentá-lo como UTC. A correção de um ponto e vírgula dentro
de um rótulo textual permitiu a verificação sequencial dos exemplos SQL.
Metabase não foi instalado, conectado ou configurado.

Verificação final executada:

```powershell
python -c "import os,pytest; os.environ['LOCAL_MYSQL_INTEGRATION']='1'; raise SystemExit(pytest.main(['-q','--basetemp=.pytest_cache/final-delivery']))"
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
uv build --out-dir dist
```

Resultado: **268 testes aprovados, um opcional ignorado**, Ruff aprovado e 47
arquivos formatados. Wheel e sdist gerados com sucesso. O teste ignorado é o
opt-in do contrato MySQL legado; a integração MariaDB local foi executada.
A restauração real do dump atualizado foi novamente conferida com 23 tabelas e
9 views. Metadados e relatórios não contêm senhas; `.env`, brutos e binários
permanecem ignorados.

T01–T14 e T25–T28 concluídas; T15–T23 bloqueadas pelo resultado/contrato.
T24 conclui a documentação desta entrega parcial. O objetivo completo continua
aberto: não existe classificação validada do compressor local nem campanha
externa com referência real avaliada.

## Revisão SDD 1.3.0 — retomada autorizada

O usuário reafirmou o foco: aprofundar a descrição e as relações entre fontes,
usar SMART-PDM como âncora de referência e encontrar representação/base pública
consolidada para a Random Forest, com aplicação externa posterior. A comparação
com detector de normalidade é auxiliar, sem substituir esse objetivo.

Atualizados `spec.md`, `plan.md` e `tasks.md` para a versão 1.3.0, com RF-39 a
RF-46, T29–T31 e reabertura de T07–T14/T24. Preservados os resultados anteriores,
suas métricas, os protocolos executados e a reserva pública. Nova hipótese
reprovada deverá levar à próxima ligação/representação ou busca dirigida.

A decisão de integração pública foi separada da prontidão local. T20 prepara o
adaptador com candidata/fixtures antes de T19; congelamento e campanha externa
continuam exigindo compatibilidade e referência observada. A calibração será
avaliada com escopo, suporte e partições próprios, sem exigir acerto de 100% nem
chamar escore de atipicidade de probabilidade de defeito.

O próximo trabalho é T29, seguido de T30 e das tarefas reabertas. A atualização
documental não executou novos modelos, não alterou o banco e não representa
cumprimento dos critérios científicos acrescentados.
# Fechamento atual — SDD 1.4.0, 01/11/2026

Esta seção registra a rodada posterior; o restante do arquivo preserva a execução
anterior. [Relatório atual](cycle-candidate-report.md).

1. Fontes adicionais TRI/NIST, espectros RWTH, ondas SMART e controle de
   lavadoras foram adquiridos/auditados; fontes adicionais com lacunas ficaram
   fora do treino. As pontes e resultados negativos das rodadas 2–6 foram preservados.
2. Duração relativa ao histórico causal produziu uma candidata. A rodada 8
   confirmou comparações por grupos, calibração aninhada, limiar e permutações.
3. Dataset `cycle-reference-8af6bb44817d037a836c` e modelo
   `cycle-freeze-8af6bb44817d037a836c` foram congelados antes do teste reservado.
4. `cycle-test-9446332f4eb72f0bb4de`: SMART 10/11 positivos detectados,
   21/273 falsos positivos e nove recusas; TRI 1/2. Critérios agregados do
   protótipo cumpridos; desempenho local e probabilidade física não confirmados.
5. Pipeline/CLI por ciclos, fixture, checks de integridade e persistência
   pública foram concluídos. Limites reais dos ciclos locais e a campanha
   externa continuam pendentes; não foi alterado ESP32/API nem lida nova campanha.

Verificação final:

- `pytest`, `LOCAL_MYSQL_INTEGRATION=1`: **306 passed, 1 skipped**, 26,58 s.
  O skip é o opt-in legado de banco compartilhado; a integração local isolada passou.
- Ruff check aprovado. Dois ajustes de formatação sem mudança de comportamento
  foram aplicados; o check final aprovou os 86 arquivos.
- Build `uv build` aprovado, wheel e sdist gerados. A primeira tentativa no
  ambiente restrito falhou por DNS ao obter setuptools; repetição com acesso
  de rede autorizado concluiu o build.
- CLI com `examples/completed-cycles.fixture.json`: três recusas por início de
  histórico e uma classificação, sem dados de equipamento real.
- Reprodução a partir das entradas congeladas: escores públicos idênticos e
  **3.128 valores SMART da matriz de treino exatamente iguais aos do banco**.
  O joblib reserializado não ficou idêntico byte a byte; não foi promovido nem
  substituiu o artefato original, cujo SHA-256 permanece inalterado.
- MariaDB: 23 tabelas, nove views; 19.276 observações, 564.907 valores,
  4.875 estatísticas e 99.879 escores canônicos de pesquisa. As 11 consultas
  passaram na conta somente leitura. Zero linhas na aquisição `readings` local.
- As 64 execuções do snapshot incluem 60 concluídas e quatro falhas históricas
  preservadas; nenhuma execução ficou rodando.

Evidências adicionais no diretório do modelo: `reproduction-check.json` e
`database-handoff-check.json`. Dump estrutural permanece com SHA-256
`f9bece5a7bff02ba13ea09c9775408c6afab92ad0d3b4e11221c4db579310037`.

T18/T20 precisam de confirmação do procedimento local; T19/T21–T23 permanecem
abertas por dependência. Esta é entrega pública de pesquisa, não conclusão da
validação física. Nenhum dado externo entrou no desenvolvimento.
