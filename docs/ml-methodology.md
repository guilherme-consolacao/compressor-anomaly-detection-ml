# Metodologia de aprendizado de máquina

O classificador binário recebe uma linha por medição completa e encerrada.
`0` representa normal e `1` representa anômala. Leituras individuais não são
exemplos independentes de treinamento. O alvo é comportamento observado; o
modelo não identifica peças, causas físicas ou data de falha.

## Contrato dos sinais e qualidade

A aquisição atual persiste `temperature`, `rms`, `accel_x`, `accel_y`, `accel_z`
na tabela `readings`. O adaptador fornece esses valores ao mesmo extrator usado
no treinamento e na inferência. Os eixos já estão corrigidos por offset e
supressão de ruído pela API; o ML não repete esse tratamento.

O sinal `rms` é `sqrt((x²+y²+z²)/3)` para cada pacote recebido. É uma combinação
espacial instantânea, e não RMS temporal sobre uma janela. Sua definição é
`api-calibrated-spatial-rms-v1`, e o processamento estatístico inicial é
`spatial-rms-stats-v1`. A unidade de aceleração precisa estar explicitamente
confirmada como `g` em cada medição. Não há inferência de unidade a partir dos
valores. A disponibilidade real dessa unidade ainda depende do firmware.

Cada medição exige identidade, equipamento, limites temporais, contagem esperada
e IDs explícitos das leituras. Não são geradas janelas de 15 segundos pelo ML.
A duração real pode variar. Medições abertas não são elegíveis. Nenhum rótulo ou
estado do compressor é inferido a partir de vibração.

O extrator verifica campos, tipos numéricos, valores finitos, timestamps e
consistência com os limites da medição. Leituras são ordenadas por timestamp e
ID para determinismo. Empates de horário são possíveis porque o SQL da API usa
`TIMESTAMP` com resolução de segundos. O horário persistido é de inserção no
banco, não um instante comprovado de captura. Configuração de fuso deve ser
explícita quando o driver retornar horários sem offset.

São exigidas ao menos duas leituras válidas por série. Esse mínimo protege a
implementação; não comprova adequação científica para vibração. Valores ausentes,
NaN e infinitos causam erro, sem preenchimento por zero e sem classificação
normal por conveniência. Zeros já gravados pela aquisição são valores reais do
contrato de sinal. Frequência de amostragem, montagem e banda física precisam
ser avaliadas com coletas reais.

## As 20 características e sua ordem

Para uma série `s` com `n` valores:

- Média: `sum(s) / n`.
- Máximo: `max(s)`.
- Pico absoluto: `max(abs(s))`, incluindo extremos negativos.
- Amplitude: `max(s) - min(s)`.
- Desvio padrão populacional: `sqrt(sum((s - media)²) / n)`, com `ddof=0`.

O vetor usa a ordem fixa abaixo:

| Série | Média | Máximo ou pico absoluto | Amplitude | Desvio padrão |
| --- | --- | --- | --- | --- |
| Temperatura | `temp_media` | `temp_max` | `temp_amplitude` | `temp_desvio_padrao` |
| RMS espacial | `vib_rms_media` | `vib_rms_max` | `vib_rms_amplitude` | `vib_rms_desvio_padrao` |
| Eixo X | `x_media` | `x_pico_abs` | `x_amplitude` | `x_desvio_padrao` |
| Eixo Y | `y_media` | `y_pico_abs` | `y_amplitude` | `y_desvio_padrao` |
| Eixo Z | `z_media` | `z_pico_abs` | `z_amplitude` | `z_desvio_padrao` |

Os campos adicionais discutidos para estado ligado e tempo desde a partida não
fazem parte deste vetor. Uma mudança de fórmula, unidade, semântica do sinal ou
colunas exige outra versão de processamento e modelo compatível.

## Rótulos, grupos e conjunto de treinamento

Somente medições encerradas com rótulo conhecido `0` ou `1` e origem de rótulo
identificável entram no treinamento. A predição do próprio modelo não é verdade
de referência. Conjuntos de uma classe são rejeitados; a aplicação não inventa
exemplos anômalos para liberar treinamento supervisionado.

Cada medição rotulada precisa de `group_id` explícito. Esse grupo representa o
ciclo, equipamento, campanha ou período correlacionado que deve ficar inteiro
no mesmo conjunto. O produtor dos dados escolhe a granularidade apropriada e
documenta sua origem; não basta atribuir um grupo diferente a cada medição para
contornar a proteção. Se o objetivo é generalizar a equipamentos não vistos,
o agrupamento precisa representar equipamento. O backend não deduz grupos
automaticamente de IDs ou horários.

Há ao menos dois grupos distintos contendo cada classe para ser possível
buscar treino e avaliação com ambas as classes. Esse requisito é necessário,
mas pode ser insuficiente para uma separação viável e representativa.

## Treinamento e separação para avaliação

O algoritmo principal é `sklearn.ensemble.RandomForestClassifier` com parâmetros
iniciais centralizados: `n_estimators=200`, `class_weight="balanced"`,
`random_state=42` e `n_jobs=-1`. Não são hiperparâmetros comprovadamente ótimos e
não se afirma superioridade sobre outros algoritmos sem experimento comparativo.

A divisão usa `GroupShuffleSplit`, fração inicial de avaliação de 25% dos grupos,
semente inicial 42 e até 100 tentativas determinísticas,
selecionando a primeira separação em que treino e avaliação contêm as duas
classes. Grupos são disjuntos entre conjuntos. Se nenhuma tentativa satisfizer
essas condições, o treinamento falha com informação sobre a insuficiência do
dataset. A busca considera disponibilidade das classes, nunca a pontuação do
modelo na avaliação. A estratégia e os IDs/grupos separados ficam registrados.

O modelo é ajustado somente ao conjunto de treino e avaliado no conjunto
reservado. Não é retreinado automaticamente a cada nova medição. A avaliação de
uma versão publicada deve preservar a separação do seu treinamento; não medir
desempenho de generalização com as próprias linhas usadas no ajuste.

Os indicadores obrigatórios são matriz de confusão com ordem `[0, 1]`, acurácia,
precisão, recall e F1. A classe positiva é anomalia (`1`), de modo que recall mede
a fração dos exemplos anômalos identificados. Divisões por zero são tratadas
explicitamente na métrica. A interpretação deve considerar também quantidade
de exemplos por classe, grupos e representatividade do conjunto reservado.

## Artefato, rastreabilidade e inferência

O artefato `joblib` contém o estimador, a versão, os nomes ordenados das
características, a versão de processamento e a configuração relevante. Arquivos
de modelo são locais e devem ter origem confiável: `joblib` não é um formato
seguro para carregar arquivos desconhecidos.

Os metadados persistidos incluem parâmetros, métricas, instante de treinamento,
contagens, distribuição de classes, IDs e grupos de treino/avaliação, e
fingerprints dos dados/IDs/hashes de origem. As características também preservam
a associação à medição e à versão de processamento. A integridade dos arquivos e
a correspondência de metadados devem ser verificadas antes da inferência.

Uma medição nova percorre a mesma validação e extração do treinamento. O modelo
deve aceitar a versão e a ordem exatas das 20 entradas. A inferência usa
`predict()` e `predict_proba()`; a associação das probabilidades a normal/anomalia
é obtida de `model.classes_`, sem presumir índices fixos.

Uma estimativa de probabilidade não é garantia de acerto nem diagnóstico físico.
Não há calibração de probabilidade demonstrada neste MVP. A importância
`feature_importances_` é global da versão do modelo, persistida uma vez por
variável, e não explica causalmente uma predição individual.

## Dados artificiais e limites de evidência

A demonstração e os testes usam dados sintéticos identificados como artificiais.
Eles validam fórmulas, fluxo de treinamento, carregamento, inferência,
rastreabilidade e integridade de persistência. Métricas produzidas sobre esses
dados não demonstram capacidade de identificar defeitos reais.

A validação de campo depende de medições encerradas confiáveis, confirmação de
unidades e amostragem, rótulos independentes, grupos corretos, diversidade de
regimes e quantidade suficiente de exemplos normais e anômalos. Repouso, partida
e transição não viram classes extras nesta versão. Nenhuma coleta deve provocar
falha perigosa ou dano ao equipamento para produzir exemplos.
