# Banco local — execução e evidências

Data: 01/11/2026. SDD: versão 1.1.0. Tarefas: T25, T27 e T28.

## Autorização e escolha

O usuário autorizou acrescentar persistência relacional e visualização ao plano,
usar um SGBD local existente, estender a estrutura da aquisição e disponibilizar
um dump inicial somente de estrutura. O servidor hospedado não foi utilizado.

A inspeção local identificou os serviços `mysql` e `postgresql-x64-17` ativos.
O serviço `mysql` usa o MariaDB do XAMPP. A conexão SQL confirmou a versão
`10.4.24-MariaDB`. Foi escolhido MariaDB para reusar a tecnologia da aquisição
e a stack SQLAlchemy/PyMySQL existente. PostgreSQL não foi modificado.

Antes da criação, foi verificada a ausência de `compressor_ml_dev`. O helper
também verificou ausência das contas do projeto e do arquivo de configuração
antes de qualquer criação, recusando substituição.

## Estrutura e configuração

Foi criado somente `compressor_ml_dev` como banco permanente desta entrega:
23 tabelas InnoDB, incluindo a cópia estrutural de `readings`, as entidades
legadas `ml_*` e a extensão `study_*`; e 9 views `mb_*`.

O ML lê `readings` e tem SELECT/INSERT/UPDATE somente nas entidades permitidas.
A conta do Metabase tem SELECT no banco do projeto. Nenhuma das duas contas tem
DDL ou permissões globais administrativas. Senhas aleatórias foram salvas
somente em `.env`, ignorado pelo Git; valores ou hashes de senha não aparecem
neste documento.

Não foram importadas leituras privadas, datasets públicos ou modelos reais.
O único registro permanente inicial é a versão técnica do esquema. Fixtures de
verificação foram criadas somente em bancos temporários exclusivos e removidas
com esses bancos depois dos testes.

## Provisionamento e exportação executados

```powershell
python -m compressor_anomaly_detection_ml.database.local_setup init
python -m compressor_anomaly_detection_ml.database.local_setup export --dump-exe mysqldump.exe --output database/local/schema.sql
python -m compressor_anomaly_detection_ml.database.local_setup verify --client-exe mysql.exe --schema-file database/local/schema.sql
```

O exportador confirmou que o dump não contém dados ou contas. SHA-256 do arquivo
inicial: `43ba08e0d7c360b605639311a7a009c99fe9edbca039d250999504cbe5f3d7b1`.

A restauração confirmou igualdade de tabelas, colunas, índices, chaves
estrangeiras, CHECKs e definições das views. Todas as tabelas restauradas estavam
vazias; todas as views executaram no destino novo. Definers e qualificações do
banco original foram removidos para impedir dependência da instância de origem.
O banco temporário foi removido; o desenvolvimento foi preservado.

## Testes e correções

Os testes direcionados `test_local_setup.py` e `test_local_mysql.py`, com
`LOCAL_MYSQL_INTEGRATION=1`, passaram: **19 testes**. Casos reais incluem recusa
de rótulo de outra observação por FK composta, CHECK de valor ausente, métricas
JSON nulas e contas com permissões limitadas.

Após a integração, a suíte completa com os novos testes locais habilitados
concluiu com **208 testes aprovados e 1 ignorado**, em 37,65 segundos. O teste
ignorado é o teste legado que exige um MySQL vazio dedicado e variáveis próprias;
os dois testes novos de MariaDB local foram executados. Ruff check e verificação
de formatação passaram em `src` e `tests`. `git check-ignore` confirmou `.env`
fora do versionamento.

Comando da regressão, sem credenciais nos argumentos:

```powershell
python -c "import os,pytest; os.environ['LOCAL_MYSQL_INTEGRATION']='1'; raise SystemExit(pytest.main(['-q','--basetemp=.pytest_cache/local-db-regression']))"
```

Esta área de trabalho ainda não possui commit desta entrega. O arquivo de
dump tem seu hash acima; o registro técnico no banco também contém o hash dos
quatro scripts aplicados. Não foi inventado um SHA de commit para a execução.

A fixture de avaliação externa gerou seis casos artificiais: TP, TN, FP e FN;
uma entrada recusada; e uma referência indeterminada. O resultado conferido foi
6 processados, 5 classificados, 4 avaliados, TP/TN/FP/FN iguais a 1, acurácia 0,5
e cobertura 5/6. Uma segunda versão de referência não duplicou casos nem alterou
a avaliação vinculada à primeira versão. Esses números verificam as consultas;
não são desempenho de um detector real.

Foi corrigida a conversão de JSON `null` para SQL numérico, preservando NULL em
vez de converter ausência de métrica para zero. Checks de estilo identificados
durante a implementação foram corrigidos antes da conclusão.

## Limites e continuação

T26 e o preenchimento dos resultados de pesquisa permanecem pendentes. O novo
banco fornece a estrutura, não a análise multibase nem a eficácia do modelo.
As tabelas, views e regras de consumo estão documentadas em
[database/local/README.md](../database/local/README.md). Metabase e painéis são
responsabilidade dos demais integrantes, fora do escopo deste backend.

A continuidade segue a ordem atualizada do SDD: T01, T26 e depois T02. Dados do
protótipo continuam reservados para teste externo, com a exposição histórica já
declarada nos documentos anteriores.

## Delimitação posterior — SDD 1.2.0

Após a preparação acima, o usuário esclareceu que nossa responsabilidade termina
na persistência e disponibilização documentada dos dados no banco. Conectar,
configurar e operar o Metabase ou criar perguntas, gráficos e dashboards são
atividades dos demais integrantes. Esse esclarecimento foi aplicado à
especificação, plano, tarefas e documentação de entrega.

As views e a conta leitora já criadas foram mantidas como interfaces de consulta.
Nenhum SQL, dado, permissão ou serviço foi alterado nesta revisão de escopo.
Os testes de banco anteriores continuam como evidência da estrutura; a revisão
1.2.0 verificou apenas consistência documental e links.
