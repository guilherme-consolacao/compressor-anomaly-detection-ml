# Relatório da implementação — 27/10/2026

Atualização em 28/10: foi analisado um backup fornecido posteriormente, com
3.701 leituras históricas, sem importação ou execução de SQL. O snapshot confirmou
a estrutura de `readings`, a engine InnoDB e a consistência numérica do RMS;
continuam ausentes IDs/limites de medição e rótulos. Veja
[a análise do backup](database-dump-audit.md). Nenhum modelo foi treinado ou
validado com essas leituras. A inspeção online continua pendente após a recusa
anterior de autenticação por conta bloqueada. As limitações de acesso descritas
no relato inicial abaixo referem-se à etapa de 27/10.

## Sistema existente e compatibilidade

A API e seu fork local foram analisados integralmente no commit `6e20a97`:
sete arquivos versionados, sem diferenças locais. Há uma tabela `readings`
com sensores, ID autoincremental e timestamp do banco. O recebimento é por
leitura via HTTP; os eixos passam por offsets e supressão de valores baixos,
e `rms` combina espacialmente os eixos de um pacote. Não representa RMS temporal.

As cinco séries podem ser adaptadas por equivalência de nomes, preservando a
calibração. Unidade dos eixos, frequência, identidade de equipamento, limites
de coleta, encerramento e origem dos rótulos não estão confirmados ou não
existem. O banco implantado não foi inspecionado por falta de acesso/configuração;
a análise do SQL do repositório não foi apresentada como inspeção do banco real.

## Implementação concluída

- Aplicação Python executável, configuração por ambiente e interface CLI.
- Domínio tipado e adaptação da tabela `readings` existente.
- Validação de medições encerradas e 20 estatísticas determinísticas (`ddof=0`).
- Dataset rotulado, split por grupos e Random Forest com parâmetros centralizados.
- Matriz de confusão, acurácia, precisão, recall e F1 no holdout.
- Artefatos joblib versionados, checksum e validação de contratos.
- Inferência com mapeamento por `classes_`, sem confundir ausência de dados com normalidade.
- Persistência transacional, chaves únicas, versões e histórico; erros separados.
- Polling configurável, lotes limitados e encerramento controlado.
- SQL revisável para tabelas auxiliares e consultas de apoio ao Metabase.
- Testes unitários, integração SQLite e teste opcional MySQL isolado.
- Demonstração sintética executável sem o dispositivo ou MySQL.

O diagrama e a árvore dos módulos estão em `architecture.md` e no README.
Os principais arquivos são `domain/entities.py` (contratos),
`features/extraction.py` (validação/estatísticas), `ml/training.py` (dataset e treino),
`ml/inference.py` (predição), `ml/artifacts.py` (versionamento),
`database/repository.py` (transações), `services.py` (casos de uso) e `cli.py`.

## Validação realizada

A suíte executada no ambiente virtual Python 3.12 passou com **189 testes
aprovados e 1 pulado**. O teste pulado requer um MySQL vazio e isolado e não foi
executado contra uma instância MySQL/MariaDB. SQLite não comprova sozinho os
comportamentos desse servidor. Os testes cobrem também concorrência e rollback
com falha injetada, probabilidade com classes reordenadas, reavaliação com nova
versão, rejeição de dataset de uma classe, checksum, contratos e CLI.
Ruff (`check` e `format --check`) e compilação dos módulos também passaram.

A demonstração `validation-demo.sqlite` foi executada: 36 medições artificiais,
32 rotuladas, treino com 24 medições e holdout com 8 (4 de cada classe).
A execução produziu matriz `[[4, 0], [0, 4]]` e acurácia/precisão/recall/F1 iguais
a `1.0`, **exclusivamente nesse conjunto artificial facilmente separável**.
Isso não é evidência de detecção de defeitos no compressor real.

O modelo `synthetic-v1` foi salvo e registrado; `synthetic-035` recebeu classe
`1`, probabilidades `0.005`/`0.995` e registro recuperável no SQLite. A repetição
retornou `created: false`, preservando uma única predição. Os arquivos locais da
demonstração são ignorados pelo Git.

## Integração parcial e pendências

O adaptador MySQL e os scripts estão implementados, mas a implantação e o fluxo
com aquisição real continuam pendentes. A API não foi modificada. Nenhuma
migração ou escrita foi feita no banco compartilhado, e nenhum modelo foi
validado com dados reais. A criação de dashboards e o produtor de finalização
na API não fazem parte do código entregue.

O caminho mínimo é:

1. Confirmar `g`, frequência, significado físico dos sinais e fuso com o firmware.
2. Inspecionar o MySQL implantado com usuário de leitura e comparar metadados.
3. Revisar/aprovar as tabelas auxiliares e o contrato de associação/finalização.
4. Adaptar a aquisição/coordenador para publicar coletas explícitas e imutáveis.
5. Validar o fluxo no MySQL isolado e reunir rótulos/grupos independentes reais.
6. Treinar e avaliar com essas medições antes de usar resultados em campo.

## Reprodução

O README inclui instalação, variáveis de ambiente, todos os comandos CLI e
testes. Uma validação independente inicial pode ser feita com:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_cache/local-run
.\.venv\Scripts\python.exe -m compressor_anomaly_detection_ml demo --database nova-demo.sqlite
```

Para MySQL, comece por `check-db` e `inspect-contract`. Execute o SQL de proposta
somente depois da inspeção e da aprovação das alterações compartilhadas.
