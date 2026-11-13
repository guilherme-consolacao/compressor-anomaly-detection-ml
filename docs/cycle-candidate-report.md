# Random Forest multibase por ciclos — resultado público

## 1. Resultado e alcance

Existe uma **Random Forest multibase treinada, congelada e avaliada em teste
público reservado**. A versão é `cycle-freeze-8af6bb44817d037a836c`.
Isso conclui a candidata pública desta rodada, sem declarar validação no
compressor do protótipo. A integração local continua condicionada a uma entrada
que a API atual não registra: os limites reais de ciclos completos.

O [ensaio por grupos temporais](reading-measurements.md) usa uma entrada distinta,
com limites inferidos de pausas de telemetria. Seus escores são exploratórios.

O avanço veio de uma representação diferente das tentativas iniciais: duração
de um ciclo comparada ao histórico imediatamente anterior. Ela avalia o
comportamento operacional após o ciclo terminar. Não prevê vida útil, não
identifica o componente avariado e não recebe diretamente temperatura/vibração.
Essa mudança está explícita no SDD; não foi tratada como equivalência entre sinais.

## 2. Composição e significado da integração

Dataset congelado: `cycle-reference-8af6bb44817d037a836c`.

| Fonte | Casos efetivamente usados no treino | Entrada própria da fonte |
|---|---:|---|
| SMART-PDM | 782 ciclos | Duração relativa ao histórico causal |
| NIST | 294 experimentos agregados | Oito características térmicas/vazão verificadas |
| TRI-HP | 35 condições, excluindo o dia OC | As mesmas oito características térmicas/vazão |
| Total | 1.111 | Quatro descritores estatísticos comuns |

Na SMART, havia 818 ciclos conhecidos de desenvolvimento; 36 ficaram sem
histórico suficiente, todos normais segundo a referência publicada. Os 782
elegíveis incluem 13 positivos e 769 normais. Não foram usados os 293 ciclos
reservados nem as medições do protótipo para construir ou escolher a candidata.

As fontes se encontram em **quatro descritores de desvio relativo a referências
normais da própria fonte**: média da raridade de cauda, maior raridade,
fração de características raras e percentil de Isolation Forest. A Random Forest
é o classificador supervisionado final; Isolation Forest apenas prepara entradas.
Os descritores de treinamento são construídos fora do próprio grupo.

Essa associação é estatística. Não demonstra uma correlação física entre uma
temperatura NIST e uma duração SMART nunca medidas juntas. Cada observação
continua identificada por origem e unidade. Nenhuma temperatura foi inventada
para uma geladeira SMART, nem vibração atribuída a uma condição TRI sem medição.
Não foram aceitos pseudorrótulos binários. As referências originais foram mantidas.

Referências SMART descrevem mau funcionamento do eletrodoméstico informado
pelos técnicos. Referências NIST/TRI descrevem condições de falha experimental
de sistemas de refrigeração. Não significam todas o mesmo defeito do compressor.
Diferenças de dimensionalidade também podem revelar a origem dos descritores;
os controles não eliminam toda possibilidade de atalho de domínio.

## 3. Confirmação antes do teste reservado

O protocolo `transfer-round8-confirmation.json` foi registrado antes da nova
comparação. Execução: `temporal-round8-9492770bdefcfd8c0fcd`.

Foram usados os três folds fixos por grupos SMART. Calibração e limiar ajustado
usaram previsões internas produzidas por grupos ausentes do respectivo ajuste;
o grupo externo não participou dessas decisões. Foram comparados RF âncora,
SMART/TRI, SMART/NIST/TRI e três embaralhamentos de rótulos por fonte.

| Comparação, limiar bruto fixo 0,5 | TP / FN | FP / TN | Recall | Average precision |
|---|---|---|---:|---:|
| SMART, folha 10 | 10 / 3 | 14 / 755 | 76,92% | 0,4865 |
| SMART/TRI | 12 / 1 | 44 / 725 | 92,31% | 0,3986 |
| SMART/NIST/TRI | 12 / 1 | 47 / 722 | 92,31% | 0,5325 |
| SMART/NIST/TRI, rótulos auxiliares embaralhados | 2 / 11 | 12–26 / 743–757 | 15,38% | 0,1616–0,2567 |

O ajuste interno de limiar não melhorou esse desenho: a variante com três fontes
detectou oito de 13 positivos nessa comparação. A regra final permaneceu em
0,5 no escore bruto, sem consultar o teste reservado. A configuração de três
fontes cumpriu os critérios de discriminação e teve Brier bruto ligeiramente
menor que a variante de duas fontes, conforme a regra de seleção prévia.
Os controles apoiam utilidade dos rótulos auxiliares neste experimento;
não provam uma assinatura física universal de falha.

## 4. Teste reservado, executado uma vez

Execução: `cycle-test-9446332f4eb72f0bb4de`. O modelo já estava congelado.
Os 293 ciclos SMART e o dia TRI OC agora são **evidência consumida**. Repetir o
comando devolve o relatório salvo. Não ajustar limiar, representação ou modelo
nesses resultados e depois chamá-los de novo teste independente.

| Fonte de teste | TP | FN | FP | TN | Observação |
|---|---:|---:|---:|---:|---|
| SMART-PDM | 10 | 1 | 21 | 252 | 284 ciclos elegíveis; nove recusas por contexto |
| TRI, condições OC | 1 | 1 | 0 | 0 | Duas condições no mesmo dia; sem normais nesse teste |
| Agregado | 11 | 2 | 21 | 252 | 286 casos elegíveis, dois grupos positivos |

Na SMART, recall foi **90,91%**, taxa de falsos positivos **7,69%**, precisão
**32,26%**, balanced accuracy **91,61%**, F1 **0,4762** e AP **0,7033**.
Dos 31 alertas SMART, 21 foram falsos positivos; isso deve permanecer visível.
A cobertura SMART foi 284/293 (**96,93%**). Nenhum positivo ficou entre as nove
recusas de início de histórico. Recusas não foram classificadas como normais.
O baseline sempre normal teria acurácia de 96,13%, mas recall zero e balanced
accuracy de 50%. A acurácia de 92,25% do modelo não foi usada isoladamente para
aprovação: o objetivo inclui detectar a classe rara e limitar falsos alertas.

O agregado passou os limites de protótipo registrados antes dos experimentos:
recall **84,62%**, balanced accuracy **88,46%**, FPR **7,69%**, AP **0,7076**.
O desempenho TRI foi parcial: apenas uma de duas condições foi detectada.
Não é possível estimar FPR TRI sem casos normais reservados nessa fonte.

Há somente um grupo positivo SMART no teste. O segundo grupo positivo é o dia
TRI, com equipamento e modalidade distintos. Isso não equivale a dois
compressores domésticos independentes. O bootstrap descritivo por quatro grupos
deu intervalos amplos: recall 50–90,91% e FPR 0–20,83%. Não sustenta garantia
para qualquer geladeira ou compressor.

## 5. Escore e probabilidade

O alerta usa o **escore bruto da Random Forest**, limiar 0,5. Separadamente, foi
persistido um mapeamento sigmoide experimental ajustado em escores SMART de
desenvolvimento fora de grupo. O limiar não foi alterado por esse mapeamento.

No teste SMART, Brier do mapeamento foi **0,02808**, contra **0,03772** da
prevalência constante de treino; log loss **0,09676**, contra **0,17480**.
Isso não basta para anunciar probabilidade de defeito bem calibrada: alguns
ajustes internos tinham só dois positivos. Na faixa de probabilidade 0,25–0,50,
os quatro casos eram positivos, mostrando grande incerteza e subestimação local.
O JSON usa `experimental_reference_probability` e informa suporte limitado.
Não aplicar esse mapeamento como probabilidade física de falha no protótipo/TRI.

## 6. Contrato de ciclos e uso local

Para cada ciclo: `cycle_id`, `equipment_id`, `started_at`, `ended_at`,
`closed: true` e `boundary_evidence`. Horários precisam de fuso explícito.
O encerramento deve ter sido observado. Um pacote HTTP ou lote não comprova
que o compressor completou um ciclo.

O cálculo usa a mediana dos **até dez ciclos anteriores**, com mínimo de três,
do mesmo equipamento/grupo. O ciclo atual, futuros e rótulos não definem a
mediana. Sobreposição ou intervalo maior que 12 horas reinicia o histórico.
Início sem suporte gera `insufficient_context`, nunca classe normal automática.
O modelo não consegue, por esse contrato, avaliar um ciclo que ainda não terminou.

A API conhecida recebe temperatura e três eixos instantâneos, corrige offsets
fixos e zera componentes abaixo de um deadband de 0,01 em unidade não confirmada.
Seu RMS é espacial/instantâneo. Não há firmware no repositório inspecionado nem
limites reais de ciclo nesse POST. Coeficientes locais não foram copiados para
o treinamento. A menor alternativa proposta é registrar os limites por observação
do operador, sem alterar ESP32/API. **Essa rotina ainda precisa ser confirmada.**

O [protocolo prospectivo](../config/external-cycle-protocol.json) define
referência independente, metas, abstinências e decisões parciais. O histórico
anteriormente explorado não vira teste prospectivo intocado. Se houver só
normalidade confirmada, o teste será parcial e não medirá recall de defeitos.

## 7. Artefatos e operação

- [Manifesto congelado](../reports/research/cycle-freeze-8af6bb44817d037a836c/manifest.json).
- [Teste reservado](../reports/research/cycle-freeze-8af6bb44817d037a836c/public-test/summary.json).
- Artefato local: `models/cycle-freeze-8af6bb44817d037a836c.joblib`.
- SHA-256: `5a44da31f348a5a28b359f321d7c57e734963c112984762186c4a8ae30ca141f`.
- Entradas congeladas: SHA-256 `811057f3b9be6246f4d6c36183cebcface3d2b9a37c383e2a176220142919401`.
- Contrato relacional: `cycle-context-normality-v1-8af6bb44817d`.

Treino, observações agregadas, referências, quatro entradas por caso, composição
do dataset, registro de modelo e métricas estão no MariaDB local. Protocolos,
previsões completas e hashes estão registrados como artefatos auditáveis.
Escores canônicos de desenvolvimento também são materializados por observação
para os gráficos. São saídas de experimentos, não novos dados medidos de treino.

Inferência de software com uma fixture compatível:

```powershell
python -m compressor_anomaly_detection_ml predict-cycles --manifest reports/research/cycle-freeze-8af6bb44817d037a836c/manifest.json --cycles examples/completed-cycles.fixture.json
```

O comando valida hash, diretório confiável, versão de scikit-learn e contrato.
Carrega apenas joblib gerado localmente. A fixture é sintética e não prova
desempenho científico. Essa CLI de pesquisa retorna JSON; a campanha local e
seu registro em `study_external_*` continuam etapas separadas, ainda não executadas.
O backend legado não carrega esse artefato como se tivesse 20 características.

O [painel de resultados](entrega-pi4.md#previsão-de-temperatura-e-painel)
foi preparado depois da rodada de treinamento e teste público.
