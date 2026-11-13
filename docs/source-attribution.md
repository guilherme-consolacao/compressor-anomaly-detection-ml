# Atribuição das bases públicas

Os arquivos brutos permanecem em `data/public/raw/`, fora do Git. Relatórios,
estatísticas e amostras derivadas mantêm a origem e a versão. As transformações
do projeto são descritas nos relatórios de importação e na auditoria das fontes.

1. **SMART-PDM Appliance Dataset**, Tiago Fonseca, Luis Lino Ferreira, Pedro Chaves,
   Bernardo Cabral e Pedro Costa; registro Zenodo 7245198, publicado em 2022.
   [Dataset e metadados](https://doi.org/10.5281/zenodo.7245198).
   Licença [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
   Alterações: subset de geladeiras, associação por chave, representação relacional,
   partições por grupos e estatísticas de pesquisa. Rótulos originais preservados.

2. **Vibration, Acoustic, Temperature, and Motor Current Dataset of Rotating
   Machine Under Varying Load Conditions for Fault Diagnosis**, versão 6.
   Contribuidores conforme o metadado da versão: Wonho Jung, Seong-Hu Kim,
   SungHyun Yun, Jaewoong Bae e Yong-Hwa Park.
   [Dataset e metadados](https://doi.org/10.17632/ztmf3m7h5x.6).
   Licença [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
   Alterações: amostra explícita de duas cargas e dois diagnósticos, leitura do
   formato nativo, segmentos de cinco segundos e estatísticas por posição.
   Escala absoluta do export MAT mantida como não confirmada; momentos sem unidade
   são derivados e não equivalem a uma nova medição física.

3. **Refrigerant-Charge-Dependent Thermodynamic and Vibration Behaviour of a
   Receiver-Equipped R290 Heat Pump**, registro Zenodo 22097811, publicado em 2026.
   Criadores, com grafia do provedor: Quintana Klebig, Tim; Luca, Hummel;
   Ostmann, Philipp; Klingebiel, Jonas; Vering, Christian; Müller, Dirk.
   [Dataset e metadados](https://doi.org/10.5281/zenodo.22097811).
   Licença [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
   Alterações: associação por sessão/carga, pivot dos três eixos do compressor,
   preservação das cinco condições sem par e análise dos agregados publicados.

4. **A labelled dataset for long-term performance of Ultra-low Temperature
   Freezers under normal and faulted states**, Tao Huang, Silas Nøstvik,
   Peder Bacher, Jonas Jensen, Wiebke Markussen e Jan Møller; Figshare, versão 1,
   publicado em 2023.
   [Dataset e metadados](https://doi.org/10.6084/m9.figshare.24033324.v1).
   Licença [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
   Alterações: amostra de três logs, leitura da planilha de eventos e modelos,
   representação relacional e estatísticas. Nenhum alvo minuto a minuto foi
   inventado a partir da data de atendimento.

Os metadados completos capturados dos provedores, incluindo identidade, licença,
autoria e URLs dos arquivos, estão registrados por hash em `study_artifacts`.

## Complementos da pesquisa multibase

- **TRI-HP**, [registro primário e autoria](https://doi.org/10.5281/zenodo.5155136),
  CC BY 4.0. Alterações: separação do registrador principal e auxiliar, preservação
  de relógio local sem fuso confirmado, oito grandezas comuns e agregação por
  condição. Referências NF/EF/CVL/LL/OC originais; sem intensidade/código no modelo.
- **NIST FDD**, [dados e autoria institucional](https://www.nist.gov/el/beed/hvacr-equipment-performance-group/fault-detection-and-diagnosis-research-data),
  sob [termos NIST não SRD](https://www.nist.gov/open/license), com reconhecimento.
  Arquivo 2019, equipamentos 14/16 SEER. Alterações: °F para °C, lb/min para g/s,
  inversão explícita NF=1 para alvo normal=0, referência ausente indeterminada e
  agregação por experimento. Não equiparar potência externa a potência do compressor.
- **SMART-PDM adicional**, mesmo DOI e CC BY 4.0 da fonte acima. Sinais rápidos
  e subconjunto de lavadoras auditados; duplicidades/associações ambíguas
  quarentenadas. Contexto causal da geladeira derivado de limites publicados.
  Código original do provedor: GPL, apenas lido para auditoria, sem incorporação.
- **RWTH adicional**, mesmo DOI/CC BY 4.0 acima. 27 PSDs do compressor usados
  para integração espectral, bandas, três eixos e associação exata a condições.
- **Smart Manufacturing Testbed**, [repositório dos autores](https://github.com/submission-2022/Smart-Manufacturing-Testbed-for-Anomaly-Detection),
  commit `ae6d6bf256e80c0044dc52aafec32b0378eec5f9`, CC0 1.0 Universal.
  Auditoria de dados MEMS/piezoelétricos, integridade, lacunas e semântica de rótulos.
  Não entrou no modelo de ciclos; nenhuma classe física foi atribuída aos códigos
  sem evidência. [Artigo dos autores](https://www.mdpi.com/1424-8220/23/1/486).
- **ORNL CO2**, [dataset e autoria](https://doi.org/10.6084/m9.figshare.13232627.v1),
  CC BY 4.0. Somente metadados, código e preview foram auditados; os CSV completos
  não foram incorporados e os nomes de arquivos não viraram rótulos.

A árvore de origem dos dados usados no modelo congelado permanece SMART-PDM,
NIST e TRI-HP. As demais fontes têm papel de estudo/controle explicitado nos
relatórios. Não há afirmação de endosso dos autores nem validação universal.
