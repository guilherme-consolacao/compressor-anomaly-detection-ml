# Exploração não supervisionada do backup

Foi executado um experimento offline nas 3.701 leituras do backup auditado.
O objetivo foi encontrar grupos de valores semelhantes e priorizar leituras
atípicas para investigação, sem criar rótulos de defeito.

Esta análise é por **leitura individual**. Não substitui o contrato de medição
completa da aplicação e não utiliza as 20 características por medição. Nenhum
modelo foi registrado no backend, nenhum resultado foi escrito no banco e
nenhuma alteração foi feita na API ou no pipeline supervisionado.

## Dados e processamento

- Origem: registros históricos da telemetria do protótipo.
- SHA-256 verificado: `a0817427315910d34aeafe66d8b20d2a73813c3a6300a00ba01d0df07d2ed789`.
- Entradas: `temperature`, `accel_x`, `accel_y`, `accel_z`.
- ID e horário ficaram fora das entradas do algoritmo.
- RMS ficou fora por ser determinado pelos três eixos; foi usado na descrição dos grupos.
- Escala: `StandardScaler`, ajustado ao histórico para esta exploração.
- Biblioteca utilizada: scikit-learn `1.9.1`, já instalada.
- Verificações executadas: hash do backup, contagem, IDs únicos, entradas
  numéricas finitas, tamanho e finitude dos escores e tamanho dos agrupamentos.

Não houve preenchimento de dados, reconstrução de ciclos, ajuste de calibração
ou definição de percentual conhecido de defeitos. Os algoritmos foram ajustados
e inspecionados no próprio histórico, sem teste de generalização em dados novos.

## Agrupamento com DBSCAN

[DBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html)
identifica regiões densas e deixa algumas observações fora dos grupos
(`cluster_id=-1`). Esse identificador não significa defeito comprovado.

Com `min_samples=20` e `eps=0.5`, em unidades padronizadas:

| Grupo estatístico | Leituras | RMS médio | Média do eixo Z |
| --- | ---: | ---: | ---: |
| 0 | 3.423 | 0,027402 | 0,002722 |
| 1 | 140 | 0,590865 | -1,023173 |
| 2 | 32 | 0,287067 | -0,496318 |
| Fora dos grupos | 106 | 0,415252 | -0,578438 |

Os grupos se distinguem principalmente por padrões dos eixos, com regiões
próximas de Z igual a zero, -0,5 e -1,0. Não foram chamados de normal, partida,
repouso ou defeito. Padrões podem refletir fenômenos físicos ou características
da aquisição; isso exige confrontar firmware, sensor e contexto operacional.

A sensibilidade ao parâmetro de distância foi verificada, sem escolher o melhor
resultado com base em rótulos que não existem:

| `eps` | Grupos | Leituras fora dos grupos |
| --- | ---: | ---: |
| 0,3 | 2 | 253 |
| 0,5 | 3 | 106 |
| 0,8 | 3 | 17 |

Essa variação impede tratar a contagem de pontos isolados como quantidade de
anomalias reais. Escala, distância, densidade, repetição de amostras e cobertura
do histórico influenciam o resultado. Um grupo grande também pode conter uma
condição indesejada frequente; o maior grupo não foi declarado normal.

## Priorização com Isolation Forest

[Isolation Forest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html)
foi ajustado com `n_estimators=200`, `random_state=42` e `n_jobs=1`.
Foi utilizado `-score_samples`: maior valor indica maior atipicidade neste modelo.
Esse escore não é probabilidade de defeito. Nenhum limiar operacional foi definido.

As primeiras cinco leituras no ranking foram:

| ID | Temperatura | RMS | Escore de atipicidade |
| --- | ---: | ---: | ---: |
| 118 | 71,3750 | 1,281182 | 0,732112 |
| 242 | 71,2500 | 1,281159 | 0,716560 |
| 2981 | 56,0625 | 1,289184 | 0,715437 |
| 1399 | 56,7500 | 1,288820 | 0,702682 |
| 903 | 62,0000 | 1,288820 | 0,696987 |

Esses são candidatos para revisão, não diagnósticos. O ranking não é apenas uma
ordenação por RMS: o algoritmo recebeu temperatura e os três eixos em conjunto.
Os resultados completos e os parâmetros foram mantidos localmente em
`.reference/unsupervised_exploration.json`, ignorado pelo Git.

## Como usar os resultados

O experimento mostra que é possível começar a exploração sem rótulos: agrupar
padrões, selecionar exemplos representativos e revisar os pontos mais diferentes
com o responsável pela aquisição. A confirmação independente pode depois gerar
rótulos documentados para o treinamento supervisionado.

Não se deve copiar os grupos ou o ranking para `rotulo_anomalia` e chamar isso de
verdade conhecida. Sem avaliação independente, não há medida de acurácia, recall
ou capacidade de identificar defeitos. Também não foram validados o limiar,
a estabilidade em outro dia/equipamento ou o comportamento em produção.

Esta abordagem não recupera amostras ausentes, não confirma a unidade dos eixos
e não resolve a baixa densidade temporal observada. Para classificar medições
completas no futuro, continua necessário identificar as coletas e confirmar a
amostragem. Um detector operacional exigirá outra validação, além desta exploração.
