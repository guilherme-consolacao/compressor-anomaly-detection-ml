# Auditoria de integração com a aquisição

Auditoria inicial: 27 de outubro de 2026; atualizada em 28/10 com a análise do
[backup fornecido](database-dump-audit.md). A etapa inicial antecedeu a definição da persistência
do backend de ML. Nenhuma alteração foi feita na API de aquisição ou em banco
compartilhado.

## Escopo e evidências

Foi consultada a árvore recursiva completa do repositório
[`guilherme-consolacao/compressor-anomaly-detection-api`](https://github.com/guilherme-consolacao/compressor-anomaly-detection-api)
no GitHub. A referência analisada foi `main`, commit
[`6e20a97437aab48f1713b5867df60b32ad826955`](https://github.com/guilherme-consolacao/compressor-anomaly-detection-api/commit/6e20a97437aab48f1713b5867df60b32ad826955),
cuja árvore retornou `truncated=false`.

Foram lidos todos os sete arquivos versionados:

| Arquivo | Conteúdo observado |
| --- | --- |
| [`main.py`](https://github.com/guilherme-consolacao/compressor-anomaly-detection-api/blob/6e20a97437aab48f1713b5867df60b32ad826955/main.py) | Servidor HTTP, validação, calibração e inserção de leituras |
| [`database/schema.sql`](https://github.com/guilherme-consolacao/compressor-anomaly-detection-api/blob/6e20a97437aab48f1713b5867df60b32ad826955/database/schema.sql) | Criação de `compressor_db` e `readings` |
| [`README.md`](https://github.com/guilherme-consolacao/compressor-anomaly-detection-api/blob/6e20a97437aab48f1713b5867df60b32ad826955/README.md) | Instalação, execução e exemplo de payload |
| [`requirements.txt`](https://github.com/guilherme-consolacao/compressor-anomaly-detection-api/blob/6e20a97437aab48f1713b5867df60b32ad826955/requirements.txt) | `mysql-connector-python==26.7.0`, `python-dotenv==1.2.4` |
| [`.env.example`](https://github.com/guilherme-consolacao/compressor-anomaly-detection-api/blob/6e20a97437aab48f1713b5867df60b32ad826955/.env.example) | Cinco variáveis `DB_*`, valores de exemplo |
| [`.gitignore`](https://github.com/guilherme-consolacao/compressor-anomaly-detection-api/blob/6e20a97437aab48f1713b5867df60b32ad826955/.gitignore) | Ignora ambiente virtual e segredos locais |
| [`LICENSE`](https://github.com/guilherme-consolacao/compressor-anomaly-detection-api/blob/6e20a97437aab48f1713b5867df60b32ad826955/LICENSE) | Licença MIT |

Não há firmware, testes, arquivos de deploy, controle de medição ou outros
módulos na árvore consultada. A ausência no repositório não prova ausência na implantação.

Os sete arquivos do clone local foram
lidos novamente. `git rev-parse HEAD` retornou o mesmo commit auditado acima e
`git status --short --untracked-files=all --ignored` não mostrou mudanças,
arquivos não rastreados ou ignorados. A inspeção de diretório confirmou que não
há `.env` local, apenas `.env.example` com placeholders. Não foram encontradas
divergências entre a cópia local e a fonte remota auditada. A cópia da API não
foi modificada e seu código não foi executado.

## Tentativa de acesso ao banco implantado — 27/10/2026

Após a auditoria inicial, o usuário forneceu credenciais e autorizou consultas
somente de leitura no servidor MariaDB/MySQL informado. A tentativa de acesso
externo alcançou o servidor, que recusou a autenticação com o código **4151**
(`ER_ACCOUNT_HAS_BEEN_LOCKED`: conta bloqueada). Esse significado consta na
[documentação oficial do MariaDB](https://mariadb.com/docs/server/reference/error-codes/mariadb-error-codes-4100-to-4199/e4151).

Não foi possível iniciar a sessão de inspeção: nenhuma consulta de metadados
ou leituras foi executada, nenhum dado foi obtido e nenhuma alteração foi feita
no banco. A senha foi fornecida ao processo por entrada oculta em memória e
não foi gravada em arquivos, configuração, documentação ou histórico Git.

A inspeção online continua pendente até o responsável liberar a conta no servidor
ou disponibilizar um usuário de leitura habilitado para acesso remoto. Não foi
possível determinar a causa do bloqueio nem confirmar a validade da senha.
Naquele momento, as conclusões continuavam limitadas à fonte versionada. A análise
posterior do backup está registrada na seção seguinte e no relatório específico.

## Snapshot do banco fornecido em 28/10/2026

A exportação histórica da telemetria foi lido como texto, sem
executar SQL ou importar dados. O dump informa MariaDB 11.8.9 e conclusão em
18/10/2026 às 02:06:54 (fuso do rodapé não informado). Os TIMESTAMPs exportados
usam UTC. Foram encontradas 3.701 leituras de 08/10, de 01:30:06 a 19:59:18 UTC.

Nesse snapshot existe apenas a definição de `readings`, equivalente aos campos,
tipos, chave primária e índice descritos na fonte. A engine é explicitamente
InnoDB, com IDs 1 a 3701 e próximo auto incremento 3702. Não há estruturas de
medição, equipamento, grupo, rótulo ou finalização no arquivo. Não foram
encontradas definições de views, triggers ou rotinas; as opções da exportação
não permitem garantir ausência desses objetos no servidor atual.

O RMS é numericamente compatível com a fórmula instantânea da API em todas as
linhas, admitindo arredondamento de seis casas. O intervalo mediano entre
registros é 13s, variando de 12s a 243s. Isso não comprova frequência física de
amostragem nem permite reconstruir medições. O `INSERT` extenso é uma escolha
do exportador e não demonstra recebimento HTTP em lote.

Veja [a análise do backup](database-dump-audit.md) para hash, estatísticas,
verificações, extremos e limites. A inspeção online permanece pendente; o
backup não representa necessariamente o banco atual. Nenhuma medição ou rótulo
foi inventado a partir das leituras históricas.

## Banco implantado: limite da inspeção inicial

O esquema descrito abaixo foi observado no SQL versionado e no código. **Não é
resultado de inspeção do MySQL implantado.** Credenciais e conectividade do
ambiente compartilhado não haviam sido fornecidas no pedido inicial. Foi confirmado que não
havia `.env` no repositório inicial nem variáveis `DB_*` disponíveis no ambiente.
Na etapa inicial, nenhuma conexão ao banco real foi realizada. A instalação real pode
conter mudanças posteriores ou locais.

Antes de qualquer aprovação de migração, usar conta de leitura para comparar:

```sql
SELECT VERSION(), DATABASE(), @@session.time_zone, @@global.time_zone;

SELECT TABLE_NAME, ENGINE
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME;

SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
       COLUMN_DEFAULT, DATETIME_PRECISION, EXTRA
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME, ORDINAL_POSITION;

SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, COLUMN_NAME, SEQ_IN_INDEX
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;

SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME,
       REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION;

SHOW CREATE TABLE readings;
```

Comparar também se a tabela usa engine transacional. O SQL original não fixa
`ENGINE`; depender do padrão do servidor não é evidência de InnoDB implantado.
As consultas acima não modificam esquema ou dados. O script de inicialização
da API não foi executado: mesmo com `IF NOT EXISTS`, ele cria estruturas, usa
um nome fixo de banco e não demonstra que uma tabela existente é compatível.

## Fluxo efetivamente implementado pela API

`HTTPServer` da biblioteca padrão escuta `0.0.0.0:8000`. O caminho suportado é
`POST /api/compressor`. O payload documentado é:

```json
{
  "temperature": 34.8,
  "vibration": {"x": 0.01, "y": 0.02, "z": 0.03}
}
```

Cada requisição produz uma única linha. A API exige `temperature` não nulo e
um objeto `vibration` com os três eixos, converte cada eixo com `float`, aplica
calibração, calcula `rms`, abre uma conexão, insere a leitura e faz `commit`.
A temperatura é enviada diretamente ao driver; não há validação explícita de
tipo, valor finito ou intervalo físico. A validação de ML precisa continuar
existindo mesmo para registros aceitos pela aquisição.

Há respostas 400 para JSON inválido/corpo vazio, 422 para campos ausentes,
500 para erros de inserção ou outras exceções, e 201 para sucesso. O corpo é
decodificado antes do `try`, e alguns erros de protocolo não têm tratamento
específico. Não há idempotência do pacote, sequência do dispositivo, timestamp
de captura, confirmação com ID da linha inserida, armazenamento de pacotes
perdidos ou retentativa controlada. Um reenvio pode gerar outra linha. Não é
possível medir perdas de comunicação apenas com esses registros.

## Sinais, calibração e significado de RMS

A aquisição aplica os seguintes tratamentos antes de persistir:

1. Subtrai offsets de repouso: X `-0.00048828125`, Y `0.0152994791667`,
   Z `0.0231119791667`.
2. Define como zero qualquer eixo corrigido cujo módulo seja estritamente
   menor que `0.01`.
3. Calcula `sqrt((accel_x**2 + accel_y**2 + accel_z**2) / 3)`.

Os offsets são estimativas a partir de três pacotes com o sensor parado,
conforme o comentário do código. Os dados brutos anteriores à calibração e à
supressão de ruído não são preservados no banco. Os valores zero armazenados
são resultados do tratamento de aquisição, e não devem ser interpretados como
leituras ausentes nem preenchidos novamente pelo ML.

O campo `rms` representa uma combinação quadrática **instantânea dos três
eixos**, com divisão por três. Não é a magnitude euclidiana simples nem RMS
de vibração calculado sobre uma janela temporal. O ML deve consumir essa série
com seu significado atual. Recalibrar os eixos ou substituir `rms` por outra
fórmula mudaria os dados e exige proposta aprovada, nova versão de processamento
e retreinamento. A descrição conceitual `vibracao_rms_g` não comprova que exista
RMS temporal em g.

A temperatura é descrita em graus Celsius no log de sucesso. README e código
não demonstram a conversão física dos eixos; a unidade g precisa ser confirmada
com o responsável pelo firmware. Também faltam frequência de amostragem,
resolução dos sensores, faixa MPU-6050, orientação da montagem, tratamento de
gravidade no dispositivo e versão de calibração por registro. Essas informações
devem integrar o contrato de sinal antes da validação real do modelo.

## Esquema versionado da aquisição

Uma única tabela, sem chaves estrangeiras:

| Campo em `readings` | Definição no SQL | Equivalência conceitual |
| --- | --- | --- |
| `id` | `BIGINT UNSIGNED`, PK, auto incremento | ID de leitura; nunca ID de medição |
| `temperature` | `DECIMAL(12,6) NOT NULL` | `temperatura_c`, com unidade a validar operacionalmente |
| `rms` | `DECIMAL(12,6) NOT NULL` | Série RMS instantânea da API; unidade ainda não comprovada |
| `accel_x` | `DECIMAL(12,6) NOT NULL` | `eixo_x_g`, sujeito à confirmação de unidade |
| `accel_y` | `DECIMAL(12,6) NOT NULL` | `eixo_y_g`, sujeito à confirmação de unidade |
| `accel_z` | `DECIMAL(12,6) NOT NULL` | `eixo_z_g`, sujeito à confirmação de unidade |
| `timestamp` | `TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP` | Horário de inserção pelo banco |

Há índice `idx_readings_timestamp(timestamp)`. Não há frações de segundo no DDL.
Várias leituras podem legitimamente compartilhar o mesmo timestamp. Ordenar por
`timestamp, id` fornece uma ordem determinística; não recupera os instantes de
captura perdidos. O timestamp não identifica início/fim de coleta nem garante a
frequência física. O fuso da sessão do MySQL deve ser inspecionado; não assumir
que um `datetime` sem fuso retornado pelo driver é UTC.

`DECIMAL(12,6)` arredonda a seis casas e limita a faixa numérica. A comparação
com dados reais deve considerar essa quantização. Nenhum renomeamento desses
campos é necessário: a camada de persistência do ML pode fornecer aliases.

## Compatibilidade com os requisitos

| Necessidade do ML | Situação no repositório da API | Adaptação/decisão |
| --- | --- | --- |
| Cinco séries por leitura | Existem `temperature`, `rms`, `accel_x/y/z` | Reaproveitar `readings`; confirmar semântica e unidades |
| Medição com identidade e ciclo confiável | Não existe | Introduzir contrato explícito de medição |
| Equipamento | Não existe | Exigir identificação do produtor, sem inventar ID a partir de vibração |
| Início, fim, duração, contagem | Não existem por medição | Registrar no encerramento pelo produtor/coordenador autorizado |
| Associação leitura → medição | Não existe | Associação explícita por IDs, sem janelas arbitrárias |
| Status de finalização | Não existe | Persistir finalização após conclusão das gravações |
| Rótulo real e origem | Não existem | Rotulação independente por medição, com proveniência |
| Compressor ligado/tempo desde partida | Não existem | Manter ausentes; não incluir nas 20 características |
| Características e versão de processamento | Não existem | Estruturas de propriedade do ML |
| Modelos, artefatos e métricas | Não existem | Estruturas de propriedade do ML e arquivos `joblib` |
| Predições e histórico por modelo | Não existem | Unicidade por medição/modelo, sem depender de status global |
| Importância global por variável/modelo | Não existe | Persistir uma vez ao treinar |
| Garantia contra duplicação de pacotes | Não existe | Discutir separadamente com aquisição/firmware |
| Resolução temporal/Hz confiável | Não demonstrada | Obter contrato do firmware e inspecionar banco real |

## Proposta de integração com menor impacto

Preservar `readings` e seus nomes. O adaptador de ML apenas lê a telemetria. A
identidade da medição deve vir de uma fonte confiável que conheça o ciclo real,
nunca de intervalos de IDs, contagem fixa ou agrupamento arbitrário por horário.
Os 15 segundos continuam como referência de aquisição, não uma janela criada
pelo ML.

Uma alternativa sem `ALTER TABLE readings` é adicionar tabelas auxiliares de
medição e associação de IDs de leitura, além das estruturas exclusivas de ML.
Cada associação referencia uma leitura existente. Unicidade sobre `reading_id`
impede que uma leitura represente duas coletas nessa versão do contrato. Uma
medição contém equipamento, início, fim, contagem, duração, rótulo opcional e
origem. Seu produtor deve fechar a medição apenas após gravar todas as leituras.
A aquisição não pode acrescentar leituras a uma medição encerrada; os IDs e a
proveniência dos dados usados pelo ML permanecem rastreáveis.

Essa proposta ainda requer um mecanismo confiável de produção do manifesto de
IDs. A API atual não retorna IDs de leitura nem recebe um identificador de ciclo;
portanto, adicionar apenas tabelas não conclui a integração. Discutir com a equipe de aquisição
como identificar cada ciclo e obter seus IDs exatos. Uma extensão de payload com
ID de medição e eventos de início/fim, ou um coordenador que conheça os commits e
IDs, são alternativas a avaliar com o firmware. Nenhuma delas foi implantada.

Outra alternativa é adicionar uma FK nullable de medição a `readings`, preservando
leituras históricas sem medição. Isso reduz uma associação, mas exige alteração
da tabela compartilhada e do caminho de inserção da API. A escolha final depende
do esquema real e da revisão da equipe de aquisição. Não retroatribuir leituras históricas a
coletas sem evidência externa independente.

O backend de ML pode implementar desde já o domínio de medição, validação,
extração, treinamento, inferência, persistência dos resultados e CLI sobre um
contrato explícito. Fixtures e dados sintéticos devem ser marcados como tais.
A demonstração local não comprova a disponibilidade desse contrato no servidor.

### Contrato isolado adotado pelo MVP de ML

O esquema auxiliar revisável usa `ml_measurements`,
`ml_measurement_readings` (com `reading_id` único), `ml_features`, `ml_models`,
`ml_predictions`, `ml_processing_runs` e `ml_feature_importances`. Essas tabelas
são novas estruturas do contrato proposto, não estruturas observadas no banco
compartilhado.

A unidade de aceleração deve ser explicitamente `g` em cada medição. Valor
desconhecido não recebe esse significado automaticamente e impede extração.
A definição de sinal é `api-calibrated-spatial-rms-v1`; a versão inicial das
características é `spatial-rms-stats-v1`. Isso documenta que as quatro
características `vib_rms_*` resumem a série RMS espacial existente. Não há
alteração silenciosa para RMS temporal.

SQLite é usado para testes e demonstração isolada, com uma tabela `readings`
compatível criada exclusivamente nesse ambiente. O MySQL real recebe somente
scripts revisáveis; eles não foram aplicados. O processamento em produção ainda
depende de aprovação do esquema, do produtor de finalização e das unidades.

## Alterações que precisam de aprovação

Antes de executar mudanças no ambiente compartilhado:

1. Comparar metadados reais com o SQL auditado e revisar engine, tipos, índices,
   fuso, resolução temporal e permissões.
2. Aprovar a representação de medição, associação de leituras e protocolo de
   encerramento com a equipe de aquisição; avaliar impacto no firmware.
3. Confirmar unidade dos eixos e significado físico de RMS; escolher a versão
   do contrato de sinal. Preservar o significado da aquisição atual.
4. Aprovar scripts de criação das estruturas auxiliares e exclusivas de ML,
   chaves estrangeiras e permissões de escrita limitadas a essas estruturas.
5. Revisar qualquer mudança na API, inclusive validação, timestamps e retorno
   de IDs, antes de aplicá-la.

Os scripts deste projeto são materiais de revisão ou de ambiente local. Não há
migração automática ao conectar, iniciar CLI, treinar ou executar o worker.

## Riscos e caminho para validação real

A lacuna bloqueante é a ausência de medições finalizadas identificáveis, seguida
pela unidade/frequência dos sinais não confirmadas. O modelo não deve processar
leituras independentes como se fossem medições completas. Timestamp com resolução
de segundos também impede deduzir qualidade de amostragem de alta frequência.

O caminho mais curto é confirmar o contrato com a aquisição, inspecionar o banco
em modo leitura, revisar e aprovar o esquema auxiliar, registrar coletas reais
encerradas com rótulo independente e grupos operacionais conhecidos, e executar
treinamento/avaliação separados. A qualidade científica de vibração depende de
amostragem adequada; o mínimo de duas amostras no extrator é apenas proteção de
software. Até esse processo, não há evidência de confiabilidade para defeitos reais.
