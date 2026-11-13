# Auditoria das fontes públicas — 01/11/2026

Este documento trata de evidência pública. Nenhuma leitura do protótipo participa
da preparação, do ajuste, da EDA ou dos experimentos descritos aqui. O relatório
parcial do PI é contexto, sem impor algoritmo, janela ou suposições de aquisição.

## Fontes com arquivos efetivamente acessíveis

| Fonte e versão | Evidência e licença | Unidade, sinais e referência | Uso permitido nesta pesquisa |
| --- | --- | --- | --- |
| SMART-PDM, Zenodo 7245198 | Dois CSVs extraídos do ZIP por Range, CRC e SHA-256 próprios; CC BY 4.0 | 1.111 ciclos, 100 características; 1.087 Normal e 24 Malfunction; vibração escalar e elétrica | Referência de manutenção do eletrodoméstico, sem chamar toda falha de defeito do compressor |
| KAIST, Mendeley ztmf3m7h5x/6 | Catálogos ZIP; amostra selecionada de arquivos TDMS/MAT; CC BY 4.0 | Bancada rotativa; mancais A/B, x/y; temperaturas A/B, correntes U/V/W; diagnósticos no nome do registro | Pesquisa de forma da vibração e efeito da carga; transferência a refrigeração continua hipótese |
| RWTH R290, Zenodo 22097811 | ZIPs/CSVs pequenos completos com checksum do provedor; CC BY 4.0 | 195 condições térmicas, 200 condições RMS XYZ do compressor, nove sessões | Correlações genuinamente pareadas por sessão/carga; não há alvo binário independente |
| ULT, coleção 6805332.v1, artigo Figshare 24033324 | Catálogo do ZIP de 9,8 GB, planilha de eventos, modelos e três logs pequenos; CC0 | Freezers em cascata; temperaturas em pontos específicos; histórico de reparos | Pesquisa térmica e contexto de falhas; não atribuir automaticamente normal/anômalo a cada minuto |

Fontes primárias:
[SMART-PDM dados](https://zenodo.org/records/7245198),
[SMART-PDM artigo](https://pmc.ncbi.nlm.nih.gov/articles/PMC10063395/),
[KAIST dados](https://data.mendeley.com/datasets/ztmf3m7h5x/6),
[RWTH dados](https://zenodo.org/records/22097811),
[ULT dados e licença](https://api.figshare.com/v2/articles/24033324),
[ULT artigo](https://pmc.ncbi.nlm.nih.gov/articles/PMC10710515/).

Hashes dos arquivos individuais e URLs de aquisição estão em `study_artifacts`
e nos relatórios de aquisição. Nos arquivos grandes amostrados, o checksum do
ZIP completo é declarado pelo provedor e **não foi verificado**. A integridade
de cada membro baixado foi conferida por CRC e SHA-256; não se anuncia download
completo ou cobertura de todas as condições.

## SMART-PDM

O join usa `F_ExtractedFeatures.Id == fridge_metadata.begin_end`, com cardinalidade
um-para-um. Linhas embaralhadas continuam associadas corretamente. Ausência,
chave duplicada, rótulo desconhecido ou valor não finito recusam a preparação.

Há 25 atributos publicados por família, totalizando quatro famílias e 100
atributos. A pesquisa de transferência usa somente forma temporal da vibração,
não dados elétricos indisponíveis na aquisição local. Frequências de captura
descritas pelos autores: 1 Hz e 2.048 Hz, conforme modalidade. Não foi confirmada
a conversão física do canal escalar de vibração. Não se assume ADC, g ou m/s².

Os ciclos duram aproximadamente 0,40 a 4,94 horas. A ausência de identidade da
unidade física impede alegar teste entre compressores diferentes. A marca/modelo
SMEG FAB5ULRD3 não identifica uma frota independente. As 24 marcações de falha
distribuem-se em somente quatro blocos semanais conectados após unir semanas
atravessadas por um ciclo. O agrupamento inicial de 86 dias era candidato;
o snapshot de pesquisa guarda a regra final mais conservadora.

O objetivo do agrupamento não é chamar cada ciclo ou janela de equipamento.
Rótulos continuam sendo a referência publicada de manutenção do eletrodoméstico.
Não foram refeitos a partir dos clusters.

## KAIST

A amostra definida antes da modelagem contém cargas de 2 e 4 Nm, condições
`Normal` e `BPFO_03`, quatro registros por modalidade. Os demais diagnósticos e
a carga de 0 Nm constam do catálogo, sem fingir que foram todos importados.

Cada posição é preservada: `housing_A_x`, `housing_A_y`, `housing_B_x` e
`housing_B_y`. Esses canais não são XYZ da carcaça de um compressor. Segmentos
não sobrepostos de cinco segundos são unidades de pesquisa **dentro de um
registro público**, sem impor janela à aquisição do protótipo. Todos os canais e
segmentos da mesma carga ficam no mesmo papel de avaliação.

O TDMS armazena dois canais térmicos e três de corrente. A propriedade de tempo
da forma de onda não comprova que um termopar atualiza fisicamente nessa taxa.
A propriedade de unidade original é preservada mesmo quando o próprio arquivo
traz um caractere inválido. A semântica dos canais vem do metadado do provedor.
As taxas e formatos medidos de cada arquivo ficam no relatório de amostras.
O MAT real usa `Signal.x_values` e `Signal.y_values`, com 25.600 amostras/s.
O arquivo declara exportação MKS, rótulo de exibição `g` e fator aproximado de
0,1019716213. Preservamos esses campos e os números nativos, sem afirmar unidade
absoluta nem aplicar conversão ainda não confirmada. As três características
candidatas de forma são invariantes a escala positiva e offset; isso não as
torna invariantes à banda, à montagem ou ao equipamento.

Ter o mesmo nome de carga/diagnóstico nos dois arquivos não demonstra captura
simultânea. Não foi fabricada correlação amostra a amostra entre MAT e TDMS.
`scipy` e `npTDMS` foram acrescentados somente para ler esses formatos.
Nos TDMS das duas condições BPFO amostradas, dois dos três canais de corrente
estão declarados mas vazios: quatro canais vazios no total. Eles permanecem
ausentes, sem zeros ou estatísticas inventadas. Esse padrão depende da condição;
usá-lo para classificar a falha poderia explorar um artefato da aquisição.
O experimento de transferência usa somente as características da vibração.
O [artigo KAIST](https://pmc.ncbi.nlm.nih.gov/articles/PMC10036499/) descreve os
sensores e instrumentos distintos de aquisição; isso não fornece, por si só,
um vínculo temporal validado entre todos os arquivos inspecionados.

## RWTH

O compressor tem RMS temporal em m/s² na banda de 10–1.000 Hz. As temperaturas
são do refrigerante na entrada/saída, não da superfície externa. Frequências
de operação do compressor não são a taxa de amostragem do acelerômetro.

O pareamento por sessão/carga resulta em 195 associações reais. Permanecem sem
temperatura: M05/2.350 g, M06/650 g, M06/750 g, M06/2.250 g e M07/2.350 g.
Não houve interpolação dessas condições. As 2.000 linhas RMS de todos os sensores
não representam 2.000 experimentos independentes.

Carga, frequência e sessão são condições experimentais. Um corte arbitrário de
carga não cria rótulo de defeito. As 195 observações mantêm alvo indeterminado.

## ULT

A planilha contém 46 registros de reparo; quatro são marcados como dados ausentes.
O artigo informa 42 eventos associados aos dados. O instante de início da falha
é desconhecido: a data registrada é a solicitação de atendimento, potencialmente
posterior ao início. Marcar meio-dia ou uma janela próxima não produziria verdade
independente para todos os pontos. Não se rotula como normal o restante do log
apenas por não possuir evento naquele minuto.

Os três logs amostrados somam 1.531 linhas com intervalo mediano de 60 segundos,
sem zona de horário confirmada. O horário local permanece no metadado; não foi
convertido artificialmente em UTC. Divergências entre identificador de controlador
no cabeçalho e pasta do provedor ficam registradas para auditoria.

No Revco, RTD é a câmara, TC1 a sucção do primeiro estágio, TC6 a sucção do
segundo estágio e TC9 o reservatório de óleo do compressor do segundo estágio.
Cada canal térmico preserva o ponto de medição definido pela fonte.
A planilha de modelos identifica, entre outros, Copeland RFT42C1E-PFZ-382,
Embraco NT2212GKV e Embraco VNEU217U. Isso contextualiza o equipamento; não
torna intercambiáveis freezers em cascata e geladeiras domésticas.

O resumo de eventos e modelos foi lido como dados. PDFs de serviço e scripts
externos não foram executados. Nenhuma ausência de rótulo foi preenchida com
uma hipótese para aumentar artificialmente o conjunto supervisionado.

## Candidatas que não forneceram observações importáveis

| Candidata | Evidência inspecionada | Decisão |
| --- | --- | --- |
| Estudo de defeitos de fabricação em compressores herméticos | Artigo descreve condições e defeitos; disponibilidade de dados declarada como não aplicável | Referência científica; nenhum arquivo bruto público confirmado para importar |
| NIST, assinaturas de três compressores de deslocamento positivo | Página primária da publicação | Referência de vibração; não há dataset rotulado reutilizável confirmado nesta inspeção |
| Catálogos Secop | Catálogo do fabricante | Referência física e de modelos; não é histórico rotulado de sensores nem permite identificar o compressor local pelas poucas leituras |

[Artigo de compressores herméticos](https://www.mdpi.com/2076-3417/12/6/3033),
[publicação NIST](https://www.nist.gov/publications/vibration-signatures-three-positive-displacement-compressors),
[catálogos Secop](https://www.secop.com/products/technical-literature/technical-literature-show/catalogs).

Essas entradas têm origem `public_reference`, separada de `public_measured`.
O suporte explícito a essa categoria exigiu a migração local
`004_reference_sources.sql`; o dump estrutural foi novamente exportado e restaurado.
Busca encerrada para esta rodada após inspecionar todas as candidatas previstas.
Nova fonte exige uma lacuna concreta e uma nova revisão rastreável.
# Complemento atual — fontes e decisão por ciclos

A auditoria inicial abaixo permanece histórica. As rodadas posteriores e a
contribuição efetiva de cada fonte estão em [research-cycle-2.md](research-cycle-2.md)
e [cycle-candidate-report.md](cycle-candidate-report.md).

TRI-HP e NIST foram incorporadas com arquivos oficiais, unidades e rótulos
verificados. O treino congelado usa SMART 782 ciclos, NIST 294 experimentos e
TRI 35 condições. RWTH, KAIST, ULT e lavadoras apoiaram investigação/controles;
não foram incluídas apenas para aumentar o número de fontes final.

Bancada Smart Manufacturing e ORNL estão registradas como auditoria/candidata,
com limitações; não entram no modelo congelado. OF550 ficou sem incorporação
por licença não confirmada. O artigo de compressores herméticos não foi
confundido com disponibilidade de dados brutos.

O teste público reservado foi aberto somente depois do congelamento e agora
é evidência consumida. Nenhuma medição do protótipo entrou nesta pesquisa.
