# Banco local para pesquisa, auditoria e consumo pelos demais integrantes

Foi escolhido o MariaDB já instalado pelo XAMPP. O servidor consultado é
MariaDB 10.4.24, em `127.0.0.1:3306`; o banco exclusivo do projeto é
`compressor_ml_dev`. PostgreSQL 17 também estava ativo, mas não é necessário
introduzir outro dialeto/driver neste fluxo.

O banco local foi criado com **23 tabelas e 9 views**. A estrutura da aquisição
foi reproduzida sem importar o backup do protótipo. A única linha inicial é a
versão técnica em `study_schema_versions`. A execução pública posterior preencheu
as tabelas de pesquisa; contagens e versões atuais estão no
[relatório de desenvolvimento](../../docs/development-execution.md).
O servidor hospedado e os outros bancos da máquina não foram alterados.

## Arquivos e recriação

- `001_acquisition.sql`: cópia estrutural de `readings`.
- `../001_ml_sidecars_proposal.sql`: entidades legadas `ml_*`, aqui aplicadas
  somente ao banco local novo autorizado.
- `002_research.sql`: fontes, proveniência, pesquisa e validação externa.
- `003_metabase_views.sql`: views de consulta; nome preservado da preparação inicial.
- `004_reference_sources.sql`: migração aplicada ao banco inicial para distinguir
  artigos/catálogos de observações medidas; instalações novas já incluem a categoria.
- `research_queries.sql`: consultas somente de leitura para a equipe consumir
  inventário, rótulos, partições, estatísticas, clusters e predições experimentais.
- `schema.sql`: **dump somente da estrutura efetivamente instalada**, incluindo
  tabelas, índices, chaves, verificações e views; sem dados, contas ou senhas.

Versão atual: `002-reference-sources`. SHA-256 do dump atualizado e novamente
restaurado: `f9bece5a7bff02ba13ea09c9775408c6afab92ad0d3b4e11221c4db579310037`.
Os valores presentes no banco não estão incluídos nesse arquivo; distribuição
de um dump de dados permanece uma entrega posterior.

Para uma instalação local nova, com Python/driver já instalados e conta
administrativa disponível:

```powershell
python -m compressor_anomaly_detection_ml.database.local_setup init
```

O comando aceita somente loopback e o nome de desenvolvimento do projeto.
Recusa banco, contas do projeto ou `.env` existentes, sem resetar suas senhas.
Somente se a conta administrativa local exigir credenciais adicionais, definir
`LOCAL_MYSQL_ADMIN_USER` e `LOCAL_MYSQL_ADMIN_PASSWORD` no ambiente do processo.
Essas credenciais não são gravadas no projeto nem recebidas por argumento de
linha de comando.

As credenciais novas da aplicação e da conta de leitura foram geradas em `.env`,
ignorado pelo Git. A aplicação existente já lê os campos `DB_*`. Cada conexão
do backend usa UTC. O provisionamento é um comando administrativo explícito;
o início normal da aplicação não cria nem migra tabelas.

DDL no MariaDB não tem rollback completo. Se houver falha parcial no setup,
preservar `.env`, consultar o estado e corrigir a causa; não apagar bancos ou
repetir cegamente o comando. O helper mantém recusa sobre estrutura existente.

### Exportar uma estrutura atualizada

Escolher um arquivo de saída novo, revisar sua diferença e depois promover a
versão desejada. O exportador não substitui um arquivo existente.

```powershell
python -m compressor_anomaly_detection_ml.database.local_setup export --dump-exe mysqldump.exe --output database/local/schema-next.sql
```

O helper usa `--no-data`, não exporta contas e remove definers específicos e
qualificações do nome do banco nas views. Não há dump dos dados nesta entrega.

### Verificar o dump existente

```powershell
python -m compressor_anomaly_detection_ml.database.local_setup verify --client-exe mysql.exe --schema-file database/local/schema.sql
```

A verificação cria um banco `compressor_ml_schema_verify_<identificador>`,
restaura o SQL, compara tabelas/colunas/índices/FKs/CHECKs/views e verifica que
todas as tabelas restauradas estão vazias. As views também são executadas.
Somente esse banco novo de verificação é removido no final.

Para restaurar em outro ambiente, criar um banco **novo e vazio** e selecionar
esse destino no cliente antes de carregar `schema.sql`. O arquivo não cria
banco nem contas. As permissões e credenciais precisam ser configuradas
separadamente naquele ambiente. O arquivo é SQL executável confiável do projeto;
não usar o helper para restaurar dumps desconhecidos. A restauração já foi
verificada em MariaDB 10.4.24; outros servidores exigem sua própria verificação.

## Entidades e auditoria

| Tabelas | Informação preservada |
| --- | --- |
| `readings` | Contrato estrutural da aquisição local; ML só lê |
| `ml_*` | Medições legadas, modelos, importâncias, features e predições existentes |
| `study_sources` | Fonte, versão, origem pública/externa, licença e estado da inspeção |
| `study_artifacts` | Arquivo, origem, tamanho, caminho e hash |
| `study_runs` | Etapa, escopo, configuração, entradas, estado e erro da execução |
| `study_observations` | Exemplo preparado, unidade, condições, grupo e proveniência |
| `study_feature_values` | Valores numéricos, unidades e contrato de características |
| `study_labels` | Referência/derivado/indeterminado, versão, evidência e confiança |
| `study_datasets`, `study_dataset_members` | Snapshot, partição, grupo e rótulo explicitamente escolhido |
| `study_statistics`, `study_clusters` | Estatísticas, correlações, grupos e escores por execução |
| `study_external_cases`, `study_external_case_readings` | Caso de teste e vínculo às leituras locais |
| `study_external_ground_truth`, `study_external_predictions` | Referência real versionada e resposta do modelo por caso |
| `study_schema_versions` | Versão técnica do esquema |

O esquema evita associar um rótulo ao exemplo errado por FK composta. A avaliação
externa aponta explicitamente à versão de referência do mesmo caso. Uma revisão
posterior não altera silenciosamente o denominador da avaliação anterior.

Dados preparados e resultados necessários aos gráficos serão persistidos nas
etapas do SDD. Brutos muito grandes e modelos binários podem ficar em arquivos,
com identidade e integridade registradas no banco. O preenchimento e os escritores
do pipeline de pesquisa são trabalho de T26 e das tarefas produtoras, ainda
pendentes. O banco não aprende rótulos nem garante elegibilidade de treinamento:
a proteção contra dados externos continua obrigatória no pipeline de T01.

## Entrega dos dados aos demais integrantes

Nosso escopo é persistir os dados, manter a estrutura SQL e documentar seu
consumo. Instalação, conexão, configuração e uso do Metabase, incluindo perguntas,
gráficos e dashboards, são responsabilidade dos demais integrantes. Nenhuma
atividade nessa ferramenta é pendência de implementação deste backend.

Informações de acesso local para os responsáveis pelo consumo:

- SGBD: MariaDB, protocolo MySQL.
- Host/porta e banco: `127.0.0.1:3306`, `compressor_ml_dev`.
- Conta de leitura existente: `compressor_ml_metabase`, com somente SELECT.
- Credenciais e parâmetros locais: campos `METABASE_SOURCE_*` de `.env`,
  entregues aos responsáveis por canal apropriado; não compartilhar todo o
  arquivo nem a credencial de escrita da aplicação.
- Datas: UTC; qualquer conversão para exibição deve manter essa semântica.

Nomes de conta, variáveis e views da preparação anterior foram preservados para
evitar alterações desnecessárias. Eles não representam uma integração com a
ferramenta. O acesso preparado é local; disponibilização em outro host ou
ambiente deve ser combinada separadamente, sem ampliar exposição de rede
automaticamente.

### Views e informações disponíveis

| View | Dados consultáveis |
| --- | --- |
| `mb_study_inventory` | Fontes/versões, quantidade de exemplos e grupos independentes |
| `mb_study_feature_values` | Séries, histogramas, dispersões, distribuições e qualidade por característica |
| `mb_study_labels` | Contagens por classe, origem e status de rótulo, filtrando uma versão |
| `mb_study_statistics` | Médias, quantis, ausências e correlações por execução/condição |
| `mb_study_clusters` | Tamanho dos grupos e escores, sem interpretá-los automaticamente como defeito |
| `mb_study_dataset_members` | Composição por fonte/classe/partição com o rótulo congelado |
| `mb_ml_models` | Comparação de versões e métricas públicas; valores não estimáveis continuam NULL |
| `mb_external_predictions` | Casos, referências, predições, recusas e acertos por modelo/campanha |
| `mb_external_metrics` | TP/TN/FP/FN, acurácia e cobertura por campanha/modelo/versão de referência |

Sempre filtrar contrato de características, fonte, dataset/modelo e versões
pertinentes. A view de rótulos expõe o histórico; contar todas as versões como
novos exemplos distorceria o gráfico. Para composição congelada, preferir
`mb_study_dataset_members`, que já aponta ao rótulo escolhido naquele dataset.

As métricas externas contam somente predição classificada com referência
confirmada. Indeterminados e recusas ficam fora dos acertos/erros, com cobertura
informada separadamente. Calcular precisão, recall e taxa de falsos positivos
com `NULLIF` no denominador, a partir de TP/TN/FP/FN. Sem suporte de uma classe,
a métrica correspondente permanece não estimável.

As etapas de pesquisa preencherão essas entidades e resultados. A equipe de
visualização consumirá os registros disponibilizados; o backend não cria nem
opera dashboards.

## Verificações realizadas

- Testes de recusa de destino remoto, nome incorreto, configuração existente e
  SQL de exportação contendo dados/contas.
- Restauração real em banco novo com comparação estrutural completa.
- Fixtures artificiais somente em banco temporário: FKs, CHECKs, views, valores
  NULL, revisões de referência e denominadores da avaliação externa.
- Leitura com as contas locais e recusa de escrita/DDL indevido e de UPDATE em
  `readings` pelo ML. As credenciais nunca são impressas pelos testes.

As evidências de execução e comandos ficam em
[`docs/local-database-audit.md`](../../docs/local-database-audit.md).

Referência: [dump do MariaDB](https://mariadb.com/docs/server/clients-and-utilities/backup-restore-and-import-clients/mariadb-dump).
# Dados da candidata pública por ciclos

O snapshot atual contém 19.276 observações, 564.907 valores e 4.875 estatísticas.
O dataset `cycle-reference-8af6bb44817d037a836c` reúne 782 ciclos SMART,
294 experimentos NIST e 35 condições TRI, com quatro entradas por caso e rótulos
originais. Filtre dataset, contrato, modelo e execução antes de contar casos.

`study_feature_values` também contém 99.879 escores canônicos de desenvolvimento,
com `study_runs.stage='public_research_scores'`. Eles são **saídas experimentais**,
não novos sinais medidos nem probabilidade física de defeito. O identificador da
comparação está em `definition_json.model_id`; a fonte original continua ligada
por observação. Os demais hiperparâmetros e previsões completas ficam nos
artefatos registrados, sem escolher apenas as comparações com melhor resultado.

O contrato `frozen-test-score-de6dbc24bcab646d` expõe 856 valores derivados
dos 286 casos elegíveis do teste público congelado, com escore bruto, classe e
mapeamento experimental SMART quando aplicável. Não é campanha do protótipo.
Nove ciclos SMART sem histórico não foram contados como normais/acertos.

As 11 [consultas de pesquisa](research_queries.sql) foram verificadas com a conta
leitora. `study_statistics` contém métricas, suporte e comparações; as views e
o esquema não exigiram novo DDL nesta rodada. O dump estrutural continua válido.
Metabase segue sob responsabilidade dos demais integrantes.

[Relatório e limites da candidata](../../docs/cycle-candidate-report.md).
A documentação de preparação original abaixo permanece como referência histórica.
