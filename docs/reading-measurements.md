# Medições agrupadas por horário

O comando `predict-readings` organiza as leituras de cada equipamento pelo
horário. Leituras consecutivas pertencem à mesma medição enquanto o intervalo
for menor ou igual a `--gap-seconds`. Um intervalo maior abre a próxima medição.
A saída inclui ID da medição, IDs das leituras associadas, primeiro e último
horário observado e duração desse trecho. O ID é repetível para o mesmo
equipamento, limite e primeira leitura.

A primeira e a última medição de cada equipamento no arquivo podem estar
cortadas pelas bordas da exportação. Elas aparecem na saída como
`snapshot_boundary`, sem escore e sem contribuir para o histórico. Grupos sem
intervalo positivo recebem `no_observed_span`. Para os demais, a Random Forest
compara a duração observada com a mediana de até dez medições anteriores do
mesmo equipamento. São necessárias pelo menos três; uma pausa acima de 12 horas
reinicia o histórico.

O resultado `exploratory_alert` usa o limiar congelado de 0,5. A duração mede o
trecho coberto pelas leituras persistidas, e as pausas podem refletir a coleta
ou a transmissão. Uma confirmação de falha depende de condição observada de
forma independente. O comando `predict-cycles` continua destinado a limites
operacionais comprovados.

## Como executar

Exporte um intervalo contínuo de leituras em JSON, com um identificador de
equipamento por linha e horário ISO 8601 com fuso. Preserve os IDs da aquisição.
O primeiro e o último grupo ficam de fora da pontuação a cada execução, então
inclua histórico e leituras após a pausa que encerra a medição a analisar.

```json
[
  {"equipment_id": "compressor-1", "reading_id": 1, "timestamp": "2026-10-08T01:30:06Z"},
  {"equipment_id": "compressor-1", "reading_id": 2, "timestamp": "2026-10-08T01:30:18Z"}
]
```

Execute na raiz do repositório, onde `models/` é o diretório confiável do modelo:

```powershell
python -m compressor_anomaly_detection_ml predict-readings --manifest reports/research/cycle-freeze-8af6bb44817d037a836c/manifest.json --readings reports/private/ulisses-time-gap-20261008/readings.json --gap-seconds 60
```

O JSON da saída é o registro das associações e dos resultados. Esse fluxo lê
arquivos locais e não depende de conexão ao banco. Exporte cada equipamento
separadamente ou identifique-o por linha, sem juntar fluxos desconhecidos.

## Ensaio histórico

Foram usadas as 3.701 leituras de 08/10/2026 do [backup auditado](database-dump-audit.md),
tratadas como um fluxo, pois o arquivo não identifica o equipamento por linha.
Dos 3.700 intervalos, 75,6% foram de 12, 13 ou 19 s. A mediana foi 13 s,
o percentil 95 foi 33 s e o percentil 99 foi 46 s. Só 10 pausas passaram
de 60 s, de 65 a 243 s. Nenhuma pausa caiu de 60 a 64 s, então qualquer
limite inteiro de 59 a 64 s separa os mesmos trechos pela regra `pausa > limite`.

Reexecutamos a Random Forest congelada com o mesmo limiar de escore de 0,5 em
18 cortes. Em cada execução, as 3.701 leituras foram associadas uma única vez.
A tabela apresenta cortes representativos.

| Pausa para separar medições | Medições | Com escore | Alertas exploratórios |
| ---: | ---: | ---: | ---: |
| >30 s | 348 | 308 | 260 |
| >45 s | 49 | 43 | 36 |
| >55 s | 15 | 10 | 8 |
| >59 s ou >64 s | 11 | 6 | 6 |
| >60 s | 11 | 6 | 6 |
| >65 s | 10 | 5 | 5 |
| >70 s | 8 | 3 | 2 |
| >72 s | 5 | 0 | 0 |
| >120 s | 2 | 0 | 0 |

Com 60 s, dois grupos ficaram nas bordas e três forneceram histórico. A nova
execução reproduziu os seis escores anteriores, entre 0,622 e 0,785. Com 65 s,
cinco desses trechos ainda geraram alerta. Com 70 s, dois permaneceram alertados
e um trecho fundido recebeu escore abaixo do limiar. Com 72 s, os três grupos
entre as bordas serviram de histórico, sem grupos adicionais para pontuar.

Alterar o limite também pode mudar o escore de um trecho com os mesmos limites.
As leituras 2830 a 2921 receberam 0,622 com 60 s e 0,306 com 55 s. A duração
observada continuou em 1.672 s, mas a razão perante a mediana do histórico
passou de 0,494 para 0,887 porque a divisão dos grupos anteriores mudou.

Para este backup, 60 s é um corte inicial para uso exploratório. Ele está na
faixa em que os agrupamentos são estáveis e separa apenas pausas raras na
coleta. A confirmação de que essas pausas delimitam ciclos e a avaliação dos
alertas dependem de registros independentes de operação e condição do compressor.
Os resultados por corte ficaram em `reports/private/ulisses-time-gap-20261008/sensitivity.json`.
