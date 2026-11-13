# Resultado da execução SDD — investigação pública multibase

Data: 01/11/2026. Dataset de pesquisa: `public-study-87d04baa2e265aeb`.
Execução concluída: `public-study-87d04baa2e265aeb-eda-737cd888`.

**A integração pretendida não foi demonstrada com a representação testada.**
O desenvolvimento chegou à decisão T14 e preservou o impedimento previsto no
contrato. O classificador final para o compressor local não foi liberado.
Os dados públicos, análises e resultados estão persistidos e disponíveis para
auditoria e uso pela equipe. O Metabase permanece integralmente fora do escopo.

## O que foi efetivamente executado

1. Proteção da origem pública, inventário, licenças, aquisição limitada e hashes.
2. Importação e auditoria das quatro fontes acessíveis; triagem dos artigos e catálogo.
3. Canonização, preservação dos rótulos originais e definição dos grupos.
4. Reserva pública por grupos, antes da EDA orientada ao modelo.
5. Análise descritiva, distribuições, evolução, correlações pareadas e qualidade.
6. KMeans e Isolation Forest com sensibilidade e análise de dependências.
7. Experimentos fixos de Random Forest: SMART, KAIST e referências combinadas.
8. Comparação por fonte, investigação de diferenças de origem, hipótese de fusão
   e decisão de compatibilidade antes de produzir o dataset/modelo final.

Nenhuma leitura do protótipo foi usada nesses passos. Os 293 ciclos SMART da
partição `test` permaneceram fora da seleção e dos experimentos. A referência
reservada não foi aberta para tentar melhorar os resultados observados.

## Dados e persistência

| Fonte importada | Observações | Referência normal/anômalo | Grupos e limite |
| --- | ---: | --- | --- |
| SMART-PDM | 1.111 ciclos | 1.087 / 24 | 12 blocos semanais conectados; apenas quatro com falhas; ID físico desconhecido |
| KAIST | 288 janelas por canal | 192 / 96 | Duas cargas amostradas; canais/janelas de uma mesma carga ficam juntos |
| RWTH R290 | 195 condições pareadas | Indeterminada | Nove sessões; cinco condições RMS sem temperatura não foram preenchidas |
| ULT | 1.531 pontos térmicos | Indeterminada | Três freezers amostrados; evento de atendimento não identifica o início exato de falha |

Total: **3.125 observações**. Isso não representa 3.125 equipamentos ou ensaios
independentes. Há 1.399 observações com referência publicada e 1.726 com alvo
indeterminado; nenhum pseudorrótulo foi aceito.

Banco `compressor_ml_dev`, MariaDB local `127.0.0.1:3306`:

- 142.311 valores de características: 139.605 preparados e 2.706 saídas experimentais.
- 3.125 registros de rótulos e 3.125 membros do snapshot de pesquisa.
- 2.360 estatísticas, incluindo correlações, qualidade e métricas experimentais.
- 10.986 atribuições/escores de agrupamentos, separados por execução e configuração.
- 23 tabelas e 9 views; dump somente da estrutura restaurado em base independente.

A [conferência das sete consultas com conta leitora](../reports/research/public-study-87d04baa2e265aeb/database-handoff.json)
registra colunas, contagens e disponibilidade. Há quatro execuções falhas
preservadas no histórico, com estados terminais; nenhuma ficou em execução.
Saídas de modelos e clusters são resultados de pesquisa, sem status de previsão
externa ou rótulo verdadeiro de defeito.

## Protocolo congelado e suporte da avaliação

O protocolo está em
[`public-protocol.json`](../reports/research/public-study-87d04baa2e265aeb/public-protocol.json),
com [partições](../reports/research/public-study-87d04baa2e265aeb/partitions.csv) e
[política de rótulos](../reports/research/public-study-87d04baa2e265aeb/label-policy.json).
As associações também estão em `study_dataset_members`, vinculadas à versão
exata do rótulo. SHA-256 das partições:
`8a5cb9210d9760ae9999964b10a17e6ca21a615786121b5d3a7d942b70f5c67f`.

O seed inicial é 2026; o primeiro split que satisfez os mínimos de suporte foi
2029. Essa busca considerou classes/grupos, sem medir desempenho de modelos.
A tentativa inicial de exigir dois grupos positivos por papel era inviável
com apenas quatro blocos positivos e foi corrigida antes da modelagem.

| Fonte/papel | Observações | Grupos | Anômalas de referência |
| --- | ---: | ---: | ---: |
| SMART treino | 511 | 5 | 12 |
| SMART validação | 307 | 4 | 1 |
| SMART teste reservado | 293 | 3 | 11 |
| KAIST treino, 2 Nm | 144 | 1 | 48 |
| KAIST validação, 4 Nm | 144 | 1 | 48 |

RWTH e ULT tiveram grupos de desenvolvimento/validação próprios para pesquisa,
sem inventar alvo binário. KAIST não possui terceira carga reservada neste subset.
Uma única falha SMART na validação e uma única carga KAIST de validação limitam
fortemente a força das conclusões. A contagem de janelas não amplia a quantidade
de equipamentos independentes.

## Características e resultados supervisionados de viabilidade

Foram investigados skewness ajustada, curtose de Fisher sem viés e
`(máximo - mínimo) / desvio_padrão_populacional` da vibração temporal.
Esses momentos não dependem de uma escala positiva ou offset. Banda, montagem,
direção, frequência de captura e duração da análise ainda afetam seu significado.
SMART fornece estatísticas por ciclo; KAIST usa janelas não sobrepostas de cinco
segundos de um canal de vibração, com 128.000 amostras por janela.

Random Forest fixa: 150 árvores, profundidade 5, mínimo de três exemplos por folha,
`class_weight=balanced`, seed 2026, limiar 0,5. Fontes tiveram peso total igual,
com ponderação por grupo/registro. Esses parâmetros foram definidos antes dos
experimentos; não houve busca orientada pelos resultados da validação.

| Treino | Validação | TP / FN | FP / TN | Recall | Acurácia balanceada |
| --- | --- | --- | --- | ---: | ---: |
| SMART | SMART | 0 / 1 | 52 / 254 | 0% | 41,50% |
| SMART | KAIST | 0 / 48 | 0 / 96 | 0% | 50,00% |
| KAIST | KAIST | 45 / 3 | 1 / 95 | 93,75% | 96,35% |
| KAIST | SMART | 1 / 0 | 306 / 0 | 100% | 50,00% |
| SMART + KAIST | KAIST | 45 / 3 | 1 / 95 | 93,75% | 96,35% |
| SMART + KAIST | SMART | 0 / 1 | 0 / 306 | 0% | 50,00% |

O conjunto combinado atingiu 99,67% de acurácia simples na SMART classificando
tudo como normal. Isso perdeu o único caso anômalo e igualou o baseline majoritário.
Na KAIST, a combinação igualou os resultados do treino somente KAIST.
Os mínimos provisórios públicos foram atendidos na KAIST e reprovados na SMART.

Um classificador auxiliar distinguiu a origem SMART/KAIST com 99,78% de acurácia
na validação. A separação das distribuições é forte; combinar exemplos não
demonstrou transferência útil e generalizável nesse experimento. Os escopos dos
rótulos também diferem: manutenção do eletrodoméstico e defeito induzido em mancal.

As três Random Forests foram experimentos transitórios em memória. Não foram
publicadas como modelo final, não receberam status de congelamento externo e
não foram aplicadas às leituras do protótipo. Outras representações continuam
hipóteses de pesquisa; este resultado não autoriza prometer desempenho local.

## Exploração, agrupamentos e tentativa de ligação entre fontes

A EDA usa somente o papel `train`: quantis, dispersão, distribuições por referência,
blocos temporais/equipamentos, cobertura de sinais e Pearson/Spearman dentro
de observações genuinamente pareadas. Valores extremos foram mantidos e marcados
descritivamente por IQR. Quatro canais de corrente dos TDMS KAIST estavam vazios;
essa ausência foi preservada, sem virar entrada do classificador.

KMeans usou 2/3/4 grupos, `RobustScaler` por fonte e seed fixo, com perfis e
estabilidade ao excluir grupos. A estabilidade por exclusão não é estimável na
KAIST de treino com apenas uma carga. O relatório mantém essa ausência explícita.
O Isolation Forest foi examinado com contaminação de 1%, 5% e 10%:

| Fonte, somente desenvolvimento | Pontos destacados nas três configurações |
| --- | --- |
| SMART | 6 / 26 / 51 |
| KAIST | 2 / 8 / 15 |
| RWTH | 2 / 7 / 14 |
| ULT | 11 / 53 / 105 |

Esses números são sensíveis à configuração e não contam defeitos confirmados.
Nenhum cluster sobrescreveu referência ou rotulou automaticamente os 1.726
casos indeterminados. Sem uma referência independente adequada em RWTH/ULT,
a comparação “referência mais pseudorrótulos” ficou não aplicável; criar esses
rótulos para obter uma métrica não mediria a detecção de defeitos reais.

A hipótese de fusão também foi examinada por três associações teóricas de
quantis das marginais SMART/ULT: mesma ordem, ordem oposta e permutação.
As marginais admitem relações conflitantes. Esses coeficientes não são correlações
empíricas entre modalidades medidas juntas, não geraram linhas de treinamento
e estão identificados como `hypothetical_coupling_*`, com suporte conjunto zero.

## Decisão por fonte e compatibilidade local

| Relação | Decisão | Condição para avançar |
| --- | --- | --- |
| Momentos de vibração SMART/KAIST | Condicional para pesquisa | Comprovar relação de alvo/representação e melhorar evidência de validação por grupos |
| Temperatura/RMS na RWTH | Suportada dentro da própria fonte | Referência de defeito independente para converter condições em alvos binários |
| Temperaturas/eventos ULT | Condicional | Resolver associação temporal e referência de normalidade/falha na unidade escolhida |
| Rótulos SMART transferidos a RWTH/ULT | Não sustentada nesta rodada | Sinais de ligação e referências independentes para avaliar a transferência |
| Aplicar o candidato na API existente | Não sustentada pelo contrato disponível | Demonstrar que os sinais locais permitem reproduzir as entradas temporais |

A API oferece temperatura e um XYZ instantâneo por registro. Seu `rms` é
`sqrt((x²+y²+z²)/3)`, uma combinação espacial; não é RMS temporal de uma forma
de onda. Os offsets e o corte de ruído já foram aplicados. Não há contrato
confirmado de taxa/banda, limites de uma coleta ou posição térmica que permita
reproduzir as entradas públicas. Um agrupamento arbitrário de leituras não
restaura informação de alta frequência ausente.

O primeiro passo para retomar o objetivo local é obter a descrição do sinal já
produzido pelo dispositivo: código/configuração de aquisição, unidade, posição,
taxa e processamento. Se existir forma de onda já disponível, ela pode ser
exportada sem mudar a API. Com essa evidência, revisar a representação/base
candidata e repetir o estudo público com nova versão. Alteração de firmware ou
aquisição só deve ser proposta após demonstrar necessidade.

Uma entrega focada apenas no domínio público KAIST exigiria redução explícita
do objetivo. Seus resultados de bancada não devem ser apresentados como
validação do compressor de geladeira local. O objetivo original permanece aberto.

## Artefatos e verificações

[Relatório estruturado de viabilidade](../reports/research/public-study-87d04baa2e265aeb/public-study-87d04baa2e265aeb-eda-737cd888/feasibility.json),
[integração e ambiente](../reports/research/public-study-87d04baa2e265aeb/public-study-87d04baa2e265aeb-eda-737cd888/integration.json),
[qualidade](../reports/research/public-study-87d04baa2e265aeb/public-study-87d04baa2e265aeb-eda-737cd888/quality.json),
[agrupamentos](../reports/research/public-study-87d04baa2e265aeb/public-study-87d04baa2e265aeb-eda-737cd888/clusters.json),
[matriz de compatibilidade](../reports/research/public-study-87d04baa2e265aeb/public-study-87d04baa2e265aeb-eda-737cd888/compatibility.json)
e [hashes dos arquivos](../reports/research/public-study-87d04baa2e265aeb/public-study-87d04baa2e265aeb-eda-737cd888/report-manifest.json).

Oito gráficos foram exportados. A inspeção visual encontrou um rótulo vertical
cortado no gráfico SMART original; a
[revisão de renderização](../reports/research/public-study-87d04baa2e265aeb/figures-v2/smart_pdm-evolution.png)
corrige o texto e o eixo UTC. Valores, partições, modelos e resultados originais
ficaram preservados, sem refit. A receita está em `scripts/render_smart_evolution.py`.

Repetir a execução concluída devolveu o mesmo `run_id`, sem duplicar estatísticas
ou predições. O relatório de execução documenta as correções de software e os
checks. T15–T23 permanecem bloqueadas; T24 registra esta entrega parcial. Não
houve teste físico externo nem medição de acurácia no compressor do protótipo.
