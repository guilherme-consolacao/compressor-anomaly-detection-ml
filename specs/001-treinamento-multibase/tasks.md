# Tarefas — treinamento multibase e validação externa

Versão: 1.4.0
Data: 01/11/2026
Contrato: [spec.md](spec.md)
Plano técnico: [plan.md](plan.md)
Situação: T07–T17, T24 e T29–T31 concluídas para a candidata pública desta rodada. T18/T20 em execução; T19/T21–T23 aguardam compatibilidade e campanha externa. Modelo por ciclos não equivale à integração automática com o POST atual.

## 1. Como executar e concluir uma tarefa

1. Ler os requisitos indicados e conferir as dependências.
2. Registrar o estado `EM_EXECUCAO`, a hipótese ou mudança e os resultados esperados.
3. Implementar ou executar a pesquisa no menor escopo que atenda aos critérios.
4. Executar a verificação e registrar sua evidência.
5. Marcar cada critério satisfeito e concluir a tarefa somente quando todos os aplicáveis estiverem atendidos.
6. Se um critério falhar, manter a tarefa `EM_CORRECAO`, identificar a causa, corrigir e verificar novamente a parte afetada.
7. Se faltar informação ou recurso externo, usar `BLOQUEADA`, registrando a evidência, o impacto e a condição de retomada. Não marcar como concluída por expiração de prazo.
8. Reabrir dependentes quando uma correção mudar o contrato, dataset, rótulos, partições ou resultados em que elas se apoiavam.

Estados permitidos: `PENDENTE`, `EM_EXECUCAO`, `EM_CORRECAO`, `BLOQUEADA`, `CONCLUIDA`.

Cada execução deve registrar tarefa, tentativa, data, versão do código/configuração, fontes e hashes relevantes, comando ou procedimento, resultado de cada critério e caminhos das evidências. Evidência não pode depender apenas de mensagem no chat ou de um arquivo temporário ausente em outro ambiente.

Critério transversal da versão 1.1.0: toda tarefa que produza dados preparados, características, rótulos, execuções ou resultados para auditoria/visualização deve persistir esses registros no MariaDB usando os escritores de T26, além de eventuais arquivos de intercâmbio. A integração do respectivo chamador e seu roundtrip são parte do aceite da tarefa produtora.

Critério condicional só pode ser marcado como não aplicável com justificativa e evidência. Exemplo: ausência comprovada de arquivos públicos pode concluir a auditoria de uma candidata, mas não comprova a integração nem conclui o objetivo multibase.

Não há número fixo de tentativas para “forçar” conclusão. Nova execução deve responder a uma correção ou hipótese concreta. Dificuldade científica persistente deve gerar conclusão explícita de inviabilidade ou pendência, sem fabricar dados, rótulos ou métricas.

## 2. Sequência e dependências

**Ordem imediata da revisão 1.3.0:** T29 → T30 → T07 → T08 → T09 → T10 →
T11 → T12 → T31 → T13 → T14. Depois de uma decisão pública favorável:
T15 → T16 → T17 → T18 → T20 → T19 → T21. T22/T23 constituem a campanha física
posterior, com referência observada; não serão marcadas por simulação.

Caixas marcadas e notas de execução da versão 1.2.0 são evidência histórica.
Os novos critérios ficam abertos até execução e verificação. Falha de uma
hipótese leva à próxima ou a busca dirigida em T30, com novo protocolo quando
necessário. Não encerrar a investigação simplesmente repetindo o primeiro piloto.

| Etapa | Tarefas | Resultado necessário |
| --- | --- | --- |
| 0. Banco, auditoria e dados consultáveis | T25, T27, T28; depois T01/T26 | MariaDB local, documentação de consulta e dump estrutural testado antes da ingestão |
| 1. Inventariar e importar fontes públicas | T01–T06 | Fontes auditadas, rastreáveis e separadas do teste externo |
| 2. Preparar e explorar | T07–T12 | Contratos, partições protegidas, exploração e hipóteses de compatibilidade |
| 3. Investigar integração | T13–T14 | Viabilidade demonstrada ou limitações documentadas |
| 4. Consolidar e adaptar | T15–T16 | Dataset final e contrato de treino/inferência versionados |
| 5. Treinar e congelar | T17–T19, T21 | Modelo avaliado em dados públicos, protocolo e software verificados |
| 6. Testar externamente | T20, T22–T23 | Predições comparadas à referência real do protótipo |
| 7. Concluir e documentar | T24 | Evidências finais e estado real do objetivo |
| Revisão 1.3: protocolo e insumos | T29, T30 | Hipóteses priorizadas, reservas e dados adicionais necessários |
| Revisão 1.3: pontes públicas | T31, T13, T14 | Relações entre modalidades testadas, transferência avaliada e decisão pública separada da local |

T20 prepara o adaptador usando apenas o esquema e fixtures; pode anteceder T21 sem acessar medições reais. T21 é a verificação transversal do fluxo antes de liberar a campanha externa. A numeração é uma sequência de execução de referência, não autorização para ignorar dependências.

Na ordem revisada, T20 usa a candidata pública de T17 e o protocolo T18 para
preparar/verificar o adaptador; T19 depende desse resultado de compatibilidade.
Somente depois do congelamento são permitidas as leituras reais reservadas.

As importações T03–T06 são independentes depois de T02 e podem ser executadas na ordem mais conveniente. Não é necessário criar agentes ou infraestrutura paralela para isso.

## 3. Etapa 1 — inventário e ingestão

### T01 — Fixar a separação entre desenvolvimento público e teste externo

Estado: CONCLUIDA
Dependências: T25, T27, T28
Requisitos: RF-01, RF-02, RF-29, RF-30, RF-31

Entregar a convenção de proveniência, os destinos locais e a proteção de entrada do pipeline público. Registrar a nova política em configuração e documentação sem remover o histórico das análises anteriores.

Critérios de aceite:

- [x] Observações possuem origem explícita; dados do protótipo recebem identificação externa não elegível ao desenvolvimento.
- [x] O validador público recusa origem local, origem ausente e derivação que inclua dados locais, independentemente do diretório.
- [x] Existe teste negativo com arquivo renomeado/copied para uma pasta pública, demonstrando que caminho não substitui proveniência.
- [x] Dados privados, brutos grandes e binários de modelos estão fora do versionamento; nenhum segredo foi incluído.
- [x] A exposição histórica ao backup está registrada e não foi apagada para simular teste nunca visto.

Evidência: configuração, política de origem, testes de isolamento e revisão dos arquivos versionáveis. Verificação: testes direcionados e inspeção dos manifestos de entrada.

Execução 01/11/2026, tentativa 1: 21 testes de proveniência/CLI aprovados; registro em `config/dataset-sources.json`, proteção em `provenance.py` e evidências em [docs/development-execution.md](../../docs/development-execution.md).

### T02 — Criar o registro das fontes e a ingestão controlada

Estado: CONCLUIDA
Dependências: T01, T26
Requisitos: RF-03, RF-04, RF-05, RF-06, RF-30

Implementar aquisição/registro simples com biblioteca padrão, preservando versão, licença e integridade.

Critérios de aceite:

- [x] SMART-PDM, KAIST, RWTH e candidatas adicionais da especificação possuem registro com estado de inspeção e campos desconhecidos explícitos.
- [x] Cada arquivo reutilizado tem URL primária, versão, licença/atribuição, tamanho e hash; arquivos originais não são sobrescritos.
- [x] Rede tem timeout e limite de tamanho; HTTP Range valida status e intervalo quando utilizado; falha não promove arquivo parcial a válido.
- [x] Extração ZIP recusa caminhos fora do destino e conteúdo acima dos limites definidos.
- [x] Casos de checksum incorreto, ZIP inválido, timeout e versão já existente têm comportamento verificável com fixtures pequenas.
- [x] Scripts externos não são executados automaticamente e downloads grandes exigem necessidade documentada.

Evidência: registro das fontes, manifesto de arquivos e testes de integridade/limites. Verificação: ingestão de arquivo pequeno conhecido e fixtures de falha, sem acesso ao banco local compartilhado.

Execução 01/11/2026: quatro metadados de datasets conferidos por identidade; artefatos/hashes e resumos registrados no MariaDB. SMART-PDM inspecionada com 1.250.154 bytes transferidos do ZIP, CRC dos membros e checksum declarado do arquivo completo identificado como não verificado. Arquivos pequenos RWTH tiveram checksum conferido. Catálogos de membros KAIST/ULT obtidos por Range. Dez testes de aquisição e nove de importadores passaram. Report: `reports/research/public-acquisition-20261101T130629769879/acquisition.json`.

### T03 — Importar e auditar os ciclos da SMART-PDM

Estado: CONCLUIDA
Dependências: T02
Requisitos: RF-03, RF-04, RF-05, RF-06, RF-13

Converter metadados e características da geladeira preservando as chaves originais e a definição dos rótulos.

Critérios de aceite:

- [x] A versão inspecionada reproduz 1.111 ciclos, 1.087 `Normal` e 24 `Malfunction`, ou uma divergência de versão é identificada e explicada.
- [x] O join `Id == begin_end` é um-para-um e tem relatório de chaves órfãs/duplicadas.
- [x] Uma fixture com linhas embaralhadas mantém a associação correta dos rótulos; join por posição não é utilizado.
- [x] Os 100 atributos publicados estão separados de metadados e do alvo; famílias e fórmulas disponíveis estão inventariadas.
- [x] Frequências, escala do canal de vibração, duração dos ciclos e ausência de ID de unidade física estão documentadas sem equivalência presumida aos eixos locais.
- [x] Rótulo original e origem de referência são preservados; `Malfunction` não foi descrito como defeito comprovado do compressor.
- [x] Há decisão sobre quais brutos precisam ser obtidos para responder às análises seguintes, sem baixar o ZIP integral por conveniência.

Evidência: dados importados, manifesto, relatório de qualidade e teste de associação. Verificação: recontagem independente e testes de cardinalidade.

Execução 01/11/2026: 1.111 observações, 1.111 rótulos e 111.100 valores persistidos; 100 features, sem valores numéricos ausentes/não finitos, associação um-para-um. Blocos temporais candidatos: 86 dias UTC, sem presumir identidade física do equipamento. Escala do canal de vibração continua não confirmada. As tabelas publicadas atendem a EDA inicial; brutos adicionais serão obtidos somente se uma hipótese de T11/T13 exigir. Report e hashes: `reports/research/smart_pdm-prepare-3f5bc63bfd8ddbeb6c49/import.json`.

### T04 — Auditar e importar a KAIST quando elegível

Estado: CONCLUIDA
Dependências: T02
Requisitos: RF-03, RF-04, RF-05, RF-06, RF-12, RF-32

Inspecionar os arquivos reais da versão candidata e identificar o que pode participar da pesquisa e do treinamento.

Critérios de aceite:

- [x] Licença, versão, arquivos e disponibilidade efetiva estão confirmados ou o impedimento de acesso está documentado com evidência.
- [x] Uma amostra acessível tem canais, unidades, posições, taxas, cargas, sessões e diagnósticos conferidos.
- [x] A representação mantém as posições/eixos originais; não renomeia posições de mancais para XYZ da carcaça sem justificativa.
- [x] Identidade/grupos e rótulos de origem são preservados; limites de generalização para refrigeração estão registrados.
- [x] Se elegível, o importador tem verificação pequena de formato/cardinalidade; se inelegível, há decisão com motivo, sem registros sintéticos simulando a fonte.
- [x] Dependência de leitura de formato é adicionada somente se necessária e declarada explicitamente.

Evidência: amostra auditada, dicionário e decisão de elegibilidade. Verificação: correspondência entre descrição primária e conteúdo importado.

Execução 01/11/2026: oito arquivos reais (quatro MAT e quatro TDMS) auditados; 288 janelas por canal, 2.304 valores e rótulos de referência preservados. MAT nativo Signal com vibração a 25.600 Hz; posições A/B x/y mantidas. Quatro canais de corrente declarados vazios ficaram ausentes, sem imputação. Escala absoluta MKS/g permanece não confirmada. O primeiro ensaio recusou corretamente canais vazios; parser e fixture foram corrigidos e oito testes passaram. Report: reports/research/kaist-audit-20261101T135438005363/audit.json. Elegibilidade: pesquisa condicional, sem equivalência comprovada à aquisição externa.

### T05 — Importar as condições térmicas e de vibração da RWTH

Estado: CONCLUIDA
Dependências: T02
Requisitos: RF-03, RF-04, RF-05, RF-06, RF-08, RF-12

Relacionar as modalidades por sessão/carga e preservar a diferença entre temperatura de refrigerante e carcaça.

Critérios de aceite:

- [x] Os arquivos pequenos e dicionários são suficientes para a importação inicial; sinais brutos grandes só são obtidos por necessidade demonstrada.
- [x] A versão inspecionada reproduz 195 condições térmicas, 200 condições de RMS XYZ do compressor e 195 associações exatas.
- [x] As cinco condições sem associação térmica são listadas; não há preenchimento por posição ou temperatura inventada.
- [x] O pivot XYZ valida três eixos por condição e mantém unidades, banda e processamento do RMS.
- [x] As nove sessões são identificadas como dependências; contagem de sensores/linhas não é apresentada como número de experimentos independentes.
- [x] Carga de refrigerante e frequência de operação permanecem condições experimentais, sem flag de defeito criada por corte arbitrário.
- [x] Há teste para chave duplicada, eixo ausente e associação incompleta.

Evidência: tabelas canônicas, relatório de associação e testes. Verificação: recontagem por chave composta e comparação ao dicionário original.

Execução 01/11/2026: 195 observações, 195 rótulos indeterminados e 9.360 valores persistidos em nove sessões. As cinco condições sem par estão listadas, sem imputação. Testes de chaves/eixos/banda passaram. Report: `reports/research/rwth_r290-prepare-2daf6e3f19b339730efc/import.json`.

### T06 — Concluir a triagem das demais candidatas

Estado: CONCLUIDA
Dependências: T02
Requisitos: RF-01, RF-03, RF-12, RF-30, RF-32

Avaliar ULT e estudos de compressores específicos, distinguindo arquivo de dados, artigo, catálogo e simulação.

Critérios de aceite:

- [x] Cada candidata citada no inventário tem inspeção ou impedimento documentado antes da decisão de integração.
- [x] ULT possui decisão sobre acesso, licença específica dos dados, sinais, eventos, grupos e aplicabilidade térmica.
- [x] Artigos sem arquivos públicos não são anunciados como datasets prontos para importar.
- [x] Catálogos entram como referência física; datasets sintéticos permanecem identificados e separados da evidência real.
- [x] Novas fontes só são acrescentadas com justificativa ligada a uma lacuna concreta, evitando busca indefinida sem critério de encerramento.

Evidência: tabela de triagem com links primários, estado e justificativa. Verificação: nenhum registro de fonte pode ficar implicitamente aceito apenas porque foi mencionado na conversa.

Execução 01/11/2026: [triagem completa](../../docs/public-source-audit.md). ULT CC0 confirmada no artigo Figshare 24033324; 46 registros de reparos, quatro sem dados e início real da falha desconhecido. Três logs somam 1.531 observações e 16.841 valores, com alvo indeterminado. Modelos de compressores preservados no relatório. Artigos/catálogos permanecem referências sem observações inventadas. Evidência ULT: `reports/research/ult_freezers-audit-20261101T132649030270/audit.json`.

## 4. Etapa 2 — contratos, partições e exploração

### T07 — Canonizar os dados e registrar tratamentos de qualidade

Estado: CONCLUIDA
Dependências: T03, T04, T05, T06, T30
Requisitos: RF-05, RF-06, RF-07, RF-08, RF-29, RF-40, RF-41

Implementar `CanonicalObservation`, proveniência e relatórios de qualidade para as fontes acessíveis.

Critérios de aceite:

- [x] IDs são estáveis e têm namespace da fonte/versão; dados normalizados apontam aos registros originais.
- [x] Ausências, não finitos, parsing inválido, duplicatas e extremos são categorias separadas.
- [x] Cada tratamento tem regra, contagem antes/depois e motivo; extremos não são removidos automaticamente como defeitos de dados.
- [x] Unidade, posição, taxa, banda, significado do tempo e método de calibração estão preenchidos ou explicitamente desconhecidos.
- [x] Campos equivalentes possuem conversão documentada; diferenças físicas não foram escondidas por nomes iguais.
- [x] Fixtures cobrem número inválido, ausência de campo, valor extremo legítimo e duplicação comprovada.

Critérios adicionais da revisão 1.3.0 (verificados nesta rodada):

- [x] O dicionário ampliado liga cada sinal/característica às modalidades, condições e unidades realmente disponíveis; as definições antigas ficam versionadas.
- [x] Novos insumos de T30 possuem qualidade, transformação e proveniência persistidas, ou exclusão/ausência justificada; não há modalidade estimada disfarçada de medida.
- [x] Os dados preparados para relações entre fontes preservam pareamentos, grupos e indicadores de incerteza/ausência.

Evidência: contrato canônico, tabelas e `quality.json`. Verificação: balanço de contagens, rastreabilidade de amostras e testes de validação.

Execução 01/11/2026: canonização relacional concluída para 3.125 observações, com identidade, fonte, definição, condição e linhagem. quality.json distingue zero ausências/não finitos nas características preparadas, quatro canais TDMS declarados vazios e cinco condições RWTH sem associação. Extremos IQR foram mantidos. Testes cobrem duplicata, campo ausente, não finito e extremo legítimo; unidades/horários desconhecidos permanecem explícitos.


Reaberta na revisão 1.3.0: os critérios anteriores preservam o histórico; os critérios adicionais exigem nova execução.


Evidência atual — revisão 1.4.0, 01/11/2026: Nova rodada: TRI 8.363 linhas, NIST 7.375 (uma referência ausente), 82 ciclos de lavadoras e espectros RWTH foram canonizados com unidades, exclusões e linhagem. As tabelas mantêm origem e contratos distintos. Evidências: research-cycle-2.md, execuções tri-hp-prepare, nist-prepare e bridge-materialize; novos casos agregados estão no dataset cycle-reference-8af6bb44817d037a836c.

### T08 — Definir unidade, alvo e grupos de dependência

Estado: CONCLUIDA
Dependências: T07
Requisitos: RF-07, RF-13, RF-14, RF-19, RF-21, RF-32, RF-43, RF-45

Explicitar o significado de uma observação e o mapeamento candidato para normal/anômalo.

Critérios de aceite:

- [x] Cada fonte possui unidade de análise e regra de agrupamento de exemplos relacionados.
- [x] O alvo comum distingue condição física, evento operacional e falha de aquisição; rótulos incompatíveis ficam fora ou indeterminados.
- [x] Rótulos originais de referência são preservados com evidência; nenhum agrupamento os sobrescreve automaticamente.
- [x] Falta de ID de equipamento está registrada; um ciclo não recebe identidade fictícia de equipamento.
- [x] O mapeamento possui versão e relatório de quantos exemplos/classificações aceita ou deixa indeterminados.

Critérios adicionais da revisão 1.3.0 (verificados nesta rodada):

- [x] A definição revista do alvo distingue mau funcionamento do eletrodoméstico, falha do compressor/mancal e evento operacional, com abrangência por fonte.
- [x] Eventos com início incerto e referências parciais têm regra de unidade/episódio e incerteza documentadas, sem janela escolhida para obter um rótulo desejado.
- [x] Probabilidade estimada, confiança do rótulo e classe de referência têm papéis separados; casos sem suporte permanecem indeterminados.

Evidência: dicionário do alvo, `labels.csv` inicial e política de grupos. Verificação: inspeção das classes e casos limítrofes por fonte.

Execução 01/11/2026: config/label-policy-v1.json e labels.csv preservam 1.399 referências e 1.726 alvos indeterminados. O alvo candidato entre eletrodoméstico e mancal é condicional. Blocos semanais conectados SMART, carga KAIST, sessão RWTH e freezer ULT são dependências, sem inventar equipamento por linha.


Reaberta na revisão 1.3.0: os critérios anteriores preservam o histórico; os critérios adicionais exigem nova execução.


Evidência atual — revisão 1.4.0, 01/11/2026: Nova rodada: unidade e alvo por fonte estão explícitos. A candidata usa ciclo operacional concluído e histórico causal; SMART continua referência de funcionamento do eletrodoméstico, NIST/TRI condições experimentais. Falha de componente e evento operacional não foram igualados. Zero rótulos binários derivados foram aceitos; indeterminação permanece preservada.

### T09 — Reservar a avaliação pública antes da análise orientada ao modelo

Estado: CONCLUIDA
Dependências: T08, T29
Requisitos: RF-02, RF-19, RF-21, RF-22, RF-42, RF-44, RF-45

Criar partições reprodutíveis e impedir vazamento por tempo, ciclo, sessão, equipamento ou rótulo derivado.

Critérios de aceite:

- [x] `partitions.csv` identifica observações, grupos e papéis de desenvolvimento/validação/referência reservada.
- [x] Nenhum grupo de dependência cruza a fronteira pertinente e não há registro local no manifesto.
- [x] A estratégia respeita a disponibilidade de classes e declara quando não permite avaliar generalização por equipamento/fonte.
- [x] O protocolo público define métricas, comparações, acesso permitido às partições e política de geração de rótulos antes dos experimentos orientados.
- [x] Testes detectam interseção de grupos, observação duplicada entre partições e origem externa camuflada.
- [x] Partições e sementes estão congeladas por versão; mudanças posteriores geram nova versão com justificativa.

Critérios adicionais da revisão 1.3.0 (verificados nesta rodada):

- [x] O acesso da nova rodada identifica validação anterior como conhecida e mantém os 293 ciclos SMART de teste selados; nenhum split é trocado para melhorar métricas.
- [x] Há grupos/partições explícitos para ajuste de pontes, geração de derivados, calibração e avaliação com referência independente.
- [x] Desenhos indutivo e transdutivo estão separados; suporte insuficiente para avaliar uma fonte/equipamento é declarado, sem chamar grupos artificiais de equipamentos.

Evidência: manifesto de partições e testes de isolamento. Verificação: interseções vazias e reprodução dos IDs a partir da configuração.

Execução 01/11/2026: snapshot public-study-87d04baa2e265aeb persistido. Seed selecionado 2029 por suporte de classes/grupos, sem consultar métricas. SMART tem 511/307/293 ciclos em treino/validação/teste; os 293 ficaram reservados. Partições e política possuem hashes e vínculo aos rótulos. Testes de sobreposição, identidade duplicada e origem externa passaram. A tentativa inicial de dois grupos positivos por papel era inviável e foi revista antes da modelagem.


Reaberta na revisão 1.3.0: os critérios anteriores preservam o histórico; os critérios adicionais exigem nova execução.


Evidência atual — revisão 1.4.0, 01/11/2026: Nova rodada: folds SMART fixos foram mantidos, a validação antiga virou desenvolvimento conhecido e o teste 293 permaneceu reservado até o congelamento. Encoders e calibração usam cross-fitting aninhado por grupos. O dia TRI OC também foi reservado. A avaliação final consumiu essas reservas uma única vez, sem retuning.

### T10 — Executar análise descritiva e exploratória nas fontes públicas

Estado: CONCLUIDA
Dependências: T09, T30
Requisitos: RF-09, RF-10, RF-21, RF-22, RF-32, RF-39, RF-40

Produzir o primeiro relatório que descreve efetivamente todas as fontes acessíveis, sem treinar o classificador final.

Critérios de aceite:

- [x] Relatório contém suporte, ausências, quantis, variabilidade, distribuições e evolução por fonte, regime e classe conhecida onde disponível.
- [x] Relações Pearson/Spearman ou outras escolhidas usam observações realmente associadas e informam suporte, grupos e limitações.
- [x] Há gráficos exportáveis com eixos/unidades e tabelas reproduzíveis; decisões não dependem de execução manual escondida.
- [x] Efeito de fonte, período, equipamento e padrão de ausências é examinado como possível atalho.
- [x] Dados reservados não foram usados para selecionar características, limiares ou regras de associação.
- [x] Nenhum valor ou distribuição local foi usado para ajustar a exploração pública.

Critérios adicionais da revisão 1.3.0 (verificados nesta rodada):

- [x] A análise ampliada cobre famílias além das três estatísticas do piloto e compara padrões relevantes ao funcionamento de refrigeração.
- [x] Relações por regime/carga/velocidade/período e relações não lineares ou temporais justificadas são avaliadas, ou sua ausência de suporte é demonstrada.
- [x] Um mapa de variáveis comuns, auxiliares e modalidades pareadas aponta hipóteses concretas e insumos para T11/T31, com resultados relacionais auditáveis.

Evidência: relatório de EDA, tabelas, gráficos e configuração da execução. Verificação: reprodução de estatísticas centrais e revisão de proveniência.

Execução 01/11/2026: EDA concluída no papel train das quatro fontes. Tabelas por classe/grupo, quantis, correlações pareadas, cobertura, distribuições e evolução exportadas; 2.360 estatísticas totais persistidas com origem/suporte. A auditoria TDMS contém estatísticas térmicas/elétricas separadas. Oito gráficos foram exportados; o gráfico SMART recebeu revisão apenas visual em figures-v2, sem alterar resultados. Nenhum dado local ou teste público reservado orientou a análise.


Reaberta na revisão 1.3.0: os critérios anteriores preservam o histórico; os critérios adicionais exigem nova execução.


Evidência atual — revisão 1.4.0, 01/11/2026: Nova rodada: análises ampliadas de 100 características SMART, espectros 46 por canal, grandezas térmicas, controles de regime e contexto temporal foram executadas. Pontes fora de sessão e correlações realmente pareadas estão nos relatórios. O complemento descritivo transfer-description-177a2b9f535be5c3f36c persistiu 252 estatísticas de entradas conhecidas após o congelamento, sem mudar a seleção.

### T11 — Definir características candidatas e matriz de compatibilidade

Estado: CONCLUIDA
Dependências: T10
Requisitos: RF-07, RF-08, RF-12, RF-15, RF-18, RF-41, RF-42, RF-46

Desenhar uma representação candidata ao modelo único e verificar sua possibilidade de aplicação pela interface conhecida.

Critérios de aceite:

- [x] Toda característica candidata tem fórmula, grandeza, unidade, posição, taxa/banda e unidade de análise.
- [x] Matriz classifica cada relação como comparável, condicional, desconhecida ou incompatível, com motivo.
- [x] RMS espacial, RMS temporal, eixos e canais escalares permanecem distinguíveis; não há equivalência por nome.
- [x] Contrato de aplicação usa somente o esquema e a documentação da aquisição, sem consultar leituras locais para escolher características.
- [x] Sinais auxiliares ausentes na aquisição não viram entradas obrigatórias de produção sem uma estratégia demonstrável.
- [x] A escolha mantém em aberto contribuição multibase, redução justificada de características e revisão após os experimentos.

Critérios adicionais da revisão 1.3.0 (verificados nesta rodada):

- [x] Mais de uma família de representação é considerada, com fórmulas e critérios de descarte; três momentos de vibração não são o limite pré-fixado da pesquisa.
- [x] Existe grafo/tabulação das relações candidatas, incluindo pontes intermediárias e seus pressupostos, sem promover caminhos ainda não testados a associações aceitas.
- [x] Variáveis auxiliares de estudo e entradas candidatas da aplicação ficam separadas; a portabilidade local tem estado próprio e não impede testar hipóteses públicas.

Evidência: matriz de compatibilidade e contrato candidato de características. Verificação: rastrear uma entrada candidata desde cada fonte até o formato exigido pela aplicação.

Execução 01/11/2026: compatibility.json e relatório de viabilidade definem skewness ajustada, curtose sem viés e amplitude/desvio populacional como candidatos condicionais. A matriz preserva bandas, posições e suporte temporal; RMS espacial da API não foi renomeado para RMS temporal. O contrato local foi inspecionado somente no código/schema. A representação não é atualmente reproduzível de forma demonstrada pela aquisição conhecida.


Reaberta na revisão 1.3.0: os critérios anteriores preservam o histórico; os critérios adicionais exigem nova execução.


Evidência atual — revisão 1.4.0, 01/11/2026: Nova rodada: famílias publicadas, espectrais, adimensionais, proxies e contexto temporal foram comparadas. A candidata final usa quatro descritores de normalidade com encoders específicos por fonte; não presume equivalência física. RF-47–RF-50 e cycle-candidate-report.md explicitam fórmulas, entradas e incompatibilidade do POST atual com limites reais de ciclo.

### T12 — Investigar grupos e atipicidade onde forem úteis

Estado: CONCLUIDA
Dependências: T11
Requisitos: RF-11, RF-14, RF-19, RF-40, RF-43

Executar agrupamento ou detecção de atipicidade para responder às hipóteses de estrutura das bases sem rótulo; dispensar método sem utilidade com justificativa.

Critérios de aceite:

- [x] Escolha ou dispensa de cada método tem pergunta de pesquisa e justificativa.
- [x] Métodos executados registram entradas, escala, parâmetros, semente quando aplicável e partição utilizada.
- [x] Sensibilidade e estabilidade são examinadas por grupos/sessões e por parâmetros relevantes.
- [x] Perfis dos grupos são confrontados com condições e referências disponíveis sem converter raridade em defeito automático.
- [x] Saídas de cluster/escore permanecem distintas de rótulos reais e não consomem o conjunto externo.

Critérios adicionais da revisão 1.3.0 (verificados nesta rodada):

- [x] Perfis de agrupamentos são confrontados com a âncora SMART e regimes das fontes candidatas em representações justificadas.
- [x] Atipicidade/normalidade é comparação auxiliar documentada; não substitui a investigação de ligação nem a Random Forest principal.
- [x] Qualquer proposta de correspondência de grupo/rótulo aponta à evidência e à avaliação independente exigida em T13.

Evidência: tabelas de grupos, perfis e análise de sensibilidade ou decisão de dispensa. Verificação: repetibilidade e revisão do significado atribuído aos grupos.

Execução 01/11/2026: KMeans 2/3/4 e Isolation Forest 1%/5%/10%, com escala ajustada apenas no train por fonte, parâmetros, seed, perfis e dependências registrados. Persistidas 10.986 atribuições/escores. A estabilidade por exclusão fica não estimável para a única carga KAIST no treino. Clusters e escores não alteraram nenhum rótulo.


Reaberta na revisão 1.3.0: os critérios anteriores preservam o histórico; os critérios adicionais exigem nova execução.


Evidência atual — revisão 1.4.0, 01/11/2026: Nova rodada: Isolation Forest auxilia os descritores comuns, com referência normal e cross-fitting, mantendo RF como classificador principal. Rodadas 6–8 confrontaram os perfis com referências SMART e térmicas. Não houve correspondência de grupo promovida a rótulo físico; esse caminho não aplicável permanece documentado, sem pseudorrótulos aceitos.

## 5. Etapa 3 — integração e rótulos derivados


### T13 — Investigar correspondências, transferência e fusão

Estado: CONCLUIDA
Dependências: T11, T12, T31
Requisitos: RF-10, RF-13, RF-14, RF-15, RF-16, RF-19, RF-41, RF-42, RF-43, RF-44, RF-45

Testar se referências da SMART-PDM e de outras fontes podem sustentar associações e novos exemplos rotulados numa representação comum.

Critérios de aceite:

- [x] Cada experimento declara variáveis compartilhadas, grandezas associadas, hipóteses, domínio e dados usados.
- [x] Dados públicos de ligação são identificados quando existem; relações não identificáveis têm incerteza registrada, sem coeficiente empírico inventado.
- [x] Associação de grupos/rótulos usa evidência além da coincidência de quantidade ou tamanho dos grupos.
- [x] Rótulos derivados têm método, versão, proveniência, confiança quando estimável e estado indeterminado para casos sem suporte.
- [x] A validação da transferência usa referências independentes de sua geração; pseudorrótulo não é apresentado como verdade externa.
- [x] Nenhuma linha é apresentada como medição conjunta real se suas modalidades foram apenas associadas por hipótese.
- [x] Os experimentos e artefatos intermediários não leem dados do protótipo.

Critérios adicionais da revisão 1.3.0 (verificados nesta rodada):

- [x] A referência SMART é usada como âncora de experimentos concretos de transferência; referências conhecidas da fonte-alvo não participam da própria geração quando usadas para avaliá-la.
- [x] São comparados caminhos diretos, via ponte e alinhamento pertinentes, ou há impedimento específico por caminho prioritário.
- [x] O efeito da inclusão de outras fontes é separado, quando viável, de tamanho de amostra, desbalanceamento e quantidade de exemplos por grupo.
- [x] Rótulos fracos/transferidos e modalidades estimadas preservam incerteza, regras de aceitação, ponderação/abstinência e cobertura dos casos excluídos.
- [x] Estimativas probabilísticas possuem escopo e avaliação próprios; concordância com pseudorrótulos não valida probabilidade física.

Evidência: `integration.json`, candidatos a `LabelRecord`, experimentos e referências reservadas. Verificação: auditoria de um rótulo derivado até suas entradas e evidências.

Execução 01/11/2026: comparações fixas SMART, KAIST, referências combinadas e baseline majoritário concluídas, com 2.706 saídas escalares persistidas e referência independente de validação. A transferência entre as fontes não atendeu ao protocolo em SMART. RWTH/ULT mantiveram alvos indeterminados; zero pseudorrótulos aceitos. Três acoplamentos teóricos das marginais demonstram relações conflitantes, explicitamente sem correlação empírica conjunta ou criação de linhas pareadas.


Reaberta na revisão 1.3.0: os critérios anteriores preservam o histórico; os critérios adicionais exigem nova execução.


Evidência atual — revisão 1.4.0, 01/11/2026: Nova rodada: caminhos diretos, pontes RWTH, proxy de regime, lavadoras e normalidade foram testados. A rodada 8 separou efeito de composição/limiar e incluiu três permutações por fonte. Rótulos auxiliares reais em três fontes obtiveram AP 0,5325, contra 0,1616–0,2567 nos controles. Modalidades estimadas da rodada 4 permaneceram marcadas como estimadas; nenhuma virou medição real.

### T14 — Concluir a viabilidade da integração antes do treinamento final

Estado: CONCLUIDA
Dependências: T03, T04, T05, T06, T10, T11, T12, T13, T29, T30, T31
Requisitos: RF-01, RF-12, RF-14, RF-15, RF-16, RF-21, RF-32, RF-39, RF-44, RF-45, RF-46

Produzir a decisão que autoriza ou impede a consolidação pretendida.

Critérios de aceite:

- [x] Cada fonte/associação tem decisão `supported`, `conditional` ou `unsupported`, com condições e evidência.
- [x] Comparações incluem sem/com transferência, referência apenas versus referência mais derivados e sensibilidade às hipóteses.
- [x] Resultados por origem/grupo e possíveis atalhos de fonte/ausência foram examinados; limitações de suporte estão explícitas.
- [x] Há contagem de exemplos candidatos por fonte, classe e tipo de rótulo; participação efetivamente multibase foi demonstrada ou a lacuna foi registrada.
- [x] A decisão informa quais condições faltam para T15, sem substituir silenciosamente o objetivo por treinamento somente SMART-PDM.
- [x] Se a investigação for negativa, existe evidência e próxima decisão; T15/T17 continuam bloqueadas enquanto seus requisitos não forem satisfeitos.

Critérios adicionais da revisão 1.3.0 (verificados nesta rodada):

- [x] Cada hipótese prioritária da rodada tem execução ou impedimento demonstrado; resultado negativo aponta próxima hipótese/busca em vez de encerrar por repetição do piloto.
- [x] A decisão separa public_integration_decision, public_probability_support, local_portability_status e external_release_decision.
- [x] Critérios e suporte registrados em T29, incluindo incerteza e possíveis resultados inconclusivos, são aplicados sem redefinição após observar métricas.
- [x] A generalização entre fontes/equipamentos é sustentada pelo desenho efetivamente possível; origem facilmente identificável não determina aprovação/reprovação sozinha.
- [x] Uma candidata pública pode avançar para T15–T17 quando seus critérios forem cumpridos, sem afirmar prontidão para o compressor local.

Evidência: relatório de viabilidade e decisões de inclusão/exclusão. Verificação: todas as candidatas foram consideradas e a conclusão pode ser reconstruída a partir dos experimentos.

Execução 01/11/2026: decisão unsupported_for_current_application. O combinado detectou 45/48 janelas anômalas KAIST e 0/1 ciclo anômalo SMART na validação, com suporte limitado e diferenças de alvo. O classificador de origem atingiu 99,78%. As contagens por origem/status e a matriz de compatibilidade estão documentadas. Comparação referência+derivados: não aplicável, pois nenhum derivado admissível foi obtido; isso não foi substituído por rótulos fabricados. T15/T17 não foram liberadas.


Reaberta na revisão 1.3.0: os critérios anteriores preservam o histórico; os critérios adicionais exigem nova execução.


Evidência atual — revisão 1.4.0, 01/11/2026: Nova decisão: a candidata pública SMART/NIST/TRI cumpriu os critérios agregados do protótipo. Probabilidade continua experimental/limitada, portabilidade local pendente e liberação externa não concedida. H06 não permite alvo fino a partir de eventos ULT incertos; H08 não permite reconstruir banda de vibração a partir de pacotes esparsos sem antialiasing. Isso não impediu testar a alternativa por ciclos.

## 6. Etapa 4 — consolidação e contratos de software


### T15 — Materializar e congelar o dataset consolidado elegível

Estado: CONCLUIDA
Dependências: T09, T11, T14
Requisitos: RF-02, RF-13, RF-14, RF-17, RF-18, RF-19, RF-29, RF-43, RF-45, RF-46

Produzir a fonte final versionada de treinamento, com rastreabilidade e partições.

Critérios de aceite:

- [x] Há contribuição elegível de pelo menos duas fontes públicas para declarar resultado multibase; fonte única mantém esse objetivo pendente.
- [x] Matriz de treinamento, rótulos, grupos, partições e contrato estão ligados por IDs únicos e hashes.
- [x] Rótulos de referência, derivados e indeterminados são distinguíveis; os indeterminados não entram como `0` ou `1` por conveniência.
- [x] As duas classes e a avaliação de referência têm suporte compatível com o protocolo; insuficiência impede liberar o treino final.
- [x] Exclusões e características ausentes têm política explícita; dados externos locais e suas derivações são rejeitados.
- [x] Regenerar a versão com as mesmas entradas/configuração reproduz conteúdo e IDs; uma nova versão não sobrescreve a anterior.

Critérios adicionais da revisão 1.3.0 (verificados nesta rodada):

- [x] O manifesto distingue candidata pública elegível de liberação externa e registra a portabilidade ainda condicional/desconhecida.
- [x] Probabilidades de rótulo não são passadas como classe contínua ao RandomForestClassifier; conversão/ponderação de derivados é explícita e reproduzível.

Evidência: dataset, manifesto, contrato e relatório de composição/exclusões. Verificação: validação completa de elegibilidade e repetição determinística da materialização.


Bloqueio histórico do primeiro ensaio, superado nesta rodada, registrado em 01/11/2026: T14 não demonstrou representação multibase com rótulos defensáveis e entradas locais reproduzíveis. Retomar após evidência de aquisição/representação e nova investigação pública aprovada; não consolidar pseudorrótulos para preencher o requisito.


Histórico anterior à rodada atual — revisão 1.3.0: o bloqueio aguardava a nova decisão pública e dependências; detalhes faltantes do ESP32 não impedem continuar T29–T31/T10–T14.


Evidência atual — revisão 1.4.0, 01/11/2026: Concluído para pesquisa pública: dataset cycle-reference-8af6bb44817d037a836c com 782 SMART, 294 NIST e 35 TRI, ambas as classes e referências originais. Entradas, quatro características por caso, rótulos, membros e manifesto estão ligados no banco. Reexecução de treino em entradas congeladas reproduziu exatamente os escores públicos; a checagem relacional verifica a matriz. O joblib reserializado não foi anunciado como idêntico byte a byte; o original ficou preservado.

### T16 — Adaptar o backend ao contrato multibase

Estado: CONCLUIDA
Dependências: T15
Requisitos: RF-07, RF-08, RF-17, RF-18, RF-25, RF-29, RF-30, RF-45, RF-46

Separar ingestão pública, características e ajuste do estimador, reusando a implementação existente quando compatível.

Critérios de aceite:

- [x] Treinamento público não exige consulta ao banco do protótipo nem medições fictícias marcadas `FINALIZADA`.
- [x] Um mesmo contrato e implementação de características/transforms atende treino e inferência do novo modelo.
- [x] Mudança de nomes, ordem, fórmula ou semântica possui versão nova; verificações dos artefatos antigos não foram enfraquecidas.
- [x] Chamadores, CLI, configuração, exports e fixtures afetados foram atualizados de forma coerente.
- [x] Testes rejeitam contrato incorreto, unidade incompatível, entrada inválida e ausência sem política definida.
- [x] Não há nova infraestrutura ou dependência sem necessidade; a aquisição e o banco compartilhado permanecem preservados.

Critérios adicionais da revisão 1.3.0 (verificados nesta rodada):

- [x] Contrato de saída separa escore, probabilidade calibrada quando sustentada, alerta, suporte de domínio e motivo de recusa; artefatos persistem o calibrador quando aplicável.

Evidência: diff, testes de contrato, exemplos locais e documentação do novo caminho. Verificação: testes direcionados de características, ML, artefatos, serviços e CLI afetados.


Histórico anterior à rodada atual — revisão 1.3.0: o bloqueio aguardava a nova decisão pública e dependências; detalhes faltantes do ESP32 não impedem continuar T29–T31/T10–T14.


Evidência atual — revisão 1.4.0, 01/11/2026: Implementado contrato cycle-context-normality-v1 em cycle_candidate.py, cálculo causal compartilhado, CLI predict-cycles, artefato e fixture explícita. O loader legado não foi afrouxado. Pacotes instantâneos são recusados no caminho por ciclos; contexto ausente não recebe classe normal. Testes cobrem identidade, horários, contexto, origem, corrupção e diretório confiável.

## 7. Etapa 5 — treinamento, protocolo e congelamento


Bloqueio registrado em 01/11/2026: falta o contrato final elegível de T15. As 20 características e o serviço legado não foram anunciados como adaptação multibase concluída.

### T17 — Treinar e avaliar a Random Forest usando apenas dados públicos

Estado: CONCLUIDA
Dependências: T16
Requisitos: RF-02, RF-19, RF-20, RF-21, RF-22, RF-32, RF-42, RF-44, RF-45, RF-46

Executar desenvolvimento supervisionado após a consolidação, preservando as reservas de avaliação.

Critérios de aceite:

- [x] Treino aponta para a versão congelada de T15; parâmetros e sementes estão registrados.
- [x] Ajustes de escala, imputação, seleção, reamostragem e hiperparâmetros usam somente partições permitidas.
- [x] Existe comparação com a classe majoritária; acurácia isolada não determina liberação.
- [x] Relatório inclui confusão, acurácia, precisão, recall, F1, falsos positivos, suporte e métricas por fonte/grupo viável.
- [x] Avaliação em referências independentes está separada da concordância com rótulos derivados; métricas sem suporte são não estimáveis.
- [x] O efeito da origem e a contribuição das fontes estão analisados; nenhuma entrada de identificação serve de atalho do alvo.
- [x] Resultados e limites atendem ao protocolo público; falha reabre a etapa causal antes de liberar o teste externo.

Critérios adicionais da revisão 1.3.0 (verificados nesta rodada):

- [x] O relatório compara a contribuição das fontes/alinhamentos ao baseline SMART e controla atalhos e composição segundo T29.
- [x] Discriminação e alertas são avaliados juntamente com confiabilidade/Brier/log loss quando houver suporte, sem tomar um escore isolado como prova de calibração.
- [x] Calibrador e limiar usam partições públicas apropriadas; métricas, prevalência e suporte por classe/grupo acompanham a estimativa.
- [x] Falta de 100% de acerto não reprova por si só; os critérios predefinidos de risco, cobertura e incerteza determinam o resultado e a próxima rodada.

Evidência: artefato de pesquisa, configuração, manifestos e relatório público. Verificação: reprodução do split e das métricas sobre os IDs reservados.


Bloqueio histórico do primeiro ensaio, superado nesta rodada, registrado em 01/11/2026: gate T14 reprovado para liberação. As três Random Forests do piloto são experimentos transitórios; não foi treinado/registrado o artefato final pretendido.


Histórico anterior à rodada atual — revisão 1.3.0: o bloqueio aguardava a nova decisão pública e dependências; detalhes faltantes do ESP32 não impedem continuar T29–T31/T10–T14.


Evidência atual — revisão 1.4.0, 01/11/2026: Modelo cycle-freeze-8af6bb44817d037a836c treinado e avaliado. No teste reservado: SMART TP10/FN1/FP21/TN252, nove recusas; TRI TP1/FN1. Agregado passou critérios: recall 0,8462, balanced accuracy 0,8846, FPR 0,0769, AP 0,7076. Baseline, calibração limitada, suporte por fonte/grupo e intervalos descritivos estão em cycle-candidate-report.md. Não houve alteração após observar o teste.

### T18 — Definir o protocolo de teste externo e a referência real

Estado: EM_EXECUCAO
Dependências: T14, T17
Requisitos: RF-23, RF-26, RF-27, RF-32, RF-45, RF-46

Planejar a campanha do protótipo sem observar seus resultados para decidir critérios de sucesso.

Critérios de aceite:

- [ ] Protocolo define unidade, vínculo às leituras, procedimento, condições observáveis e registro de equipamento/regime.
- [ ] Referência real registra observador, evidência, instante, condição e confiança, independentemente da previsão.
- [ ] Metas quantitativas, cobertura/amostra pretendidas e decisões de sucesso/reprovação/inconclusão estão preenchidas e justificadas antes do teste.
- [ ] Há regra para ausência de classe, caso indeterminado e entrada recusada; avaliação somente normal não prova recall de falhas.
- [ ] A exposição anterior ao backup está declarada; a reserva prospectiva da campanha principal está definida.
- [ ] O protocolo não exige provocar avarias perigosas nem uma nova frota de compressores para iniciar a avaliação local.

Critérios adicionais da revisão 1.3.0 (pendentes):

- [ ] O protocolo distingue validação de risco probabilístico de um diagnóstico confirmado e prevê suporte insuficiente para calibração/recall.

Evidência: `external-protocol.json` e ficha de referência. Verificação: revisão do procedimento sem consultar medições ou previsões da campanha reservada.


Bloqueio registrado em 01/11/2026: unidade/contrato e modelo final não estão definidos e liberados. Não foram inventados metas, referência real ou procedimento de teste a partir das saídas do piloto.


Progresso 1.4.0: config/external-cycle-protocol.json define amostra, referência independente, metas e reserva prospectiva. Falta confirmar a rotina de captura dos limites reais; não há coleta física nem procedimento confirmado do operador.

### T19 — Congelar a versão candidata ao teste externo

Estado: BLOQUEADA
Dependências: T17, T18, T20
Requisitos: RF-23, RF-25, RF-29, RF-45, RF-46

Publicar localmente uma versão imutável com o conjunto completo de decisões de inferência.

Critérios de aceite:

- [ ] Modelo, transformações aprendidas, contrato, limiar e política de incompatibilidade estão persistidos juntos ou por vínculos com hashes.
- [ ] Manifesto inclui versões do ambiente, código, datasets, composição, partições, métricas e protocolo externo.
- [ ] Estado `frozen_for_external_test` distingue a versão de pesquisa e de qualquer conclusão posterior de validação.
- [ ] Carregamento valida integridade e compatibilidade; artefato não confiável ou incompatível é recusado.
- [ ] Versão existente não é sobrescrita e nenhuma decisão congelada dependeu de dados do protótipo.

Critérios adicionais da revisão 1.3.0 (pendentes):

- [ ] A compatibilidade documentada por T20 permite calcular as entradas da candidata; caso contrário, fica como modelo de pesquisa e a liberação externa permanece bloqueada.
- [ ] Calibrador, score_kind, probability_scope e calibration_status acompanham a versão quando aplicáveis.

Evidência: artefato, manifesto de congelamento e testes de carga/corrupção/versão. Verificação: hash estável e reprodução da inferência numa fixture compatível.


Bloqueio registrado em 01/11/2026: não existe candidato final aprovado nem protocolo externo completo para congelar. Nenhum artefato recebeu frozen_for_external_test.


Bloqueio atual 1.4.0: existe artefato público congelado e loader verificado; o estado permanece frozen_public_research_candidate. Falta confirmar compatibilidade local e encerrar T18/T20 antes de frozen_for_external_test.

### T20 — Preparar o adaptador externo sem alterar a aquisição

Estado: EM_EXECUCAO
Dependências: T16, T17, T18
Requisitos: RF-02, RF-18, RF-24, RF-25, RF-30, RF-45, RF-46

Implementar importação/consulta de leitura e associação dos casos usando o esquema conhecido e fixtures artificiais.

Critérios de aceite:

- [ ] Adaptador consome exportação ou leitura do contrato existente, sem exigir mudança prévia no firmware ou API.
- [ ] Identidade e unidade de cada caso são explícitas; segmentos/ciclos exigem limites e IDs comprováveis, sem janela arbitrária de 15 segundos.
- [ ] Offsets/filtros da API não são aplicados novamente; RMS espacial não é tratado como temporal.
- [ ] Sinal incompatível, unidade desconhecida e valor inválido geram recusa rastreável, sem classificação normal automática.
- [ ] Não há ajuste do modelo ou de transformações durante inferência externa; testes usam fixtures, sem abrir a campanha reservada.
- [ ] Se a coleta não atender ao contrato, existe relatório da incompatibilidade e da menor alternativa, sem mudança compartilhada executada implicitamente.

Critérios adicionais da revisão 1.3.0 (pendentes):

- [ ] A preparação usa candidata pública e fixtures sem abrir a campanha reservada; a execução real posterior exige T19.
- [ ] O resultado de compatibilidade é separado da qualidade pública do modelo e propõe a menor alternativa quando as entradas locais não forem suficientes.

Evidência: adaptador, fixtures e testes de integração local. Verificação: entradas compatíveis/incompatíveis e inspeção de ausência de escrita na aquisição.


Bloqueio registrado em 01/11/2026: falta modelo/contrato final compatível. A matriz registra a incompatibilidade e a menor próxima ação: confirmar o sinal já adquirido e eventual forma de onda disponível, antes de propor mudanças na API/firmware.


Progresso 1.4.0: CLI de pesquisa e fixture por ciclos funcionam. O POST atual não fornece limites reais; a alternativa de anotação do operador foi proposta e ainda não confirmada. Não foi feita conversão automática de pacotes em ciclos, nem leitura de campanha privada. Falta concluir adaptação/persistência da campanha escolhida.

### T21 — Verificar o fluxo integrado e regressões antes do teste real

Estado: BLOQUEADA
Dependências: T03, T16, T17, T19, T20
Requisitos: RF-02, RF-19, RF-20, RF-22, RF-25, RF-29, RF-30, RF-31

Executar um ensaio de software completo e os checks pertinentes sem consumir o teste externo real.

Critérios de aceite:

- [ ] Fixture pequena percorre importação, consolidação, treino, carga e inferência com proveniência verificável.
- [ ] Há teste negativo ponta a ponta para origem local no desenvolvimento e para interseção de grupos.
- [ ] Métricas indefinidas, corrupção de artefato e falhas de associação têm saídas claras.
- [ ] Testes afetados, suíte de regressão pertinente e checks Ruff passam; qualquer exceção tem justificativa explícita e não mascara critério obrigatório.
- [ ] Relatórios distinguem ensaio sintético de software e avaliação científica com dados reais públicos.
- [ ] MySQL compartilhado não recebeu DDL/escrita; teste MySQL isolado é executado somente se uma mudança específica o exigir.

Evidência: resultados dos testes/checks e relatório do ensaio. Verificação: comandos existentes descritos no plano e testes novos ligados aos requisitos.


Progresso 1.4.0: regressão final com 306 testes aprovados e um opt-in legado ignorado; testes locais MariaDB executados. Ensaio por fixture e loader passaram. Fluxo externo completo continua pendente de T19/T20.

## 8. Etapa 6 — teste externo


Bloqueio registrado em 01/11/2026: regressão de software passou com 268 testes e um opcional ignorado, mas o fluxo novo completo com artefato final e adaptador externo não existe por T14. Testes legados e piloto não substituem esse critério.

### T22 — Coletar e registrar a campanha externa do protótipo

Estado: BLOQUEADA
Dependências: T18, T19, T20, T21
Requisitos: RF-02, RF-23, RF-26, RF-27, RF-30

Obter medições reservadas e referência real segundo o protocolo congelado. A execução depende da disponibilidade do equipamento e do observador; não é simulação de conclusão automática.

Critérios de aceite:

- [ ] Campanha e datas estão identificadas; os arquivos possuem hashes e origem externa preservada.
- [ ] Cada caso tem vínculo verificável às leituras e à unidade definida no protocolo.
- [ ] Condição real, evidência, observador e instante são registrados independentemente da previsão.
- [ ] Casos indeterminados ou fora do contrato permanecem registrados; não recebem rótulo para completar a amostra desejada.
- [ ] Modelo e critérios já estavam congelados; nenhum registro da campanha entrou no desenvolvimento.
- [ ] Procedimento e abrangência real da coleta estão documentados, incluindo falta de alguma condição prevista.

Evidência: manifesto externo e fichas de referência, preservando dados privados fora do Git. Verificação: auditoria de identidade, datas, independência e cobertura.


Bloqueio registrado em 01/11/2026: falta liberação anterior, campanha física reservada e referência independente observada. Nenhuma coleta ou condição física foi simulada para concluir a tarefa.


Bloqueio atual 1.4.0: a candidata pública existe; faltam confirmação de limites locais, liberação específica e campanha física com referência observada. Não foram gerados acertos locais artificiais.

### T23 — Aplicar o modelo congelado e avaliar os acertos reais

Estado: BLOQUEADA
Dependências: T22
Requisitos: RF-23, RF-25, RF-26, RF-27, RF-28, RF-29, RF-45, RF-46

Executar inferência e comparar a saída à referência observada do compressor local.

Critérios de aceite:

- [ ] Hash e contrato do modelo são conferidos antes/depois da campanha; não houve ajuste na avaliação.
- [ ] Predições e recusas são preservadas para todos os casos processados, com versão e motivo quando aplicável.
- [ ] A associação com referência usa `external_case_id` único e relatório de casos sem par, sem join posicional.
- [ ] Métricas são calculadas nos casos de referência confirmada; cobertura, indeterminados, recusas e suporte por classe estão separados.
- [ ] Resultado é confrontado aos critérios prévios e classificado como satisfatório, reprovado, parcial ou inconclusivo, com justificativa.
- [ ] Ausência de defeitos observados não é apresentada como validação da capacidade de detectar falhas.
- [ ] Se houver revisão motivada pelo resultado, a campanha fica marcada como conhecida para versões futuras e nova reserva é exigida para teste independente.

Critérios adicionais da revisão 1.3.0 (pendentes):

- [ ] Qualidade probabilística é medida apenas com suporte e referência adequados; alertas/escores não são contados como confirmação física de defeito.

Evidência: predições, métricas, comparação com referências e decisão externa. Verificação: recomputação das contagens TP/TN/FP/FN e auditoria do congelamento.


Bloqueio atual 1.4.0: a candidata pública existe; faltam confirmação de limites locais, liberação específica e campanha física com referência observada. Não foram gerados acertos locais artificiais.

## 9. Etapa 7 — conclusão e manutenção


Bloqueio registrado em 01/11/2026: não há campanha externa elegível nem modelo congelado. Acurácia do compressor local não foi calculada ou anunciada.

### T24 — Consolidar a documentação final e o estado do objetivo

Estado: CONCLUIDA
Dependências: T23; se houver impedimento anterior, registrar entrega parcial sem concluir tarefas não atendidas
Requisitos: RF-28, RF-29, RF-30, RF-31, RF-32, RF-39, RF-46

Atualizar o SDD e a documentação operacional para refletir resultados e decisões, incluindo limites ou inviabilidade.

Critérios de aceite:

- [x] Relatório informa fontes auditadas, aceitas/rejeitadas, contribuição efetiva, contrato e origem dos rótulos.
- [x] Avaliação de software, avaliação pública e teste externo estão separados, com links às evidências.
- [x] README e documentos afetados descrevem o comportamento efetivamente implementado; propostas antigas não são anunciadas como fluxo novo pronto.
- [x] Requisitos e tarefas possuem estado coerente; critério reprovado ou sem evidência permanece aberto ou em correção/bloqueio.
- [x] Mudanças de escopo são explícitas e não transformam resultado de fonte única ou domínio distinto em sucesso multibase local.
- [x] Resultados negativos, exposição prévia ao histórico e necessidade de nova campanha após ajustes permanecem visíveis.
- [x] Credenciais e dados privados não aparecem nos documentos versionáveis.

Critérios adicionais da revisão 1.3.0 (verificados nesta rodada):

- [x] A rodada 1.3 e seguintes registram hipóteses, pontes, buscas adicionais, contribuições efetivas, calibração e decisões pública/local separadas.
- [x] O estado de cada tarefa e dos critérios ampliados é coerente com os novos resultados; o primeiro ensaio permanece preservado como histórico.

Evidência: relatório de conclusão/entrega parcial, atualização documental e matriz final de rastreabilidade. Verificação: revisão cruzada de especificação, plano, tarefas, artefatos e resultados.

Entrega parcial documentada em 01/11/2026 conforme a exceção prevista para impedimento anterior. Relatório docs/public-feasibility-report.md, execução docs/development-execution.md, README e estados SDD atualizados. Avaliação de software, experimento público e ausência de teste externo estão separados. O objetivo completo permanece aberto.


Reaberta na revisão 1.3.0: os critérios anteriores preservam o histórico; os critérios adicionais exigem nova execução.


Evidência atual — revisão 1.4.0, 01/11/2026: Entrega parcial atualizada: relatórios das rodadas, candidata pública, protocolo prospectivo, banco e estados SDD estão coerentes. O objetivo completo permanece aberto pela portabilidade e campanha física, sem usar dados do protótipo no desenvolvimento. O primeiro ensaio negativo continua preservado.

## 10. Condições que impedem avanço indevido

| Condição observada | Ação obrigatória |
| --- | --- |
| Fonte sem licença/acesso confirmado | Manter pendente/inapta até a evidência correspondente; não distribuir conteúdo sem base |
| Join incorreto ou origem incompleta | Reabrir importação/canonização; invalidar derivados afetados |
| Grupos vazando para avaliação | Refazer partições e repetir experimentos afetados |
| Pseudorrótulos sem referência independente para avaliar a regra | Não declarar desempenho de falha real; manter a lacuna e rever T13/T14 |
| Só uma fonte contribui com exemplos | Registrar resultado de fonte única; objetivo multibase continua pendente |
| Características não disponíveis na aplicação | Rever contrato nas etapas públicas ou registrar incompatibilidade; não preencher produção por suposição |
| Critérios públicos não cumpridos | Não abrir o teste externo para escolher ajustes |
| Condição real externa desconhecida | Registrar indeterminado e limitar as métricas |
| Teste externo reprovado | Preservar resultado, reabrir causas e reservar nova campanha após revisão |

## 11. Definição de conclusão do objetivo completo

O desenvolvimento estará concluído quando houver evidência de todas as condições aplicáveis abaixo:

- [x] A integração foi investigada antes do treinamento final e sua composição multibase está demonstrada.
- [x] O dataset final é rastreável, reprodutível, elegível e separado integralmente dos dados do protótipo.
- [x] A Random Forest foi treinada e avaliada em fontes públicas conforme o protocolo.
- [ ] Uma versão foi congelada e aplicada aos casos externos compatíveis com referência real independente.
- [ ] O resultado externo atende aos critérios prévios e suas limitações estão documentadas.
- [x] O software e a documentação correspondem ao comportamento entregue.
- [x] Dados preparados e resultados auditáveis estão persistidos no banco local, as views de visualização estão verificadas e o dump estrutural é restaurável.

Se a investigação ou o teste concluir inviabilidade, isso é um resultado de pesquisa que deve ser entregue com clareza. Não equivale a declarar atingido o objetivo de obter um classificador multibase validado no compressor local.

## 12. Infraestrutura acrescentada — banco local e disponibilização de dados

Essas tarefas foram acrescentadas após a autorização inicial de execução. A ordem efetiva inicial é T25, T27, T28, T01, T26 e depois T02. Nenhum requisito de pesquisa é dispensado pela criação do banco.


### T25 — Modelar e provisionar o MariaDB local do projeto

Estado: CONCLUIDA
Dependências: nenhuma
Requisitos: RF-30, RF-33, RF-34, RF-38

Critérios de aceite:

- [x] Serviço e versão locais são identificados; a escolha do SGBD é registrada.
- [x] Um banco novo `compressor_ml_dev` é criado sem alterar bancos/contas existentes ou o servidor hospedado.
- [x] A estrutura de `readings`, entidades legadas e entidades de pesquisa possuem PKs, FKs, CHECKs e índices pertinentes.
- [x] Conta local da aplicação possui permissões limitadas, com `readings` somente de leitura; credenciais geradas ficam em arquivo ignorado pelo Git.
- [x] Inicialização normal da aplicação não executa DDL; repetir provisionamento sobre banco ou arquivo existente é recusado.

Evidência: scripts SQL, configuração sem segredos no relatório e testes de provisionamento/contratos. Verificação: inspeção do servidor local e testes em base temporária dedicada.

Execução 01/11/2026, tentativa 1: MariaDB 10.4.24, banco novo com 23 tabelas; testes reais e permissões verificados. Código de trabalho e configuração estão identificados em [docs/local-database-audit.md](../../docs/local-database-audit.md); comandos e hashes permitem reprodução. Critérios acima atendidos sem importar dados do protótipo.

### T26 — Integrar persistência auditável ao pipeline público e externo

Estado: CONCLUIDA
Dependências: T01, T25
Requisitos: RF-02, RF-29, RF-30, RF-35, RF-38

Critérios de aceite:

- [x] Há operações transacionais para fontes, arquivos/hashes, execuções, observações, valores e rótulos, com origem e versão explícitas.
- [x] Snapshots de dataset, partições, estatísticas, grupos, modelos e avaliações possuem destino relacional definido e escritores reutilizáveis.
- [x] O contrato de uso dos escritores e testes de roundtrip está documentado para os chamadores subsequentes; a integração efetiva de cada chamador é critério transversal de sua própria tarefa.
- [x] Origem externa e suas derivações são recusadas no caminho de consolidação/treino público.
- [x] Testes demonstram integridade, repetição sem duplicidade, recusa de mudança incompatível e rollback de gravação incompleta.
- [x] Arquivos grandes/binaries permanecem rastreáveis por hash, tamanho e caminho; nenhuma credencial é persistida como metadado de pesquisa.

Evidência: repositório de pesquisa, testes e contrato de uso dos escritores. Verificação: roundtrip no MariaDB local/isolado e consulta dos registros vinculados. Os escritores básicos verificados concluem T26 e liberam T02; a integração de cada chamador permanece critério obrigatório da respectiva tarefa.

Execução 01/11/2026: cinco testes reais em bancos temporários passaram, cobrindo roundtrip, idempotência, conflito de versão, rollback e isolamento público/externo. A primeira execução revelou erro na fixture ao obter o banco selecionado; foi corrigida com `SELECT DATABASE()` e repetida com sucesso. Registro em [docs/development-execution.md](../../docs/development-execution.md).

### T27 — Disponibilizar estrutura de consulta e documentação para os demais integrantes

Estado: CONCLUIDA
Dependências: T25
Requisitos: RF-22, RF-27, RF-36, RF-38

Critérios de aceite:

- [x] Views expõem inventário, valores/qualidade, rótulos, estatísticas, grupos, composição de dataset, modelos e avaliação externa por versão.
- [x] Colunas numéricas e temporais podem ser consultadas diretamente, sem depender de interpretar arrays JSON de características.
- [x] Revisões de rótulos e referências não multiplicam indevidamente observações avaliadas; campanha/modelo/versão são filtros explícitos.
- [x] Métricas não estimáveis permanecem NULL; recusas e condições indeterminadas não são contadas como normalidade/acerto.
- [x] A conta local de consumo consulta as views e tem escrita/DDL recusados.
- [x] Há documentação das entidades, views, campos de conexão e regras de contagem para os demais integrantes consumirem os dados; configurar ferramentas de visualização é responsabilidade deles.

Evidência: SQL das views, consultas verificadas com fixtures e documentação de consumo dos dados. Verificação: SELECTs reais e testes de permissão com o usuário leitor; não exige acesso à interface do Metabase.

Execução 01/11/2026, tentativa 1: nove views consultadas, fixture com seis casos externos e revisão de referência sem duplicação; NULLs e recusas conferidos. Contas locais tiveram SELECT permitido e escrita/DDL temporário recusados. Documentação de consumo em [database/local/README.md](../../database/local/README.md). Na revisão 1.2.0, o critério foi delimitado à entrega dos dados: conexão, configuração e painéis do Metabase ficam integralmente com os demais integrantes. Estrutura, permissões e evidências SQL permanecem válidas.

### T28 — Exportar a estrutura e verificar recriação independente

Estado: CONCLUIDA
Dependências: T25, T27
Requisitos: RF-29, RF-30, RF-37, RF-38

Critérios de aceite:

- [x] `database/local/schema.sql` contém estrutura e views, sem INSERTs, contas, senhas ou seleção do banco original.
- [x] Definers e qualificações específicas do banco de origem não impedem recriação em um banco novo vazio.
- [x] Restauração foi executada em banco temporário próprio e tabelas, colunas, índices, FKs, CHECKs e views foram comparados.
- [x] Tabelas restauradas estão vazias e todas as views executam no banco restaurado.
- [x] Apenas o banco temporário criado pela própria verificação foi removido; o banco de desenvolvimento permanece preservado.
- [x] Há documentação de provisionamento, exportação e restauração; dump de dados fica explicitamente para depois.

Evidência: dump estrutural, teste/relatório de restauração e instruções locais. Verificação: recriação real, não apenas inspeção textual do SQL.

Execução 01/11/2026, tentativa 1: dump de 48.696 bytes, SHA-256 `43ba08e0d7c360b605639311a7a009c99fe9edbca039d250999504cbe5f3d7b1`; restauração independente das 23 tabelas e 9 views conferida. [Relatório e comandos](../../docs/local-database-audit.md).

## 13. Aprofundamento da integração — revisão 1.3.0

### T29 — Registrar hipóteses, critérios e reservas da nova rodada

Estado: CONCLUIDA
Dependências: T01, T02, T26
Requisitos: RF-01, RF-02, RF-19, RF-22, RF-31, RF-39, RF-44, RF-45, RF-46

Usar os resultados históricos como ponto de partida e registrar o protocolo
antes de executar os novos ajustes. Não depende da conclusão revisada de T14.

Critérios de aceite:

- [x] Matriz prioriza perguntas de ligação, representações, fontes/modalidades, evidência necessária e decisões para cada hipótese.
- [x] SMART é a âncora rotulada; refrigeração continua o foco; KAIST e detector de normalidade têm papel auxiliar explícito.
- [x] O protocolo identifica validação anterior como conhecida e preserva os 293 ciclos SMART reservados, sem novo split para melhorar o resultado.
- [x] Partições/grupos para ajuste, alinhamento, geração de derivados, calibração e avaliação independente estão definidos e verificáveis.
- [x] Métricas, mínimos de suporte e decisões de sucesso/reprovação/inconclusão são registrados antes dos novos resultados, sem exigir 100% de acerto.
- [x] Cada hipótese reprovada aponta uma próxima tentativa/busca; critérios de conclusão pública e liberação externa são separados.
- [x] Protocolo, versão, hashes e execução existem em arquivos e nos destinos relacionais de pesquisa, sem leitura de medições externas.

Evidência: `transfer-protocol.json`, matriz de hipóteses e manifesto de reservas.
Verificação: revisão de cobertura, anterioridade do protocolo e testes de
separação por grupo/origem.

Execução: protocolo registrado como `transfer-protocol-2b941b65972c76bd9371`, SHA-256 `2b941b65972c76bd9371310931b8be3435cfbb4ce469e94498672658fed675aa`. Reexecução idempotente confirmou reservas intactas e ausência de dados externos. Seis testes do contrato passaram. Grupos concretos de novas fontes serão congelados em T09 antes dos ajustes.

### T30 — Completar insumos e buscar fontes dirigidas às lacunas

Estado: CONCLUIDA
Dependências: T29, T03, T04, T05, T06
Requisitos: RF-03, RF-04, RF-05, RF-06, RF-08, RF-32, RF-35, RF-39, RF-40, RF-41

Complementar as primeiras amostras para responder às hipóteses, sem usar uma
busca genérica indefinida como substituto de experimentos.

Critérios de aceite:

- [x] Inventário cobre famílias SMART, sinais térmicos/elétricos/RMS/PSD RWTH, eventos/canais ULT e controles KAIST disponíveis, com semântica e lacunas.
- [x] Dados adicionais são ligados a uma hipótese e têm licença, limites de aquisição, versão, integridade e atribuição antes da incorporação.
- [x] Brutos ou arquivos processados adicionais são obtidos quando necessários à representação, sem presumir que só as tabelas iniciais bastam.
- [x] Lacunas não cobertas motivam busca de bases públicas de refrigeração/compressores; consultas, candidatos, acesso e decisões ficam registrados.
- [x] Conjunto e referências finais não são escolhidos apenas porque uma fonte obteve melhor pontuação no piloto; domínio e alvo são considerados.
- [x] Novos dados, hashes, metadados e ausências são persistidos; alterações de contrato/importação têm verificações de associação e qualidade pertinentes.
- [x] Nenhum anexo privado, leitura local ou dado sintético é apresentado como nova referência pública medida.

Evidência: registro ampliado de fontes, relatório de busca orientada por lacuna,
artefatos adquiridos e insumos para T07. Verificação: rastrear cada obtenção a
uma hipótese de T29 e a uma fonte primária acessível.


Evidência atual — revisão 1.4.0, 01/11/2026: Insumos concluídos para esta decisão: SMART bruto e famílias publicadas, RWTH térmico/PSD triaxial, controles KAIST, eventos/canais ULT, TRI e NIST auditados. Busca dirigida também avaliou ORNL, bancada intersensorial, OF550 e estudos herméticos. ORNL ficou só em metadados/preview; bancada sem mapeamento binário comprovado; OF550 sem licença confirmada. Essas limitações não foram preenchidas com rótulos fictícios. Novas auditorias/arquivos estão em research-handoff-de6dbc24bcab646d1e02.

### T31 — Construir e validar pontes entre modalidades e fontes

Estado: CONCLUIDA
Dependências: T10, T11, T12
Requisitos: RF-10, RF-12, RF-14, RF-15, RF-16, RF-19, RF-29, RF-35, RF-41, RF-42, RF-43

Investigar dados públicos de ligação para chegar à transferência de T13 com
evidência além de proximidade de histogramas ou três momentos compartilhados.

Critérios de aceite:

- [x] Grafo/tabulação identifica nós, arestas e caminhos, incluindo ligações medidas, estimadas e hipotéticas; nenhuma associação é aceita apenas pelo desenho.
- [x] Caminhos prioritários envolvendo SMART e fontes de refrigeração são testados ou têm impedimento específico documentado; bancada permanece apoio.
- [x] Cada ponte tem variáveis compartilhadas, contexto/regime, unidades, suporte e dados de ajuste/avaliação definidos.
- [x] Quando existem modalidades pareadas, mapeamentos são avaliados fora do grupo de ajuste e comparados a baselines, com erro, incerteza e sensibilidade.
- [x] Relações condicionais ou não identificáveis declaram hipóteses e não produzem coeficiente empírico fictício nem linhas conjuntas falsas.
- [x] Efeito de domínio e exclusão de variáveis/fontes é investigado; ajuste de ponte bom isoladamente não equivale a validade do rótulo.
- [x] Resultados de cada aresta/caminho e a incerteza propagada são persistidos e entregues a T13 para avaliar associação/transferência de referências.

Evidência: `source-relations.json`, `bridge-validation.json`, métricas e manifestos
das pontes. Verificação: reconstruir um caminho até observações públicas e sua
avaliação independente, incluindo a regra para insuficiência de suporte.

Evidência atual — revisão 1.4.0, 01/11/2026: Pontes medidas RWTH foram comparadas fora de sessão com controles de regime/constante; algumas eram previsíveis mas não transferiram a falha SMART. A associação final por normalidade tem encoders por fonte, quatro entradas e referências originais, sem pareamento físico artificial. A contribuição auxiliar foi comparada com exclusão de fontes e permutações. Resultados das arestas e casos estão em research-cycle-2.md e cycle-candidate-report.md.
