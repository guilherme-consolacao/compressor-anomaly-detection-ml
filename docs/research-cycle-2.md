# Pesquisa multibase — ciclos 2 a 8

Estado atual: candidata pública por ciclos congelada e avaliada; aplicação local pendente.
As medições do protótipo permanecem fora da pesquisa, do treino e da seleção.
Os 293 ciclos SMART ficaram reservados até o congelamento da candidata da rodada 8.
Agora são evidência consumida, junto ao dia TRI OC. A validação usada no primeiro
piloto é evidência conhecida de desenvolvimento, não um novo teste independente.

## 1. Protocolo e novas fontes

O protocolo `transfer-protocol-2b941b65972c76bd9371` registra oito hipóteses,
partições, critérios, papéis das fontes e continuidade após reprovação. SHA-256:
`2b941b65972c76bd9371310931b8be3435cfbb4ce469e94498672658fed675aa`.
A reexecução confirmou idempotência e preservação das reservas.

Foram incorporados dados públicos adicionais, mantendo arquivos originais,
integridade, licença, proveniência e versões relacionais:

1. **TRI-HP**, [registro primário](https://zenodo.org/records/5155136), CC BY 4.0:
   8.363 amostras do registrador principal, 37 condições e nove dias de sessão.
   São falhas fisicamente impostas em uma bomba de calor R290, com compressor
   scroll de velocidade variável. Existem 2.448 linhas sem falha e 5.915 com
   condição de falha; linhas consecutivas não são experimentos independentes.
   O arquivo combina dois registradores em colunas distintas. O superaquecimento
   assíncrono não foi unido por número de linha. Código de teste, intensidade e
   data são metadados, sem entrada nos classificadores. A intensidade OC10 varia
   de modo suspeito e foi preservada sem uso preditivo. O dia OC está reservado.
2. **NIST**, [página oficial de dados](https://www.nist.gov/el/beed/hvacr-equipment-performance-group/fault-detection-and-diagnosis-research-data):
   7.375 resumos, 7.374 referências conhecidas e uma referência ausente mantida
   indeterminada. O campo original `NF=1` significa normal, portanto o alvo do
   projeto é invertido. Conversões de °F para °C e lb/min para g/s têm testes.
   Potência da unidade externa inclui outros componentes e não foi igualada à
   potência do compressor. Uso sob os [termos NIST para dados não SRD](https://www.nist.gov/open/license),
   com atribuição; não são dados de geladeira doméstica.
3. **RWTH complementar**: 27 espectros do compressor, três eixos em nove sessões.
   O manifesto identifica `comp_down_tri_x/y/z`; a associação térmica usa sessão
   e carga de refrigerante exatas. Dos 200 pontos espectrais, 195 têm associação
   térmica já auditada. A integral do espectro reproduz o RMS publicado com
   diferença máxima de 1,41%, 0,60% e 0,54% nos eixos x, y e z. O ZIP completo
   não foi baixado; cada membro tem CRC e SHA-256 local.
4. **SMART bruto**: 263 ciclos de desenvolvimento, incluindo os 13 com referência
   de mau funcionamento e até 30 normais por grupo, escolhidos por hash antes
   dos novos ajustes. Transferência de 176.827.363 bytes; expansão de
   695.620.841 bytes. Os sinais rápidos auditados têm 60 ou 120 segundos,
   amostrados a 2.048 Hz, e não representam automaticamente o ciclo completo.
   A prevalência dessa amostra não é a prevalência esperada na aplicação.
5. **SMART lavadoras**, controle auxiliar do mesmo provedor: 82 ciclos com
   associação não ambígua, sendo 62 Working, sete Motor, seis Bearings e sete
   Heating. Identificadores com referências ou vetores conflitantes foram
   colocados fora da incorporação, sem escolher arbitrariamente uma versão.
   Duas entropias de potência indefinidas foram preservadas como ausentes e
   excluídas das comparações. Esses controles não são uma segunda base de
   geladeiras; as falhas mecânicas observadas pertencem a um único modelo.

Os dados NIST e TRI, suas referências e características estão no MariaDB local.
O conjunto `thermal-references-e39da1111e9a2325` tem 15.738 membros, com partições
registradas e SHA-256
`e39da1111e9a23251de433f56c1502348464b9f557c5fdbf9ad1b2fbe00d344d`.
Fontes, membros, resultados e contratos continuam consultáveis pelas views de
pesquisa. A instalação/configuração do Metabase permanece fora do escopo.

## 2. Experimentos executados

| Execução | Pergunta e resultado |
|---|---|
| `anchor-round2-e66c9eee5ccc1f261841` | 24 ablações SMART, todas as 100 características e famílias separadas, com três folds de semanas. O melhor F1 por família permaneceu entre 0 e 0,10. Usar mais características publicadas não resolveu a generalização. |
| `bridge-round2-9154a7b7f7ac5737b9e7` | Três famílias de pontes medidas e 48 avaliações térmicas. NIST/TRI compartilham temperaturas e vazão verificadas; a combinação melhora alguns resultados, mas os critérios conjuntos de sensibilidade e falsos alertas não passaram. |
| `spectral-round2-bf2cffa52330d761890f` | 46 descritores espectrais por canal, seleção de ponte fora de sessão e comparação com controle de regime. Seis descritores passaram o filtro de ponte; nenhum caso TRI de treino ficou dentro da caixa dos seis preditores RWTH. Não se forçou extrapolação para montar uma base. |
| `spectral-round3-c61d2d3fdf5e9f3a0d50` | Trabalho específico R290 `1000 × kW / (g/s)` e diferenças térmicas, com nove sessões RWTH conhecidas. Algumas relações têm R² alto, mas nenhuma passou também o ganho incremental sobre os controles de operação. |
| `spectral-round4-proxy-bb432419f779fc881bbe` | Hipótese explicitamente diferente: um descritor previsível de regime pode apoiar o classificador sem ser evidência específica de defeito. Uma banda passou o filtro predefinido; 17 condições TRI de treino ficaram em suporte, com ambas as classes. A combinação detectou oito dos 13 casos SMART, com 71 falsos alertas entre 250 normais na configuração de melhor F1 multibase. Os critérios finais não foram relaxados e não passaram. |
| `auxiliary-round5-b2db3eab72fa67abc96f` | 60 comparações com controles do mesmo provedor, referências mecânicas ou todas as falhas, e ablação de origem. Melhor F1 observado: 0,125. O controle auxiliar não estabeleceu transferência útil para as geladeiras. |
| `novelty-round6-a0cdfdba68ec937811c1` | 56 comparações com descritores de desvio estatístico e Random Forest supervisionada. Os vetores de treino foram produzidos fora do próprio grupo. NIST/TRI contribuíram com 329 experimentos agregados; melhor F1: 0,0656. Essa abstração também não resolveu a referência SMART. |
| `temporal-round7-c2f700026e1cc1c77edd` | 84 comparações de duração, duração relativa ao histórico causal e ambas. A combinação SMART/NIST/TRI por duração relativa detectou 12/13 positivos com 47/769 falsos positivos no desenvolvimento por grupos. Isso motivou confirmação antes do teste reservado. |
| `temporal-round8-9492770bdefcfd8c0fcd` | Comparou fontes, limiar interno, calibração aninhada e três permutações de rótulos por fonte. A candidata de três fontes teve AP 0,5325 contra 0,1616–0,2567 nos controles. Calibração permaneceu limitada por poucos positivos. |
| `cycle-freeze-8af6bb44817d037a836c` | Congelou modelo, contrato e 1.111 casos efetivos: 782 SMART, 294 NIST e 35 TRI. Unidade SMART mudou explicitamente para ciclo completo e histórico; não usa diretamente os pacotes de temperatura/vibração. |
| `cycle-test-9446332f4eb72f0bb4de` | Teste reservado único: SMART TP10/FN1/FP21/TN252, nove recusas; TRI TP1/FN1. Os critérios agregados do protótipo passaram, sem provar validade local ou para qualquer compressor. |

Cada pasta de execução contém protocolo, resultados, previsões e manifestos.
Os protocolos das rodadas 3–6 foram registrados antes de seus respectivos
ajustes. Rodadas recentes também preservam os bytes do código executado.
Escores são de classe de referência e permanecem sem calibração; percentis de
atipicidade não foram apresentados como probabilidade de defeito.

## 3. Relação entre variáveis: o que ficou demonstrado

Nas 195 condições RWTH, a regressão térmica/elétrica fora de sessão obteve,
por exemplo, R² de 0,695 para centroide espectral e 0,896 para energia de
10–100 Hz. O controle usando somente regime obteve 0,265 e 0,975, respectivamente.
Portanto, parte da correlação é explicada pelo funcionamento da máquina.
Correlação previsível e utilidade para detectar falhas são perguntas distintas,
e ambas foram testadas. A hipótese de proxy preservou essa distinção e foi
avaliada com referências SMART realmente medidas, não com os próprios rótulos
estimados.

Nenhuma linha juntou temperatura de uma coleta com vibração de outra como se
fossem simultâneas. A projeção da rodada 4 contém características estimadas,
com origem e limites explícitos, e referências de falha originais do experimento.
Nenhum rótulo físico derivado foi aceito automaticamente.

## 4. Lacunas e continuidade

As rodadas 2–6 não autorizaram liberar uma candidata. A decisão posterior por
ciclos está no [relatório específico](cycle-candidate-report.md). Continuam abertos
o vínculo com o alvo físico pretendido, suporte independente, calibração e
compatibilidade da aquisição local. SMART rotula mau funcionamento da geladeira,
sem especificar o componente; não se deve declarar cada positivo como defeito
confirmado do compressor.

A pesquisa dirigida também auditou a bancada
[Smart Manufacturing](https://github.com/submission-2022/Smart-Manufacturing-Testbed-for-Anomaly-Detection),
CC0, commit `ae6d6bf256e80c0044dc52aafec32b0378eec5f9`. Os ZIPs medidos
permitem associação por condição/RPM, não por linha. A série MEMS não possui
timestamps; o piezoelétrico tem grandes lacunas entre rajadas. A correspondência
dos códigos 1/2/3 com normal/falha não foi confirmada, então nenhum alvo binário
foi inventado e a bancada não entrou no modelo congelado.

O [OF550W](https://github.com/iftitalukder/fault-detection) foi triado como
compressor de ar triaxial; licença não confirmada, sem incorporação. O
[estudo hermético](https://www.mdpi.com/2076-3417/12/6/3033) não disponibiliza
um pacote de dados brutos confirmado; artigo aberto não foi tratado como dataset.
A base [ORNL CO2](https://doi.org/10.6084/m9.figshare.13232627.v1) tem metadados e
cabeçalho auditados, mas os CSV grandes ainda não foram incorporados nem
receberam rótulos inventados por nome de arquivo.

Também surgiu uma pergunta de qualidade temporal: características publicadas
de potência parecem incluir contexto além dos limites do ciclo. Nas primeiras
comparações, médias/desvios e comprimentos rápidos publicados coincidem com os
brutos; esse ponto não explica sozinho as falhas de classificação. Duração,
cobertura e contexto operacional precisam de auditoria antes de virar novos
preditores, sem confundir lacuna de aquisição com falha da máquina.

O código original SMART foi auditado apenas como texto: os limites publicados
são obtidos a partir do sinal lento de potência. Isso não permite reproduzir os
mesmos limites a partir de um POST instantâneo de temperatura/três eixos sem
verificação adicional. Os scripts originais são GPL e não foram executados nem
copiados para implementar a candidata.

H06: eventos de manutenção ULT com início incerto não sustentam rótulo binário
fino por minuto. H08: subamostrar uma forma de onda a intervalos de segundos
não preserva a banda mecânica de 10–1.000 Hz; não foi simulado sucesso de
transferência para esse contrato. A alternativa por duração exige limites reais.

Fechamento de software: **306 testes aprovados, um opt-in legado ignorado**,
Ruff e build Python aprovados. Os testes MariaDB locais foram executados em
bases temporárias isoladas. Metabase não foi configurado.
