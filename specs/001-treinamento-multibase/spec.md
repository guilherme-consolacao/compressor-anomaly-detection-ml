# Especificação — treinamento multibase e validação externa

Versão: 1.4.0
Data de consolidação: 01/11/2026
Estado: candidata pública por ciclos treinada e avaliada; portabilidade e teste externo pendentes
Método: Spec-Driven Development (SDD)
Plano derivado: [plan.md](plan.md)
Tarefas executáveis: [tasks.md](tasks.md)

Resultado da execução em 01/11/2026: [relatório de viabilidade](../../docs/public-feasibility-report.md).
Aquela execução e seus artefatos permanecem como evidência histórica da versão
1.2.0. A revisão 1.3.0 reabre a pesquisa pública; a falha da representação com
três estatísticas de vibração não encerra a hipótese de integração entre fontes.
Naquele ensaio, T15–T23 não foram liberadas. A decisão atual por ciclos está em 9.1; não há declaração de sucesso local.

## 1. Finalidade e autoridade deste documento

Esta especificação registra as decisões da conversa para orientar a próxima evolução do projeto Compressor Anomaly Detection ML. Define o comportamento esperado, as restrições metodológicas, os contratos dos dados e as condições necessárias para considerar cada entrega concluída.

`spec.md` define **o que deve funcionar e por quê**. `plan.md` define **como desenvolver e verificar esse funcionamento**. `tasks.md` divide o plano em unidades executáveis, com dependências, evidências e critérios de aceite. Código, experimentos e documentação de resultados devem permanecer rastreáveis a estes três arquivos.

O contrato SDD foi criado na versão 1.0.0. A versão 1.1.0 acrescentou persistência relacional e suporte de dados para visualização. A versão 1.2.0 explicita a divisão de responsabilidades solicitada: nossa entrega é persistir e documentar os dados no banco; os demais integrantes usam esses dados no Metabase. Instalação, configuração, conexão e criação de perguntas, gráficos ou dashboards no Metabase estão fora do nosso escopo. Naquela etapa, a infraestrutura local foi preparada sem treinamento multibase ou validação de campo. A candidata pública posterior está descrita em 9.1.

A versão 1.3.0 retoma o objetivo reafirmado pelo usuário: aprofundar a descrição
e as relações entre fontes, procurar características e mecanismos comuns e usar
a referência rotulada SMART-PDM para investigar a incorporação de exemplos de
outras bases ao treinamento da Random Forest. Um detector treinado apenas em
normais pode ser ferramenta comparativa, mas não substitui esse objetivo.
Esta revisão muda o trabalho científico pendente, sem alterar retroativamente
as métricas, os limiares ou os protocolos já executados.

### 1.1. Decisão central

O projeto deve explorar **todas as fontes públicas candidatas antes de definir a base final e treinar o classificador final**. A SMART-PDM fornece dados rotulados e uma referência para investigar correspondências com outras bases. As outras fontes são candidatas a fornecer exemplos ao conjunto final de treinamento, além de informação para a análise.

A investigação deve verificar se características, condições e rótulos de fontes diferentes podem ser relacionados de forma defensável. Essa relação pode exigir análise estatística, representação comum dos sinais, agrupamento, transferência de rótulos ou fusão de dados. Sua viabilidade é uma conclusão a demonstrar, não uma equivalência presumida entre equipamentos.

**Os dados medidos pelo Ulisses ficam exclusivamente para o teste externo do modelo pronto.** Eles não participam da exploração que constrói o modelo, da consolidação de treinamento, do agrupamento de desenvolvimento, da transferência de rótulos, da seleção de características, da normalização aprendida, da escolha de hiperparâmetros ou do ajuste do limiar de decisão.

O foco de aplicação continua sendo refrigeração, especialmente compressor de
geladeira. Independência em relação ao equipamento é uma hipótese de
generalização a testar, não uma promessa universal. Características comuns não
exigem sensores idênticos nem correlação entre todas as variáveis; exigem uma
relação de significado e uma transformação cuja utilidade possa ser avaliada.

### 1.2. Precedência e mudança em relação ao projeto existente

As decisões explícitas mais recentes do usuário prevalecem sobre propostas anteriores. Este contrato substitui, para esta evolução, a proposta de usar as medições do protótipo como base de treinamento.

O relatório parcial do PI4 é contexto do projeto e não uma imposição metodológica. Random Forest é o classificador principal pretendido; as 20 características anteriores, a janela de 15 segundos e um contrato de medição finalizada no banco não são obrigações científicas desta evolução. O PDF de outro projeto foi desconsiderado.

O código atual continua implementando o fluxo anterior. Sua documentação descreve esse estado, inclusive as limitações de integração. A existência de funções e testes não comprova que o novo fluxo multibase esteja pronto. Mudanças em código serão realizadas pelas tarefas deste SDD; não se devem alterar contratos antigos silenciosamente.

## 2. Problema, objetivo e fronteiras

O histórico local possui poucas informações sobre diversidade de equipamentos e condições reais de defeito. Esperar por uma nova campanha ampla de coleta e por alterações na aquisição comprometeria o prazo disponível. A estratégia escolhida é investigar dados públicos para desenvolver um modelo e reservar o compressor local para uma avaliação externa posterior.

O objetivo funcional é estimar o **risco da condição anômala de uma unidade de
análise**, mantendo o alvo normal (`0`)/anômalo (`1`) e seu significado explícitos.
A saída deve distinguir escore de classe, probabilidade calibrada quando
sustentada, alerta por limiar e estado de incompatibilidade/dado inválido.
Não se exige 100% de acerto. Escrever uma saída entre zero e um não comprova
calibração nem a converte automaticamente em probabilidade de defeito físico.
Quando o suporte só permitir estimar a referência de manutenção do
eletrodoméstico, esse é o escopo declarado; não afirmar diagnóstico do compressor.

“Prever anomalias”, neste escopo, significa estimar a classe a partir dos sinais de entrada disponíveis. Previsão de falha futura, tempo restante de vida, identificação de peça defeituosa e diagnóstico causal não são resultados prometidos por esse classificador.

### 2.1. Incluído

1. Inventário e obtenção reprodutível das fontes públicas candidatas.
2. Auditoria, preparação e análise descritiva e exploratória dessas fontes.
3. Investigação de relações entre fontes e de rótulos derivados com evidência.
4. Definição de uma representação comum compatível com a aplicação pretendida.
5. Construção versionada de um conjunto final de treinamento, se sustentado pela pesquisa.
6. Treinamento, avaliação interna pública e congelamento da Random Forest.
7. Adaptação da inferência à aquisição existente, dentro da compatibilidade demonstrada.
8. Teste externo com medições do protótipo e referência real observada independentemente.
9. Registro de resultados, limitações, proveniência e decisões negativas.

### 2.2. Fora desta entrega de documentação

O plano agora inclui implementação e um banco local novo. O preparo da infraestrutura autoriza DDL e contas restritas exclusivamente nesse ambiente local. Não autoriza modificar o firmware, a API ou o banco hospedado do protótipo, nem importar seu histórico para o treinamento. Dados de pesquisa e teste serão carregados nas respectivas tarefas; o dump inicial é somente da estrutura.

Também ficam fora do objetivo obrigatório: redes neurais, dois modelos finais separados por sinal como solução previamente escolhida, busca irrestrita de hiperparâmetros, interface própria de gráficos, serviço HTTP novo e suporte universal a qualquer compressor. O Metabase, incluindo instalação, configuração, conexão, perguntas, gráficos, dashboards e sua operação, é responsabilidade dos demais integrantes. Nossa entrega se encerra na persistência, estrutura SQL, documentação dos dados e acesso de leitura. Views já criadas permanecem como apoio à consulta; sua existência não cria uma obrigação de integração com o Metabase. Gráficos exploratórios internos da pesquisa de ML podem ser produzidos para análise e não constituem uma entrega de painel.

## 3. Contexto e evidências disponíveis

### 3.1. Aquisição existente

A versão auditada da API recebe uma leitura por `POST /api/compressor`, com `temperature` e `vibration.x/y/z`. Cada chamada aceita gera uma linha em `readings`. A API aplica offsets e supressão de valores pequenos nos eixos e grava `temperature`, `accel_x`, `accel_y`, `accel_z`, `rms` e `timestamp`.

O valor chamado `rms` na aquisição é:

```text
rms_espacial = sqrt((accel_x² + accel_y² + accel_z²) / 3)
```

É uma combinação espacial instantânea. RMS temporal é outra grandeza, calculada sobre amostras no tempo, com definição do sinal, remoção ou manutenção de componente DC, banda e intervalo. Ambos não podem ocupar uma mesma característica apenas porque usam a sigla RMS.

O esquema auditado não identifica medição, ciclo, equipamento, rótulo ou fim de coleta. O horário é de inserção e não comprova o instante de captura no sensor. A unidade física dos eixos não foi confirmada pelo firmware. O modelo exato do compressor e a montagem física dos sensores permanecem não confirmados.

Conhecer os campos e o processamento dessa interface é permitido para definir o **contrato de aplicação**. Isso não autoriza usar os valores das medições locais para desenvolver o modelo.

### 3.2. Histórico do protótipo já examinado antes desta decisão

Um backup local contém 3.701 leituras, sem rótulos de normal/anômalo ou limites de medição. O intervalo mediano entre registros é aproximadamente 13 segundos; isso descreve persistência e não a taxa interna do acelerômetro. O arquivo não demonstra envio HTTP em lote.

Houve uma exploração histórica com DBSCAN e Isolation Forest. As contagens de pontos fora dos grupos variaram com os parâmetros. Esses resultados não identificaram defeitos e não são insumos para o desenvolvimento multibase agora especificado. Essa exposição prévia deve constar como limitação de qualquer avaliação que reutilize o backup. Para um teste externo prospectivo, novas medições reservadas são preferíveis.

O acesso online anterior ao MariaDB foi recusado por conta bloqueada. O backup é um snapshot e não uma inspeção do servidor atual. Não há autorização implícita neste SDD para alterar a aquisição ou o banco.

### 3.3. Registro inicial de fontes públicas

Os fatos abaixo resultam da pesquisa e das inspeções realizadas na sessão. Cada importação futura deve confirmar a versão e a integridade dos arquivos utilizados. “Candidata” não significa aceita no treinamento.

| Fonte | Evidência conhecida | Limites e situação inicial |
| --- | --- | --- |
| SMART-PDM, subconjunto de geladeiras | 1.111 ciclos; 1.087 `Normal` e 24 `Malfunction`; metadados e características tabulares inspecionados; CC BY 4.0 | Um modelo de geladeira identificado nos metadados: SMEG FAB5ULRD3. Não há identificação confirmada do modelo do compressor nem ID de cada unidade física. Um canal de vibração e sinais elétricos; sem temperatura ou XYZ equivalentes aos locais. Rótulo de mau funcionamento do eletrodoméstico não comprova defeito específico do compressor. |
| KAIST, máquinas rotativas, Mendeley v6 | Descrição de vibração, temperatura, corrente e acústica sob cargas e condições de falha de laboratório; CC BY 4.0 segundo o registro | Equipamento de laboratório, não compressor doméstico. Há eixos em posições de mancais; não presumir equivalência a XYZ na carcaça. Arquivos de amostras ainda não auditados localmente. |
| RWTH Aachen, bomba de calor R290, Zenodo 22097811 | Arquivos processados térmicos e RMS inspecionados; 9 sessões; 195 condições térmicas e 200 condições de RMS XYZ do compressor, com 195 correspondências exatas por sessão/carga; CC BY 4.0 | Temperaturas de entrada/saída, não temperatura da carcaça. Estados de carga de refrigerante, sem flag binária pronta de defeito. RMS temporal em banda 10–1.000 Hz; não equivalente ao RMS espacial da API. Os 50/90 Hz descrevem frequência de operação do compressor, não taxa de amostragem do acelerômetro. |
| Freezers de ultrabaixa temperatura, coleção Figshare 6805332 | Publicação descreve temperaturas e eventos de manutenção/falha em 53 freezers | Sistema de refrigeração distinto, sem vibração confirmada. Dados, licença específica e alinhamento dos eventos ainda precisam de auditoria. Candidata térmica adicional. |
| Estudos de compressores herméticos e NIST | Há publicações específicas com vibração e condições de operação ou defeitos | Arquivos brutos públicos reutilizáveis não confirmados. Artigo disponível não equivale a dataset disponível. |
| Catálogos Secop e outros fabricantes | Especificações, famílias, refrigerantes, capacidade e tipos de acionamento | Referência física e de contexto; não constituem exemplos rotulados de sensores. Não permitem identificar com segurança o compressor local somente pelos valores observados. |

Na SMART-PDM, `F_ExtractedFeatures.csv.Id` deve ser ligado a `fridge_metadata.csv.begin_end`. A correspondência foi verificada como um-para-um nos 1.111 ciclos. **A ordem das linhas dos arquivos é diferente**; juntar por posição atribuiria rótulos incorretos. Existem 100 características numéricas publicadas, não 100 sinais distintos. As taxas informadas são 1 Hz para sinais lentos e 2.048 Hz para sinais rápidos; a documentação de cada canal e sua escala deve ser preservada.

Na RWTH, cinco condições de RMS não possuem linha térmica correspondente: M05/2.350 g; M06/650 g, 750 g e 2.250 g; M07/2.350 g. Não preencher essas temperaturas por associação posicional. Os arquivos brutos somam cerca de 32 GB; os arquivos processados pequenos permitem uma primeira análise sem esse download integral.

Dados sintéticos eventualmente encontrados devem permanecer identificados. Seus resultados não demonstram generalização para defeitos reais.

### 3.4. Limite do primeiro ensaio e motivo da revisão

A rodada 1.2.0 preparou 3.125 observações públicas e uma EDA por fonte. Seu
experimento de transferência usou somente skewness, curtose e amplitude/desvio
padrão da vibração SMART/KAIST. O combinado detectou 45/48 janelas anômalas KAIST
e perdeu o único ciclo anômalo SMART na validação. Isso reprovou aquela
configuração, com suporte pequeno; não avaliou todas as representações possíveis.

A RWTH contém modalidades realmente associadas por condição e pode fornecer
pontes entre vibração, grandezas elétricas/termodinâmicas e temperatura, quando
as definições forem confirmadas. A ULT acrescenta dados térmicos e eventos de
serviço, com incerteza temporal. Essas possibilidades ainda precisam de
experimentos de ligação e validação de transferência. A demonstração de que
marginais isoladas admitem vários acoplamentos não substitui essa investigação.

O resultado anterior não autoriza baixar um limiar até acertar aquele ciclo.
Também não torna um erro isolado prova de inviabilidade geral. A nova rodada
deve investigar sinais, representações, regimes e hipóteses adicionais sem usar
as medições do protótipo. A validação pública já consultada passa a ser conhecida;
os 293 ciclos SMART reservados continuam selados para a avaliação apropriada.

## 4. Fluxo de trabalho obrigatório

**Pré-requisito de infraestrutura:** provisionar o banco local, suas tabelas, views de leitura e exportação de estrutura reproduzível. As etapas abaixo devem persistir seus resultados auditáveis no banco, além dos arquivos e relatórios de apoio.

1. **Inventariar as bases e o contrato de aplicação:** fontes, versões, licença, sensores, sinais, rótulos, unidades e disponibilidade dos campos na aquisição.
2. **Preparar e explorar as fontes públicas:** qualidade, ciclos, distribuições, relações internas, grupos e condições de operação.
3. **Investigar relações entre fontes:** características comuns, equivalência física, diferenças de domínio, correspondência de grupos e validade de eventual transferência de rótulos ou fusão.
4. **Consolidar e congelar a base de desenvolvimento:** escolher a representação, justificar cada inclusão/exclusão e reservar avaliação pública sem vazamento.
5. **Treinar e avaliar a Random Forest:** desenvolver somente com fontes públicas, medir desempenho por origem e congelar uma versão candidata ao teste externo.
6. **Executar o teste externo do protótipo:** importar medições reservadas, aplicar o modelo congelado e comparar com a condição real registrada independentemente.
7. **Concluir e documentar:** métricas, evidências, limitações e decisão de aplicação. Resultado negativo ou inconclusivo deve permanecer explícito.

“Treinar de uma vez” significa chegar ao treinamento final após a investigação e a consolidação. Não proíbe ajustes ou comparações internos necessários ao desenvolvimento, desde que usem somente dados públicos e respeitem as reservas de avaliação. Não haverá treinamento final prematuro somente na SMART-PDM seguido de tentativa de justificar as demais fontes depois.

## 5. Requisitos funcionais e metodológicos

Cada identificador abaixo é estável para rastreabilidade. Os detalhes das seções posteriores fazem parte do respectivo requisito.

### 5.1. Governança e aquisição de dados

- **RF-01 — Fluxo multibase:** analisar as fontes candidatas e concluir a investigação de integração antes de liberar o treinamento final. Outras bases devem ser avaliadas como fornecedoras de exemplos, não limitadas previamente ao papel de bibliografia.
- **RF-02 — Separação externa:** impedir qualquer uso das leituras, distribuições e rótulos do protótipo em etapas que aprendam ou selecionem o modelo. A separação deve ser verificável por proveniência e por validação automática das entradas.
- **RF-03 — Registro de fontes:** registrar versão, URL/DOI, licença, autores, arquivos, hashes, domínio, sensores, unidades, posições, taxas, alvo, limites de acesso e estado da inspeção. Campos desconhecidos devem ser explícitos.
- **RF-04 — Ingestão reprodutível:** obter apenas arquivos necessários, preservar originais, conferir integridade, impedir extração insegura e retomar importações sem sobrescrever versões. Código de terceiros baixado não deve ser executado automaticamente.
- **RF-05 — Identidade e associação:** manter IDs de origem, associação entre amostra/ciclo/condição e rótulo, cardinalidade esperada e relatório de registros sem correspondência. Proibir junção por ordem de linhas.
- **RF-06 — Qualidade:** distinguir erro estrutural, valor ausente, leitura extrema e condição anômala física. Tratamentos devem produzir contagens antes/depois e motivos por registro. Um extremo não deve ser eliminado automaticamente por ser raro.

### 5.2. Representação e exploração

- **RF-07 — Unidade de análise:** definir explicitamente o que representa uma linha do modelo: leitura individual, ciclo ou segmento com duração e condições conhecidas. Evitar converter ciclos inteiros em leituras equivalentes sem evidência. Unidades relacionadas devem compartilhar grupo de dependência.
- **RF-08 — Semântica física:** cada característica deve definir grandeza, unidade, ponto de medição, eixo/orientação quando aplicável, banda, taxa necessária, fórmula e calibração. Preservar a distinção entre RMS espacial, RMS temporal e estatísticas de ciclos.
- **RF-09 — Exploração pública:** produzir descrições por fonte, classe, equipamento identificado, regime e período: contagens, ausências, quantis, variabilidade, evolução temporal, distribuições e relações observadas. Não ajustar decisões exploratórias ao teste externo.
- **RF-10 — Relações estatísticas:** calcular correlações observáveis dentro de registros efetivamente associados e investigar associações entre fontes com métodos explicitados. Distinguir correlação medida, transferência estimada e hipótese física. Correlação não deve ser apresentada como prova de causalidade.
- **RF-11 — Métodos não supervisionados:** permitir agrupamentos e escores de atipicidade para investigar estrutura e candidatos a revisão, com escala, parâmetros, estabilidade e sensibilidade registrados. `cluster_id` e escore de exceção não equivalem a `target_label`.
- **RF-12 — Compatibilidade entre fontes:** construir matriz que explique quais características e condições podem ser relacionadas, quais exigem transformação e quais não são comparáveis. Avaliar efeitos de equipamento, montagem, sensor, faixa, frequência, carga e alvo.

### 5.3. Rótulos e consolidação

- **RF-13 — Alvo e rótulos de referência:** definir o alvo binário e preservar o rótulo original. Rótulos existentes não serão substituídos somente por discordarem de um agrupamento. Falha de mancal de bancada, mau funcionamento de geladeira e subcarga de refrigerante precisam de mapeamento explícito; não são automaticamente o mesmo diagnóstico.
- **RF-14 — Rótulos derivados:** permitir rótulos provisórios ou transferidos somente com método, evidência, confiança, versão e decisão de revisão. Manter `indeterminado` quando a evidência não sustentar `0` ou `1`. Um classificador treinado para reproduzir pseudorrótulos não deve ser declarado detector validado de falhas reais por esse fato.
- **RF-15 — Fusão e transferência:** investigar representação comum, associação por variáveis compartilhadas, dados públicos de ligação e métodos de integração sob hipóteses verificáveis ou explicitadas. Não exigir que todas as variáveis sejam correlacionadas para haver informação diagnóstica. Não criar pares fictícios como se temperatura de uma fonte e vibração de outra fossem uma medição real conjunta.
- **RF-16 — Evidência de integração:** comparar alternativas com e sem transferência, apenas rótulos de referência versus acréscimo de rótulos derivados, sensibilidade às hipóteses e desempenho em exemplos públicos de referência que ficaram fora da geração desses rótulos. A ausência de identificação estatística deve gerar incerteza, não um fator de correlação inventado.
- **RF-17 — Dataset consolidado:** produzir uma versão imutável, com exemplos aceitos, registro dos excluídos, contrato das características, proveniência, rótulos, grupos, partições e hashes. A composição multibase precisa estar demonstrada em contagens; resultado com uma única fonte não pode ser chamado de treinamento multibase.
- **RF-18 — Portabilidade das entradas:** selecionar entradas calculáveis na aplicação local mediante transformações justificadas. Sinais elétricos ou espectrais úteis à exploração podem servir de informação auxiliar, mas não se tornam entradas obrigatórias de produção quando a aquisição não os fornece. Variável ausente não deve virar zero silenciosamente.

### 5.4. Treinamento e avaliação pública

- **RF-19 — Ausência de vazamento:** reservar avaliação pública antes de usar rótulos ou valores desses exemplos em escolhas aprendidas. Separar por ciclo/sessão/equipamento/campanha conforme a dependência e aplicar qualquer ajuste de escala, imputação, seleção, alinhamento ou geração de pseudorrótulos apenas na partição de desenvolvimento apropriada.
- **RF-20 — Classificador final:** usar Random Forest como candidato principal sobre o dataset consolidado elegível. Versionar configurações e comparar ao menos com a classe majoritária. Não disparar novo treinamento a cada leitura recebida. Mudança do algoritmo principal exige atualização explícita dos documentos SDD.
- **RF-21 — Desbalanceamento e viés de origem:** relatar suporte de classes, equipamentos e grupos; examinar se fonte, arquivo, período, ausências ou pseudorrótulos explicam artificialmente a classificação. Reamostragem, se usada, deve ficar dentro do treino. IDs e origem são metadados de auditoria, não atalhos de classificação.
- **RF-22 — Avaliação pública:** registrar matriz de confusão, acurácia, precisão, recall, F1, taxa de falsos positivos, suporte e métricas por fonte/grupo viável. Avaliar discriminação por escores quando houver suporte. Métricas sobre pseudorrótulos e métricas sobre referências independentes devem ser separadas.
- **RF-23 — Congelamento:** antes do teste externo, congelar modelo, extrator, pré-processamento, características ordenadas, política de incompatibilidade, limiar, ambiente, datasets, partições e protocolo de avaliação. Registrar critérios quantitativos de sucesso antes de observar o resultado externo; não inventar uma meta de acurácia já alcançada.

### 5.5. Aplicação e validação externa

- **RF-24 — Integração mínima:** consumir o contrato existente da aquisição sem depender previamente de reescrever firmware ou API. Preferir exportação ou consulta de leitura e processamento no backend de ML. Mudança compartilhada só deve ser proposta quando uma necessidade demonstrada não puder ser atendida pelo adaptador.
- **RF-25 — Inferência consistente:** aplicar as mesmas características e transformações congeladas do treinamento. Validar esquema, unidade, finitude, suporte dos sinais e versão do artefato. Registrar classificação, escore e rastreabilidade ou motivo de recusa; dado inválido não significa normalidade.
- **RF-26 — Referência externa independente:** registrar a condição real de cada unidade avaliada, com evidência, observador, instante e confiança, sem defini-la pela resposta do modelo. Condições indeterminadas ficam registradas e fora das métricas binárias confirmadas.
- **RF-27 — Teste externo:** usar o equipamento do protótipo exclusivamente para a avaliação externa da versão congelada. Relacionar predição e referência por identidade estável e relatar métricas, cobertura, recusas e incerteza. Somente exemplos normais não demonstram capacidade de detectar falhas.
- **RF-28 — Reavaliação:** se o teste falhar, registrar o resultado e reabrir as tarefas pertinentes. Ajustes baseados no teste tornam aqueles exemplos conhecidos para a versão seguinte; uma nova alegação de teste externo independente requer nova reserva prospectiva. Manter predições e resultados anteriores.

### 5.6. Reprodutibilidade e operação

- **RF-29 — Artefatos:** persistir contrato, transformações aprendidas, estimador, versões, hashes, composição do treino, métricas e estado de liberação. Carregar somente artefatos confiáveis e compatíveis. Não confundir modelo sintético de demonstração com modelo validado em dados reais.
- **RF-30 — Preservação da aquisição:** não executar DDL, sobrescrever `readings`, recalibrar novamente eixos já corrigidos, publicar alterações ou gravar no banco compartilhado sem autorização correspondente. Segredos não entram em datasets, relatórios, exemplos ou logs.
- **RF-31 — SDD e evidências:** toda tarefa deve referenciar requisitos, ter critérios verificáveis e registrar evidência. Enquanto houver critério pendente, a tarefa continua aberta ou em correção. Revisão do contrato deve propagar para plano e tarefas.
- **RF-32 — Conclusões honestas:** documentar também incompatibilidade, resultado negativo e insuficiência de rótulos. Conhecer o modelo do compressor é útil, mas não bloqueia o início do inventário e da exploração pública. Não prometer aplicabilidade universal ou eficácia física ainda não demonstrada.

### 5.7. Persistência, auditoria e disponibilização dos dados

- **RF-33 — Banco local relacional:** usar um banco novo e exclusivo do projeto, preservando os demais bancos da máquina e o servidor hospedado. Preferir MySQL/MariaDB para manter compatibilidade com a aquisição e a stack existente. A inspeção encontrou MariaDB 10.4.24 e PostgreSQL 17 ativos; foi escolhido o MariaDB local em `127.0.0.1:3306`, banco `compressor_ml_dev`.
- **RF-34 — Estrutura estendida:** reproduzir localmente a estrutura de `readings` sem importar seus dados nesta preparação. Acrescentar entidades para fontes/versões, arquivos e hashes, execuções, observações, características, rótulos versionados, datasets/partições, estatísticas, agrupamentos e testes externos. Reusar as entidades de modelos e resultados já existentes quando compatíveis.
- **RF-35 — Persistência auditável:** resultados preparados usados em auditoria ou visualização devem existir em tabelas relacionais, com vínculos e versão de execução. CSV/JSON podem servir a intercâmbio e reprodução, mas não serão o único repositório desses resultados. Sinais brutos volumosos e modelos binários podem permanecer em arquivos com localização, tamanho, hash e origem registrados no banco. Identidade local versus pública deve continuar explícita em consultas e na construção de datasets.
- **RF-36 — Dados consultáveis pelos demais integrantes:** disponibilizar no banco dados preparados e resultados com colunas numéricas, datas e dimensões de origem/versão, acompanhados de dicionário e regras de contagem, para qualidade, distribuições, rótulos, correlações, grupos, composição dos datasets, métricas públicas e avaliação externa. Documentar acesso de leitura e estrutura SQL para os responsáveis pelo consumo. O uso desses dados no Metabase é dos demais integrantes; não é critério de aceite nosso instalar, conectar, configurar ou operar essa ferramenta, nem criar perguntas, gráficos ou dashboards nela.
- **RF-37 — Exportação de estrutura:** manter um dump SQL somente de estrutura, sem dados, senhas, usuários de servidor ou dependência do nome original do banco. Incluir tabelas, índices, chaves, verificações e views. Validar recriação em banco temporário novo e vazio e comparar o esquema; preservar os bancos existentes.
- **RF-38 — Operação e evidência do banco:** separar provisionamento administrativo do início normal da aplicação. Registrar versão do servidor/esquema, configuração de conexão sem segredos, testes de integridade, permissões e restauração. Conta da aplicação deve escrever somente nas entidades do projeto necessárias; `readings` permanece de leitura para o ML. Dump de dados fica para etapa posterior. Publicação de painéis é responsabilidade dos demais integrantes e está fora deste plano.

### 5.8. Organização da persistência

`readings` é a cópia estrutural da aquisição. As tabelas `ml_*` existentes continuam guardando o contrato legado, modelos, importâncias e resultados associados a medições finalizadas. As novas tabelas `study_*` não exigem criar medições fictícias para as fontes públicas.

Fontes e versões são identificadas em `study_sources`; arquivos em `study_artifacts`; configurações, entradas e estados em `study_runs`. Observações preparadas e valores são separados em `study_observations` e `study_feature_values`, permitindo gráficos por característica sem extrair arrays JSON manualmente.

`study_labels` mantém versões de rótulos. `study_datasets` e `study_dataset_members` fixam observações, rótulos e partições usados em cada dataset; a associação deve apontar ao rótulo da mesma observação. Estatísticas e agrupamentos ficam em `study_statistics` e `study_clusters`, sempre vinculados à execução.

Casos externos, vínculos às leituras, referência real versionada e predições ficam separados em `study_external_cases`, `study_external_case_readings`, `study_external_ground_truth` e `study_external_predictions`. A avaliação deve usar a versão explícita da referência do caso, evitando contar reclassificações como novas medições. A referência indeterminada ou uma entrada recusada não entra como acerto normal.

O banco não substitui as verificações de elegibilidade pública do pipeline: chaves e CHECKs protegem consistência local, enquanto a regra de proveniência e separação continua obrigatória na aplicação. Atualização e importação devem preservar versões e rastreabilidade. A tarefa T26 integra os escritores aos resultados produzidos nas tarefas subsequentes.

### 5.9. Aprofundamento multibase — requisitos da versão 1.3.0

- **RF-39 — Cobertura das hipóteses:** registrar uma matriz finita de hipóteses,
  representações, ligações e experimentos, com prioridade, dados necessários e
  decisão. A rodada não termina somente porque a configuração anterior falhou
  ou porque a interface local ainda tem lacunas. Cada caminho prioritário deve
  ter experimento executado ou impedimento específico demonstrado. Caminhos
  reprovados devem motivar nova hipótese, representação ou busca dirigida de
  fontes; a matriz é renovável por ciclo e não limita a pesquisa às quatro bases
  da primeira rodada. Não encerrar a execução apenas repetindo a decisão anterior.
- **RF-40 — Descrição orientada à ligação:** inventariar todas as famílias
  disponíveis e estudar relações por estado/regime, fonte e unidade física,
  incluindo efeitos temporais, dependências não lineares e variáveis de contexto
  quando houver suporte. Identificar separadamente sinais comuns, auxiliares,
  modalidades pareadas, dados ausentes e diferenças de processamento. Não
  limitar a comparação às três estatísticas previamente usadas.
- **RF-41 — Pontes públicas:** construir um grafo de relações entre fontes,
  modalidades, regimes e unidades de análise. Testar ligações diretas e caminhos
  intermediários, por exemplo usando uma fonte que contenha vibração e
  temperatura conjuntamente. Cada aresta deve distinguir associação medida,
  transformação estimada e hipótese física/estatística, com erro, limites e
  evidência. O nome da variável ou a proximidade de histogramas não basta.
- **RF-42 — Representação transferível:** investigar representações físicas ou
  estatísticas compartilhadas, condicionamento por operação e alinhamento de
  domínio quando justificáveis. Comparar a mesma regra entre fontes/equipamentos
  e grupos reservados. Distinguir avaliação indutiva de adaptação transdutiva;
  nenhuma transformação pode aprender com as medições reservadas do protótipo.
- **RF-43 — Referência e transferência de rótulos:** usar a SMART-PDM como âncora
  rotulada, sem apagar referências independentes das outras bases. Investigar
  a associação de perfis/grupos e a transferência por ligações validadas.
  Registrar a incerteza de cada etapa, o significado do alvo e conflitos entre
  manutenção do eletrodoméstico, mancal e compressor. Rótulos fracos/derivados
  exigem origem, regra de aceitação, ponderação/exclusão e avaliação separada.
- **RF-44 — Evidência entre domínios:** comparar SMART isolada, referências
  combinadas sem alinhamento e candidatos com pontes/alinhamento/derivados.
  Controlar tamanho, classes e grupos quando viável para medir a contribuição
  das fontes. Fazer ablação de ligações e avaliação fora da origem quando
  suportado. Identificar fonte com facilidade é um diagnóstico de diferença,
  não prova isolada de que a transferência falhou ou de que o alinhamento funcionou.
- **RF-45 — Risco e calibração:** manter separados atipicidade, confiança do
  rótulo, escore `predict_proba` e probabilidade calibrada da classe de referência.
  Avaliar discriminação, falsos alertas e qualidade probabilística, com suporte
  por classe/grupo. Calibração e limiar são ajustados somente em dados públicos
  permitidos. Suporte insuficiente gera estado explícito e limita a interpretação;
  não preencher uma probabilidade física nem exigir certeza de 100%.
- **RF-46 — Decisões separadas de continuidade:** concluir separadamente a
  viabilidade pública da integração e a prontidão para aplicação local. Uma
  candidata pública pode avançar em consolidação/treinamento de pesquisa sem
  afirmar compatibilidade externa. A liberação externa exige o contrato local
  atendido. O fechamento negativo da nova investigação exige cobertura da matriz
  de hipóteses, incerteza documentada e próximo passo, não apenas repetir o piloto.

- **RF-47 — Ciclo concluído como candidata explícita:** a representação
  `cycle-context-normality-v1` usa duração relativa à mediana dos até dez ciclos
  anteriores, mínimo de três, no mesmo equipamento/grupo. Rótulos, ciclo atual
  e futuros não definem a mediana. Sobreposição ou lacuna maior que 12 horas
  reinicia o histórico; ausência de suporte é recusa, não normalidade.
- **RF-48 — Integração estatística sem pareamento fictício:** cada fonte pode
  fornecer descritores de normalidade calculados em suas próprias grandezas.
  A candidata SMART/NIST/TRI preserva encoders específicos e referências
  originais. Essa representação não comprova correlação física entre fontes.
- **RF-49 — Saída da candidata de pesquisa:** manter separados classe por limiar
  bruto, escore de referência não calibrado, mapeamento probabilístico
  experimental, suporte limitado e validação local pendente. Não anunciar
  probabilidade universal de defeito do compressor.
- **RF-50 — Portabilidade por metadados confirmados:** pacotes instantâneos de
  temperatura/vibração não comprovam ciclos operacionais. O fluxo por ciclos
  exige limites reais e evidência. Anotação do operador é alternativa proposta
  sem mudança de firmware, ainda dependente de confirmação do procedimento.
  Não habilitar automaticamente o modelo sobre a aquisição existente.

## 6. Contratos lógicos de dados

Estes contratos descrevem informação obrigatória; não exigem criar uma tabela SQL para cada objeto. O plano escolhe formatos locais simples e versionados.

### 6.1. Fonte (`DatasetSource`)

Deve identificar `source_id`, `source_version`, URL/DOI, licença/atribuição, arquivos e hashes, tipo de equipamento, sensores, posições, unidades, taxas, origem dos rótulos, acesso aos brutos e resultado da auditoria. A ausência de informação deve usar estado explícito como `unknown`; não preencher identificação física por suposição.

Os estados são `candidate`, `inspected`, `eligible`, `ineligible` e `pending_evidence`, com motivo e evidência. Uma fonte pode ser elegível apenas para um subconjunto de características ou para a pesquisa, sem ser elegível para todos os exemplos do treinamento.

### 6.2. Observação normalizada (`CanonicalObservation`)

Deve preservar `observation_id` estável, `source_id/version`, IDs e arquivos de origem, `analysis_unit`, identidade do equipamento quando conhecida, `dependency_group_id`, condição operacional, início/fim quando aplicáveis, semântica do horário, sinais/características disponíveis e sua definição, indicadores de qualidade e proveniência de cada transformação.

Um identificador de observação não pode ser confundido com identidade de equipamento. Falta de ID da unidade física deve reduzir a força da alegação de generalização, não ser contornada criando um equipamento por linha.

### 6.3. Rótulo (`LabelRecord`)

Deve conter `observation_id`, `original_label`, `target_label` (`0`, `1` ou ausente), `label_status` (`reference`, `derived`, `indeterminate`), método, evidências, responsável ou processo, versão e confiança quando mensurável. `label_confidence` não é a probabilidade emitida pelo classificador final.

Registros de referência devem apontar ao metadado/evento/documento independente. Registros derivados devem apontar ao experimento que os gerou, suas entradas de desenvolvimento e restrições de aplicação. Mudança de rótulo deve preservar histórico e justificativa.

### 6.4. Contrato de características (`FeatureContract`)

Deve definir `feature_contract_version`, unidade de análise, nomes e ordem, tipos, fórmulas, unidades, significado físico, sinais necessários, pré-processamento, banda, exigência temporal, regras para ausências e incompatibilidades e disponibilidade esperada na inferência.

Uma mudança de significado exige versão nova mesmo que o nome da coluna permaneça igual. O uso das 20 características antigas depende dessa verificação. FFT, RMS temporal e atributos de alta frequência não podem ser reconstruídos a partir de leituras esparsas somente por renomear ou normalizar colunas.

### 6.5. Manifesto de desenvolvimento (`TrainingManifest`)

Deve apontar a versão e o hash do dataset consolidado, contrato das características, fontes, contagens por classe/origem/status de rótulo, observações e grupos por partição, semente, critérios de seleção, exclusões, evidência de ausência de dados locais, versão do código e ambiente. Dados estimados, imputados ou transferidos precisam ser identificáveis.

### 6.6. Predição e referência externa

`ExternalPrediction` deve conter `external_case_id`, IDs das leituras locais associadas, `model_version/hash`, contrato de entrada, instante, resultado, escore e estado `classified`, `invalid_input` ou `unsupported_signal`, com motivo quando não classificado.

O contrato revisado deve acrescentar, quando aplicável, `score_kind`,
`calibration_status`, `probability_scope`, versão do calibrador/limiar e suporte
de domínio. Uma probabilidade não estimável fica ausente com motivo; um alerta
não é confirmação de defeito. A persistência pode reusar campos/metadados
existentes ou exigir migração local explicitamente testada nas tarefas técnicas.

`ExternalGroundTruth` deve conter `external_case_id`, condição observada, classe confirmada ou indeterminada, evidência, observador, instante e vínculo à medição. Um caso deve se referir à mesma unidade temporal e física usada pela predição. Um lote HTTP ou intervalo arbitrário não passa a ser uma medição validada por conveniência.

### 6.7. Relação e experimento de transferência

`SourceRelation` deve identificar aresta/caminho, fontes e versões, modalidades,
grandezas/representações comuns, unidade de análise, condições, IDs de observações
pareadas quando existirem, tipo de evidência e transformações versionadas. Deve
conter a hipótese, o que ela não identifica e a abrangência física da ligação.

`TransferExperiment` deve ligar a hipótese aos grupos usados para ajuste,
calibração e avaliação; método, parâmetros e seed; referências permitidas;
comparações/controles; erros de reconstrução ou previsão das pontes; sensibilidade;
confiança dos rótulos transferidos; decisão e contribuição ao dataset candidato.
Uma modalidade estimada deve ter indicador e incerteza, sem aparecer como medida
original. A probabilidade de um rótulo não é passada como classe contínua ao
`RandomForestClassifier`; a política de conversão/ponderação deve ser explícita.

Esses contratos são lógicos. Usar `study_runs`, `study_statistics`,
`study_artifacts`, `study_feature_values` e versões de `study_labels`/datasets
sempre que bastarem. Não criar tabelas ou uma infraestrutura de grafos apenas
para representar um pequeno conjunto de relações auditáveis.

## 7. Integração entre fontes: o que precisa ser demonstrado

### 7.1. Alternativas a investigar

1. Extrair características comuns que representem a mesma grandeza e anexar exemplos compatíveis de fontes diferentes.
2. Usar variáveis auxiliares disponíveis nas bases públicas para investigar relações ou orientar rótulos, mantendo a entrada final compatível com a aplicação.
3. Investigar agrupamentos nas fontes sem rótulos e sua correspondência com referências públicas em uma representação compartilhada.
4. Avaliar transferência ou fusão estatística quando houver dados públicos de ligação, variáveis em comum ou hipóteses físicas/estatísticas explicitadas. Dados de ligação são observações públicas com modalidades efetivamente associadas que ajudam a avaliar uma relação entre fontes.
5. Reduzir o conjunto final de características se isso permitir um classificador único aplicável, justificando o efeito da redução e a participação das fontes.

Nenhuma dessas alternativas está escolhida como resultado científico antecipado. O fato de variáveis isoladas conterem informação útil é compatível com a investigação. O que precisa de evidência é a interpretação dos exemplos e a validade da associação usada para treinar e avaliar.

### 7.2. Evidências mínimas para aceitar uma associação

- Compatibilidade documentada de grandeza, unidade, ponto de medição, regime, unidade de análise e significado do alvo.
- Identificação do que foi medido conjuntamente e do que foi estimado.
- Separação entre dados usados para definir a associação e referências públicas reservadas para avaliá-la.
- Sensibilidade a parâmetros, hipóteses de associação, confiança dos rótulos derivados e escolha de fontes.
- Controle de atalhos: fonte, período, arquivo e modalidade ausente não podem explicar sozinhos uma alegação de detecção física.
- Comparação por fonte e por grupos independentes, com suporte de classes e limites de representatividade.

Normalização ajusta escalas. Ela não identifica, por si só, a distribuição conjunta de sinais nunca medidos juntos. Um coeficiente teórico pode participar de um experimento com incerteza e análise de sensibilidade, mas não deve ser apresentado como correlação empiricamente medida.

### 7.3. Investigação exigida na nova rodada

1. Mapear vibração, corrente/potência, temperatura, estado e contexto nas fontes
   de refrigeração; tratar KAIST como apoio mecânico e referência controlada.
2. Investigar características temporais, espectrais e adimensionais disponíveis,
   relações relativas a regime e transformações fisicamente justificáveis.
   Estatísticas de ciclo, médias de condição e janelas continuam distintas.
3. Avaliar se RWTH ou outra fonte já prevista fornece uma ponte entre sinais
   presentes na SMART e sinais térmicos de outras bases. Os caminhos são
   candidatos; nenhuma ligação SMART–RWTH–ULT está aceita antecipadamente.
4. Testar mapeamentos/alinhamentos em grupos públicos fora do ajuste, com
   referências preservadas e análise de sensibilidade. Um mapeamento numérico
   bom sem relação demonstrada com o alvo não basta para transferir rótulos.
5. Usar agrupamento para explorar perfis e regimes e confrontá-los com os
   rótulos da âncora. Um detector de normalidade pode ser comparação auxiliar;
   não encerra a integração nem substitui a Random Forest pretendida.
6. Contabilizar quais observações de outras fontes podem efetivamente contribuir
   para o treino, com qual representação e qual tipo de referência/derivação.
   Se um caminho falhar, registrar a causa e investigar os demais prioritários.

A investigação pública pode usar sinais auxiliares ausentes no ESP32 para
estudar mecanismos ou orientar rótulos. A definição final de entradas deve
explicar o que será mensurável na aplicação, o que serve apenas ao estudo e o
que ainda exige compatibilidade. Lacunas locais ficam visíveis sem parar T29–T31
ou os experimentos públicos de T10–T14.

## 8. Avaliação e condições de liberação

### 8.1. Níveis separados de evidência

1. **Software:** fixtures e demonstrações sintéticas verificam parsing, fórmulas, contratos, persistência, ausência de vazamento e reprodutibilidade.
2. **Desenvolvimento público:** dados públicos com referência reservada permitem comparar representações e modelos dentro dos limites dessas fontes.
3. **Teste externo local:** medições do protótipo, com referência observada e modelo congelado, avaliam aplicação no equipamento real disponível.

Cada relatório deve dizer a qual nível pertence. O conjunto externo não substitui a validação interna necessária para ajustar o modelo sem consultá-lo. O teste externo também não comprova generalização para modelos de compressor não avaliados.

### 8.2. Métricas e protocolo

A classe positiva é `1` (anomalia). O relatório deve conter TP, TN, FP e FN, com definições explícitas; acurácia; precisão; recall/sensibilidade; F1; taxa de falsos positivos; quantidade por classe e grupo; cobertura de classificação; recusas; casos indeterminados e limitações. Métricas indefinidas por ausência de suporte devem ser indicadas como não estimáveis, não como zero de desempenho.

Sempre apresentar a classe majoritária como comparação. Na SMART-PDM inspecionada, prever sempre `Normal` teria aproximadamente 97,84% de acurácia e nenhum acerto entre os 24 ciclos `Malfunction`. Portanto, acurácia isolada não libera o detector.

Antes do teste externo, o protocolo deve estabelecer critérios numéricos de sucesso, amostra e cobertura pretendidas, unidade da avaliação, agrupamento para incerteza, regras para referência indeterminada e decisões possíveis. Os valores ainda não foram acordados; devem ser definidos e justificados com dados públicos, objetivo operacional e restrições do teste, sem consultar os resultados externos. Não há promessa de um percentual nesta especificação.

Testes locais devem usar condições observáveis e procedimentos apropriados ao equipamento, sem provocar avaria perigosa para obter a classe positiva. Se só houver operação normal confirmada, relatar a avaliação parcial e a impossibilidade de estimar recall de anomalia nesse teste.

### 8.3. Protocolo probabilístico e suporte da nova rodada

T29 deve registrar antes dos novos ajustes as hipóteses, métricas principais,
comparações, suporte mínimo e decisões de sucesso/reprovação/inconclusão. O
protocolo 1.2.0 permanece imutável e seus resultados não são reclassificados.
Uma única falha disponível pode ser relatada como erro, mas não sustenta sozinha
uma conclusão ampla sobre calibração ou todos os caminhos de transferência.

Além das métricas de alerta, avaliar PR-AUC/average precision quando houver
suporte e curvas de confiabilidade, Brier score e log loss para probabilidades.
Esses escores probabilísticos refletem mais de um aspecto do modelo; não usar
um deles isoladamente para afirmar boa calibração. Informar contagens por faixa,
classe e grupo e a incerteza que os dados permitem estimar.
([Calibração — documentação oficial](https://scikit-learn.org/stable/modules/calibration.html).)

Não calibrar com pseudorrótulos e anunciar a concordância como probabilidade
confirmada de defeito. Ajustar calibrador/limiar em partições públicas apropriadas
e avaliar em referências independentes, respeitando grupos. Comparar fontes
aceitas, fonte excluída e regimes diferentes quando o desenho permitir.

Separar as saídas de T14: `public_integration_decision`,
`public_probability_support`, `local_portability_status` e
`external_release_decision`. A primeira permite decidir T15–T17; a última exige
T18/T20 e congelamento T19. Modelo de pesquisa público não recebe estado de
modelo validado localmente.

## 9. Estados, falhas e decisões de continuidade

| Etapa | Saída para avançar | Se não houver evidência suficiente |
| --- | --- | --- |
| Inventário | Fontes identificadas, acessíveis ou com limitação registrada | Manter fonte pendente/inapta e investigar alternativas públicas |
| Preparação | Dados identificáveis, íntegros e rastreáveis | Corrigir importação; não encobrir erro com preenchimento |
| Integração | Associação e representação sustentadas por evidência pública | Reavaliar características, fontes ou hipóteses; documentar inviabilidade se persistir |
| Consolidação | Dataset e partições congelados com ambas as classes e referências avaliáveis | Reabrir preparação/rotulagem; não inventar exemplos para liberar treino |
| Modelo | Critérios públicos cumpridos e versão congelada | Rever desenvolvimento público; teste externo continua reservado |
| Aplicação | Contrato de entrada atendido | Registrar incompatibilidade; não emitir “normal” por ausência de sinal |
| Teste externo | Predições e referências associadas, protocolo executado | Relatar falhas, cobertura parcial ou resultado inconclusivo |

Uma entrega de pesquisa pode concluir que certas fontes não são combináveis. Isso conclui a investigação correspondente, mas não conclui o objetivo de obter um classificador multibase aplicável. Redução do objetivo para uma única fonte, outro tipo de equipamento ou outra arquitetura final precisa ficar explícita na revisão do SDD e na decisão com o usuário.

Na versão 1.3.0, T07–T14 são reabertas para os critérios ampliados e T24 volta
a acompanhar a execução. T29 registra o protocolo, T30 completa os insumos
necessários e T31 testa as pontes públicas. Resultados históricos continuam
consultáveis; as caixas marcadas na rodada anterior não concluem os novos
critérios. Não há obrigação de sucesso de uma hipótese particular, mas há
obrigação de executar ou justificar cada caminho prioritário antes da conclusão.

### 9.1. Decisão da rodada por ciclos — 01/11/2026

A versão de pesquisa `cycle-freeze-8af6bb44817d037a836c` foi congelada com
782 ciclos SMART, 294 experimentos NIST e 35 condições TRI. A seleção usou
somente desenvolvimento público, controles por grupos e rótulos auxiliares
embaralhados. O teste reservado posterior detectou 10/11 positivos SMART,
com 21/273 falsos positivos e nove recusas por contexto, e 1/2 condições TRI.
Os limites agregados do protótipo foram cumpridos, sem alterar os critérios.

O modelo agora tem unidade de entrada diferente da hipótese inicial de
vibração/temperatura: ciclo completo e histórico causal. Isso é uma candidata
de pesquisa explícita, não autorização para mudar silenciosamente a integração
local. As entradas atuais da API não atendem ao contrato por si só.

Estados separados:

1. `public_integration_decision`: protótipo de discriminação aprovado no
   agregado registrado; TRI parcial e suporte por equipamento limitado.
2. `public_probability_support`: experimental/limitado. Brier e log loss
   superam o prior no teste SMART, mas poucos grupos e casos por faixa impedem
   afirmar calibração de probabilidade física de falha.
3. `local_portability_status`: pendente de limites reais dos ciclos e do fluxo
   de captura desses metadados; não há modelo validado no protótipo.
4. `external_release_decision`: não liberado. Campanha e referência real
   prospectivas ainda não executadas.

O teste público reservado agora está consumido. O modelo e seu limiar não
foram alterados após a avaliação. Os resultados completos e as limitações
estão no [relatório da candidata](../../docs/cycle-candidate-report.md).
O [protocolo externo](../../config/external-cycle-protocol.json) define a
campanha futura, sem inventar medições, condições ou aprovação do operador.

## 10. Regras de manutenção do SDD

Toda tarefa começa com a leitura dos requisitos e dependências pertinentes. Implementação e testes devem apontar aos IDs dos requisitos. Uma tarefa só fica concluída depois de todos os critérios de aceite aplicáveis terem evidência verificável.

Critério reprovado exige correção e nova verificação da parte afetada. Repetição não significa rodar indefinidamente o mesmo procedimento sem nova hipótese. Bloqueio externo ou resultado científico negativo deve ter causa, evidência, impacto e próxima decisão registrados, mantendo explícito o trabalho ainda não atendido.

Mudanças de fonte, representação, alvo, rótulo, limiar, algoritmo principal ou uso do conjunto externo devem atualizar este contrato, o plano e as tarefas afetadas. Alterações de significado não podem ser acomodadas somente trocando o código e preservando o mesmo nome/versão.

## 11. Referências e documentação de apoio

### 11.1. Fontes primárias públicas

- [SMART-PDM — registro e licença](https://zenodo.org/records/7245198).
- [SMART-PDM — descrição científica e aquisição](https://pmc.ncbi.nlm.nih.gov/articles/PMC10063395/).
- [KAIST — registro de dados, versão 6](https://data.mendeley.com/datasets/ztmf3m7h5x/6).
- [RWTH Aachen — dados térmicos e de vibração R290](https://zenodo.org/records/22097811).
- [RWTH Aachen — dicionário de dados](https://zenodo.org/records/22097811/files/data_mapping.csv?download=1).
- [Freezers ULT — publicação](https://pmc.ncbi.nlm.nih.gov/articles/PMC10710515/) e [coleção de dados](https://doi.org/10.6084/m9.figshare.c.6805332.v1).
- [Estudo de defeitos em compressores herméticos](https://www.mdpi.com/2076-3417/12/6/3033). Dados brutos públicos não confirmados.
- [NIST — assinaturas de vibração de três compressores](https://www.nist.gov/publications/vibration-signatures-three-positive-displacement-compressors). Publicação confirmada, dataset bruto reutilizável não confirmado.
- [Secop — catálogos de compressores](https://www.secop.com/products/technical-literature/technical-literature-show/catalogs).
- [Istat — integração e statistical matching](https://www.istat.it/en/classifications-and-tools/methods-and-software-of-the-statistical-process/process-phase/data-integration/).
- [scikit-learn — prevenção de vazamento e pré-processamento consistente](https://scikit-learn.org/stable/common_pitfalls.html).

### 11.2. Evidência e documentação locais

- [Auditoria da API e limites da inspeção do banco](../../docs/integration-audit.md).
- [Auditoria do backup](../../docs/database-dump-audit.md).
- [Exploração histórica anterior à decisão de teste externo](../../docs/unsupervised-exploration.md).
- [Metodologia implementada anteriormente](../../docs/ml-methodology.md).
- [Arquitetura implementada anteriormente](../../docs/architecture.md).

As inspeções SMART-PDM em `.reference/dataset-search/` são evidências locais ignoradas pelo Git. Sua ausência em outro clone não pode impedir reprodução: as tarefas devem reconstruí-las a partir das fontes primárias. Credenciais e conteúdo bruto privado não devem ser copiados para a documentação versionada.
