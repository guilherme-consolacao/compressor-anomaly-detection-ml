# Auditoria do backup de telemetria — 28/10/2026

O arquivo fornecido contém **3.701 leituras históricas** e confirma, para esse
snapshot, a estrutura simples da API: uma tabela `readings`, sem medição,
equipamento, rótulo ou encerramento de coleta. Os dados permitem uma análise
exploratória; ainda não constituem um dataset supervisionado de medições.

## Fonte, datas e método

- Origem: exportação compactada do banco de telemetria do protótipo.
- Tamanho: 66.233 bytes comprimidos; 286.753 bytes de SQL descomprimido.
- SHA-256: `a0817427315910d34aeafe66d8b20d2a73813c3a6300a00ba01d0df07d2ed789`.
- Cabeçalho: servidor `11.8.9-MariaDB-log`, exportador MariaDB 11.8.9 para Linux.
- Rodapé: exportação concluída em `2026-10-18 02:06:54`, sem fuso nesse comentário.
- O SQL configura `TIME_ZONE='+00:00'`: os valores exportados de `TIMESTAMP`
  são interpretados em UTC. Isso não revela o fuso original do firmware ou o
  fuso usado no nome/rodapé do arquivo.

O gzip foi lido como texto UTF-8. Foram reconhecidas somente tuplas com ID,
cinco números decimais e um timestamp no formato esperado. Todas as 3.701
tuplas foram aceitas; nenhuma foi descartada ou preenchida. A estrutura e os
principais resultados numéricos foram conferidos por duas leituras independentes.
Não houve `eval`, execução de SQL, importação em banco ou conexão remota.
O arquivo original foi preservado e não foi copiado integralmente para o Git.

Este é um backup concluído em **18/10**, contendo leituras de **08/10 em UTC**.
Ele não comprova o estado do servidor em 28/10. A tentativa anterior de acesso
online foi recusada por conta bloqueada, conforme a auditoria de integração.

## Estrutura observada no arquivo

Há uma definição de tabela, `readings`. Não foram encontradas definições de
views, triggers, procedures, functions ou events. Como as opções e permissões
da exportação não foram informadas, isso descreve o conteúdo do arquivo e não
garante ausência desses objetos no servidor.

| Campo | Definição exportada |
| --- | --- |
| `id` | `BIGINT UNSIGNED`, chave primária, auto incremento |
| `temperature` | `DECIMAL(12,6) NOT NULL` |
| `accel_x`, `accel_y`, `accel_z` | `DECIMAL(12,6) NOT NULL` |
| `rms` | `DECIMAL(12,6) NOT NULL` |
| `timestamp` | `TIMESTAMP NOT NULL DEFAULT current_timestamp()`, sem frações de segundo |

Existe o índice `idx_readings_timestamp(timestamp)`. A engine exportada é
**InnoDB**, com `utf8mb4_unicode_ci` e próximo auto incremento `3702`.
Não há chave estrangeira ou associação explícita a equipamento/coleta.

A tabela equivale à definição versionada da API. O backup acrescenta evidência
de engine/charset/collation efetivos nesse snapshot; o SQL da API não fixa a
engine. O nome do banco exportado difere do nome de exemplo `compressor_db`,
o que pode ser acomodado pela configuração, sem renomear estruturas.

O arquivo contém comandos de restauração, incluindo `DROP TABLE`, `ALTER TABLE`,
`INSERT` e `COMMIT`. Eles foram tratados exclusivamente como texto.

## Volume, período e integridade estrutural

| Verificação | Resultado |
| --- | --- |
| Leituras | 3.701 |
| IDs | 1 a 3701, únicos e contíguos |
| Primeiro registro | 08/10/2026 01:30:06 UTC |
| Último registro | 08/10/2026 19:59:18 UTC |
| Período entre primeiro e último | 18h29min12s |
| Valores nulos ou não finitos | 0 |
| Timestamps repetidos | 0 |
| Reversões temporais em ordem de ID | 0 |
| Repetições dos cinco valores de sensores | 240 além da primeira ocorrência |

Em `America/Sao_Paulo`, o período é **07/10 às 22:30:06 até 08/10 às 16:59:18**.
IDs contíguos não demonstram que nenhuma amostra física se perdeu: faltam
sequência do dispositivo e contagem esperada. Valores repetidos também não
provam reenvio; podem resultar de quantização, filtragem ou estabilidade.

## Intervalos entre registros persistidos

Foram analisados os 3.700 intervalos entre timestamps consecutivos:

| Estatística | Segundos |
| --- | ---: |
| Mínimo | 12 |
| Mediana | 13 |
| Média | 17,987 |
| Percentil 95 | 33 |
| Máximo | 243 |

Os intervalos mais frequentes foram 12s (1.389 ocorrências), 19s (818) e
13s (589). Há 347 intervalos maiores que 30s e 10 maiores que 60s. O maior,
de 4min03s, ocorre entre IDs 2396/2397, de 13:35:26 a 13:39:29 UTC.
Não é possível atribuir essas variações a rede, agendamento, pausas, falhas ou
perdas sem evidência do dispositivo e dos logs da aquisição.

O volume observado equivale a aproximadamente 200 registros por hora.
Isso é uma taxa de **persistência observada**, não a frequência interna do MPU-6050,
e não mede tempo de resposta, tráfego completo ou custo da API. No código
auditado, cada requisição aceita gera uma linha; este histórico não sugere
centenas de registros persistidos por segundo.

Com espaçamento mínimo de 12s nesse histórico, um período de 15s conteria no
máximo duas das leituras já persistidas, e alguns períodos não conteriam nenhuma.
Isso não implementa nem identifica medições. Também não constitui evidência de
amostragem suficiente para caracterizar vibração. É necessário confirmar se o
firmware captura mais amostras e transmite apenas parte delas.

## Valores observados

Os números abaixo preservam os campos existentes, sem nova calibração.
Temperatura é interpretada em °C conforme o contrato/log da API; a confirmação
física do firmware e a unidade dos eixos continuam necessárias.

| Campo | Mínimo | Máximo | Média |
| --- | ---: | ---: | ---: |
| `temperature` | 49,062500 | 71,500000 | 61,987453 |
| `accel_x` | -1,983948 | 2,000427 | -0,004359 |
| `accel_y` | -0,086344 | 1,984639 | 0,002978 |
| `accel_z` | -1,023173 | 0,105794 | -0,057045 |
| `rms` | 0,000000 | 1,297283 | 0,062070 |

A mediana do RMS é `0,028755`. Há 275 valores acima de `0,2`; esse corte é
somente descritivo, sem significado de normalidade ou anomalia validado.
O máximo `1,297283` aparece seis vezes, com o mesmo vetor de eixos:
`(2,000427; -0,015361; -1,023173)`, nos IDs 3120, 3190, 3224, 3462, 3513 e 3595.
O eixo Z assume exatamente `-1,023173` em 159 registros.

Esses valores repetidos e extremos merecem confronto com faixa, orientação,
conversão, calibração e comportamento do sensor. Não se concluiu saturação,
defeito, partida do compressor ou anomalia a partir deles. As temperaturas
observadas, por si só, também não definem defeito: faltam posição do sensor,
condições operacionais e uma referência de funcionamento.

## Consistência do RMS e da supressão de ruído

Foi recomputada a expressão utilizada pela API:

```text
sqrt((accel_x² + accel_y² + accel_z²) / 3)
```

Nenhuma linha apresentou erro absoluto superior a `1,1 × 10^-6`. O erro máximo
foi `8,5894 × 10^-7`, compatível com o arredondamento a seis casas dos eixos e
do próprio RMS. A tolerância considera que a API calcula antes de o banco
arredondar cada campo; igualdade decimal exata não seria um critério correto.

Isso confirma a compatibilidade numérica do campo com a combinação espacial
instantânea. Não comprova RMS temporal, unidade `g`, calibração física correta
ou qual versão da API recebeu cada pacote.

| Eixo | Quantidade exatamente zero | Percentual |
| --- | ---: | ---: |
| X | 2.147 | 58,01% |
| Y | 895 | 24,18% |
| Z | 1.125 | 30,40% |

Em nenhum eixo aparece valor não zero com módulo menor que `0,01`, o que é
compatível com a supressão de ruído do código auditado. Há 445 registros com
os três eixos zerados, também com RMS zero. Isso não significa ausência de
dado nem comprova compressor desligado. O filtro remove sinais pequenos e
precisa ser avaliado com o responsável pela aquisição antes de qualquer ajuste.

## Relação com envio em lote e com ML

Existe um único `INSERT INTO readings VALUES` estendido no arquivo, contendo
3.701 tuplas. **Esse é o formato do backup, não evidência de uma requisição HTTP
em lote.** O endpoint auditado continua aceitando uma leitura por requisição.
O arquivo não armazena fronteiras de pacotes ou de coletas.

Não existem IDs de medição, início/fim de ciclo, status de finalização, equipamento,
grupo de correlação, rótulo 0/1 ou origem do rótulo. Não é possível converter
com confiança essas 3.701 leituras em um número conhecido de medições. O backend
não criou janelas arbitrárias, não atribuiu classes e não executou a Random Forest
sintética sobre esse histórico.

A proposta de tabelas auxiliares permanece compatível com o esquema do backup,
sem recriar `readings`. Para prosseguir com dados de coleta confiáveis:

1. Confirmar unidades, aquisição interna, frequência de envio e horários com o firmware.
2. Documentar os extremos e zeros junto ao responsável, sem rotulá-los automaticamente.
3. Definir IDs e limites de medições encerradas; se um lote for uma coleta inteira,
   publicar explicitamente essa equivalência, preservando os tempos das amostras.
4. Associar rótulos independentes e grupos de correlação para o treinamento.
5. Comparar o esquema online atual e aprovar eventuais tabelas auxiliares antes de implantá-las.

O backup resolve a inspeção de **um snapshot histórico**. A inspeção online,
o contrato de medição e a validação do classificador com dados rotulados
continuam pendentes.

Posteriormente foi executado um [experimento não supervisionado](unsupervised-exploration.md)
por leitura, com DBSCAN e Isolation Forest. Ele encontrou grupos e candidatos
para revisão, sem criar medições, rótulos de defeito ou validação do classificador.
