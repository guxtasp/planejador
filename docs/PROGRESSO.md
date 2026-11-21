# PROGRESSO — Planejador Acadêmico multi-curso

> **Arquivo de retomada.** Se a conversa acabar, envie este arquivo + o zip mais
> recente em um chat novo e cole o prompt da seção "Como retomar".
> Atualize a tabela e o "Próximo passo" ao fim de CADA etapa.

## Status

| Etapa | Entrega | Status |
|-------|---------|--------|
| 0   | Fundação: factory, config, erros, health, testes de caracterização do app legado | ✅ Concluída |
| 1A  | Modelos SQLAlchemy + migração inicial | ✅ Concluída |
| 1B  | Repositories + seed de CC vira `examples/*.csv` | ✅ Concluída |
| 2   | Motor de regras puro (`planner/domain`) | ✅ Concluída |
| 3A  | Importação CSV: parser + validação de schema | ✅ Concluída |
| 3B  | Importação CSV: validação referencial/semântica + prévia (dry-run) | ✅ Concluída |
| 3C  | Importação CSV: commit atômico + endpoints + tela de prévia + prompt de IA | ✅ Concluída — 🛑 aguardando validação do usuário |
| 3D  | Ajustes pedidos após a 3C: sem histórico no CSV, storytelling na tela de importação, novas fontes de dados (quadro de horários, sites institucionais) | ✅ Concluída — 🛑 aguardando `pytest` completo e validação do usuário |
| 4A  | Frontend modular + onboarding (escolher/criar curso) | ✅ Concluída — 🛑 aguardando `pytest` completo (backend não rodou no ambiente) e validação do usuário |
| 4B  | Turmas/encontros no planejador, calendário e conflitos por turma | ✅ Concluída — 🛑 aguardando `pytest` completo (backend não rodou no ambiente) e validação do usuário |
| 5A  | Autenticação por link mágico (e-mail), sessão, rotas protegidas, posse de curso | ✅ Concluída — 🛑 aguardando `pytest` completo (backend não rodou no ambiente) e validação do usuário |
| 5B-1 | Login pelo Supabase (substitui o link mágico da 5A) | ✅ Concluída — 🛑 aguardando `pytest` e validação |
| 5B-2 | Histórico (N tentativas), planos por usuário, dashboard/status do fluxograma | ✅ Concluída — 🛑 aguardando `pytest` completo (não rodado no ambiente, a pedido) e validação |
| 5B-3 | Calendário livre: horários próprios por disciplina (sem depender de quadro importado) | ✅ Concluída — 🛑 aguardando `pytest` completo + `flask db upgrade` e validação |
| 6   | Deploy Vercel + Postgres, CI | 🟡 Arquivos prontos (`api/index.py`, `vercel.json`, CI, `docs/DEPLOY.md`); falta o deploy real 🛑 |
| 7   | Documentação final (IMPORTACAO.md, README, DEPLOY.md) | 🟡 README e DEPLOY.md atualizados; revisar IMPORTACAO.md |
| Futuro | **Melhorar UI e comunicabilidade. Nada explicativo: aprende-se só testando** (ver Tarefas futuras) | ⏳ 1ª passada feita |

Legenda: ✅ feito · ⏳ em andamento/próxima · ⬜ pendente · 🛑 parar para validação do usuário

## Etapa 0 — o que foi feito

- Pacote `planner/` com Application Factory (`create_app`), configs por ambiente,
  extensões (`db`, `migrate`), tratamento central de erros JSON e `/api/health`.
- Esqueleto das camadas vazias: `models/ repositories/ services/ domain/ importers/`.
- `legacy/app_legacy.py` = `app.py` original, **intocado**, usado só pelos testes
  de caracterização (não é mais o ponto de entrada).
- `planner/templates/index.html` = frontend original, **intocado** (ainda não é
  servido; a API nova só tem `/api/health`).
- 11 testes passando (`pytest`): 2 da app nova + 9 de caracterização do legado
  (6 marcados `legacy_bug`, que documentam os defeitos do diagnóstico).
- Descobertas: o seed tem **49** disciplinas (README dizia 40); INF110×EST105
  colidem em 2 dias (SEG e QUI).

## Etapa 1A — o que foi feito

- `planner/models/` com as 10 tabelas de `ARQUITETURA.md §4`, um módulo por assunto:
  `curso.py`, `disciplina.py` (Disciplina + Requisito), `oferta.py` (Turma + Encontro),
  `usuario.py` (Usuario + Historico), `plano.py` (Plano + PlanoSemestre + PlanoItem),
  `enums.py` (vocabulários fechados). Tudo reexportado por `planner/models/__init__.py`.
- Campos acadêmicos opcionais são `NULL` (só `nome`/`codigo`/`tipo` etc. são obrigatórios).
- Enums gravados como texto + `CHECK` (portável SQLite/Postgres), via helper `check_enum`.
- Integridade: `UNIQUE(curso_id, codigo)`, `UNIQUE` de turma/semestre/requisito,
  `CHECK` (início < fim, créditos/vagas ≥ 0, nota 0–100, sem autorrequisito).
- Cascatas: curso → disciplinas → requisitos/turmas/encontros (`CASCADE`);
  **`historico.disciplina_id` = `RESTRICT`** (apagar disciplina/curso com histórico é bloqueado);
  apagar usuário apaga histórico e planos, mas o curso sobrevive (`dono_id` → `SET NULL`);
  apagar turma mantém o item do plano sem turma (`SET NULL`).
- `extensions.py`: convenção de nomes de constraints (necessária ao Alembic/SQLite) e
  `PRAGMA foreign_keys=ON` no SQLite — sem isso as FKs seriam ignoradas nos testes.
- `Migrate(render_as_batch=True)`; pasta `migrations/` criada; migração inicial
  `05f7ecdec8d2_schema_inicial.py` (upgrade, downgrade e `flask db check` limpos).
- 42 testes passando: 11 anteriores + 28 de schema (`test_models_schema.py`) +
  3 de migração (`test_migracao.py`, incluindo "modelos e migração não divergem").
  Conferido por mutação: sem o PRAGMA, 9 testes de schema falham.

### Decisões/limites da 1A (para quem continuar)

- `StatusHistorico` mantém só `aprovado/reprovado/cursando` (os do app original);
  se a Etapa 2 precisar de `trancado/dispensado`, é uma migração de `CHECK`.
- `dias_letivos` é coluna JSON (lista de siglas); `NULL` = derivar da grade (Etapa 4B).
- `Usuario` só tem `email/nome/criado_em`; campos de autenticação entram na 5A.
- Regras que o banco não consegue garantir ficam para serviços/importador: requisito apontando
  para disciplina de **outro curso** (3B) e `turma` pertencer à `disciplina` em `PlanoItem` (4B).
- Nota é `Numeric(5,2)` com `CHECK 0–100`; se algum curso usar escala 0–10, ela cabe, mas a
  validação de faixa por curso é semântica (importador).

## Etapa 1B — o que foi feito

- `planner/repositories/`: um repository por modelo, todos herdando `RepositorioBase`
  (`base.py`): `CursoRepository`, `DisciplinaRepository`, `RequisitoRepository`,
  `TurmaRepository`, `UsuarioRepository`, `HistoricoRepository`, `PlanoRepository`.
- Política de transação: `adicionar`/`remover` fazem `flush`, **nunca `commit`** — o limite da
  transação é de quem chama (necessário ao commit atômico da 3C). Sessão injetável (`sessao=`).
- Sem N+1 (`selectinload`), provado por testes que contam as instruções SQL:
  `DisciplinaRepository.listar_do_curso(com_requisitos, com_turmas)` = 4 consultas fixas;
  `TurmaRepository.listar_do_curso` = 2; `PlanoRepository.obter_completo` = 5.
- Ordenação portável: disciplinas por `periodo_sugerido` com NULL por último
  (`.is_(None)` primeiro; SQLite e Postgres ordenam NULL de formas diferentes).
- `tools/export_legacy_seed.py` (`python -m tools.export_legacy_seed`): sobe o legado num banco
  temporário e converte o seed em `examples/ciencia-da-computacao/{curso,disciplinas,requisitos,turmas}.csv`
  (UTF-8 com BOM, delimitador `,`). 49 disciplinas, 46 requisitos, 61 turmas; `curso.csv` só traz o que o seed afirma.
- 69 testes passando: 42 anteriores + 16 de repositório (`test_repositories.py`) + 11 do exportador
  (`test_export_legacy_seed.py`), incluindo: CSVs versionados não podem ficar defasados em relação ao
  exportador, e os CSVs carregam no schema sem violar constraints.

### Decisões/limites da 1B (para quem continuar) — REVISAR OS CSVs

- **Inferências a partir de comentários do seed** (constantes nomeadas em `export_legacy_seed.py`):
  - `periodo = 9` no legado era só agrupamento das optativas → viram `tipo=optativa` e `periodo_sugerido` vazio.
  - "2026/1 (Ímpares) e 2026/2 (Pares)" → períodos ímpares = `2026/1`, pares = `2026/2`
    (INF498, 7º → 2026/1; INF499, 8º → 2026/2, pela mesma regra).
  - ⚠️ **Optativas**: o seed diz "26/1 e 26/2" sem separar. Para não escolher sozinho, cada uma foi exportada
    **nos dois períodos** (26 das 61 turmas). Apague a linha que não se aplica em `turmas.csv`
    (e rode o teste de drift após regenerar, ou ajuste a constante `PERIODOS_LETIVOS_DAS_OPTATIVAS`).
- Vazio = desconhecido: `instituicao`, totais de créditos/CH, `max_creditos_semestre`, `duracao_semestres`,
  `dias_letivos`, `docente`, `vagas` e `grupo_alt` saem vazios (o seed não os traz).
- INF497 tem 0 créditos/0 CH no seed (mantido como está) e **não tem horário** → fica sem turma.
- Legado só tem um conjunto de horários por disciplina → `codigo_turma = T1` para todas.
- Nomes de colunas dos CSVs foram fixados aqui de forma provisória; **a 3A os formaliza** (ARQUITETURA.md §5):
  `disciplinas.csv: codigo,nome,creditos,carga_h,periodo_sugerido,tipo,cor` ·
  `requisitos.csv: disciplina,requisito,tipo,grupo_alt` ·
  `turmas.csv: disciplina,periodo_letivo,codigo_turma,docente,vagas,horarios`.
- Repositories não validam regra nenhuma: requisito entre cursos distintos continua para a 3B.
- Remover curso/disciplina com histórico levanta `IntegrityError` (RESTRICT da 1A); o serviço decide como tratar.

## Etapa 2 — o que foi feito

- `planner/domain/` (só stdlib; teste de arquitetura `test_domain_pureza.py` vigia isso):
  - `entidades.py`: value objects `@dataclass(frozen=True)` — `Disciplina`, `Requisito`, `Tentativa`, `Encontro`, `Turma`.
  - `historico.py`: N tentativas → situação por disciplina (aprovada > cursando > reprovada). **Corrige bug #4.**
  - `requisitos.py`: `avaliar_requisitos` (pre/co, grupos OR por `(tipo, grupo_alt)`), `verificar_plano`
    (semestres anteriores do plano contam como concluídos — **corrige bug #5**), `classificar_disciplinas` (assistente).
  - `progresso.py`: obrigatórias + optativas **limitadas ao exigido**; sem base → `None`, nunca inventa percentual.
  - `carga.py`: sobrecarga pelo `max_creditos_semestre` do curso; limite `None` = sem julgamento (fim do "28" fixo).
  - `conflitos.py`: por turma, três resultados `conflito` / `conflito_possivel` / `sem_turma_compativel`.
  - `previsao.py`: média do próprio aluno com fallback configurável; calendário por `periodo_letivo` ("AAAA/N",
    `periodos_por_ano` parametrizável) — fim do `getMonth() < 6`.
- Testes: `test_domain_requisitos.py`, `test_domain_progresso_carga_previsao.py`, `test_domain_conflitos.py`,
  `test_domain_pureza.py` (49 casos). Os `legacy_bug` **foram invertidos** nesses arquivos (bugs #4, #5, "28 fixo",
  "optativas no denominador", "média 20"); os testes de caracterização do legado continuam como estão (documentam o app antigo).
- Não foram tocados: rotas, repositories, modelos, migrações, frontend.

### ⚠️ Verificação desta etapa (ler antes de confiar) — ✅ RESOLVIDO na 3A: `pytest` completo rodado, 118 verdes

O ambiente em que a Etapa 2 foi feita **não tinha rede**, então `pytest`, SQLAlchemy e Flask-SQLAlchemy não puderam ser
instalados. Portanto:
- Os 49 testes de domínio foram executados com um executor mínimo (fora do projeto) e passaram; também foi feita
  verificação por mutação (5 mutações, todas derrubadas por algum teste).
- **A suíte completa (`pytest`, esperada: 69 antigos + 49 novos = 118) NÃO foi rodada.** Rode `pytest` na sua máquina
  antes de seguir; se algo falhar, traga a saída no próximo chat.

### Decisões/limites da Etapa 2 (para quem continuar)

- **`StatusHistorico` não ganhou `trancado`/`dispensado`**: trancamento não conclui nada (não registrar) e dispensa/
  equivalência entra como `aprovado`. Status desconhecidos são ignorados pelo motor. Sem migração de `CHECK`.
- **Optativas e eletivas formam um pool único** contra `creditos_optativos_exigidos` (§6 da ARQUITETURA). Se o curso não
  informa esse valor, optativas não entram no denominador. Grupos de optativas ficam para depois.
- Plano é projeção otimista: o que está em semestre anterior conta como concluído nos seguintes (avisa, não bloqueia).
- `cursando` satisfaz só correquisito, nunca pré-requisito (mesmo critério do legado).
- Conflitos são analisados **par a par**; três disciplinas que só colidem em conjunto não são detectadas.
  Disciplina sem turma ofertada não é julgada. Horários que só se tocam (fim == início) não colidem.
- Créditos `None` contam 0 na soma mas aparecem em `disciplinas_sem_creditos` para a UI poder avisar.
- Os serviços (Etapa 4B/5B) é que converterão modelos → entidades do domínio; ainda não existe nenhum serviço.

## Etapa 3A — o que foi feito

- `planner/importers/` (só leitura e validação de **schema**; nada é gravado, nenhum módulo importa Flask/db/repositories —
  vigiado por teste):
  - `base.py`: `Issue{arquivo,linha,coluna,severidade,mensagem}` (+ `para_dict()` p/ JSON), `Severidade`, `Esquema`,
    `LinhaCsv`, `Tabela`, `ResultadoLeitura` (`registros`, `issues`, `erros`, `avisos`, `linhas_lidas`, `linhas_descartadas`).
  - `leitor_csv.py`: decodifica (UTF-8/BOM; Windows-1252 com aviso; binário/.xlsx recusado), detecta delimitador
    (`,` `;` TAB), valida cabeçalho (obrigatórias, repetidas, desconhecidas = aviso, aliases) e entrega as linhas.
  - `horarios.py`: `parse_horarios("SEG 16:00-18:00 | QUI 14:00-16:00")` → `domain.entidades.Encontro` (reaproveitado).
  - `campos.py`: `LeitorLinha` (texto, código, inteiro, decimal, escolha, período letivo, cor, dias) acumula os problemas;
    `vocabulario()` monta as opções a partir dos Enums do banco (não diverge de `models/enums.py`).
  - `importador.py`: `CsvImporter` (Strategy + Template Method): `importar()` lê, converte linha a linha e **descarta a
    linha com qualquer erro**; gancho `verificar_arquivo()`.
  - `curso.py`, `disciplinas.py`, `requisitos.py`, `turmas.py`, `historico.py` + `registros.py` (Value Objects imutáveis
    com `linha`) + registro `IMPORTADORES` em `__init__.py`.
- **Nomes de colunas formalizados** em `ARQUITETURA.md §5` (iguais aos da 1B, então os `examples/` continuam válidos).
- 233 testes passando: 118 anteriores + 115 novos (`test_importers_leitor/horarios/arquivos/exemplos.py`). Os 4 CSVs de
  `examples/` passam com **0 erros e 0 avisos** (1 curso, 49 disciplinas, 46 requisitos, 61 turmas). Verificação por mutação:
  4 mutações em pontos críticos (descarte de linha com erro, BOM, `tipo` obrigatório, fim == início), todas derrubadas.
- Verificação da Etapa 2 pendente no arquivo anterior: a suíte completa **foi rodada** no início desta etapa
  (118 verdes), então o aviso da Etapa 2 está resolvido.

### Decisões/limites da 3A (para quem continuar) — REVISAR

- **`tipo` da disciplina e `codigo_turma` vazios são ERRO** (não há padrão). Motivo: regra "nunca inventar"; `tipo` muda o
  cálculo de progresso. Se preferir ser mais permissivo (ex.: `T1` por padrão), é mudar `obrigatorias` no importador.
- **`codigo_turma` virou obrigatório** no `turmas.csv` (na 1B já vinha sempre preenchido).
- Código de disciplina: espaços internos colapsados, **caixa preservada**. A **3B deve comparar com
  `leitor_csv.normalizar`** (casefold/sem acento) ao cruzar arquivos, senão `inf110` ≠ `INF110`.
- Erro em um encontro descarta a **turma inteira** (grade parcial seria falsa). Turma sem `horarios` = aviso, é mantida.
- `local` do encontro existe no modelo, mas **não** no formato CSV (não foi pedido); entra depois se necessário.
- Linhas rejeitadas já na leitura (colunas a mais) contam em `linhas_lidas` (a prévia da 3C mostrará "N lidas, M válidas").
- `curso.csv` com mais de 1 linha: mantém a primeira e gera **erro** (ambíguo).
- **Fora da 3A, de propósito (é a 3B):** duplicatas (no arquivo e no banco), referências entre arquivos (requisito/turma/
  histórico → disciplina inexistente), ciclos de pré-requisito, requisito em período posterior, encontros sobrepostos
  na mesma turma, razão créditos/carga horária, nota > 10 (escala), grupo OR com um único membro.
- Não existe `examples/.../historico.csv` (o seed legado não tinha histórico válido); a 3C pode criar um modelo.
- `CsvImporter` ficou em `importador.py` (não em `base.py`, como dizia o plano) para evitar import circular com o leitor.

## Etapa 3B — o que foi feito

- `planner/domain/ciclos.py`: `componentes_ciclicos` (Tarjan iterativo, só stdlib) — regra pura reaproveitada pelo importador.
- `planner/importers/validacao/` (só dados simples; sem Flask/SQLAlchemy/repositories, vigiado por teste que agora varre subpastas):
  - `estado.py`: `EstadoExistente` (retrato do curso no banco). `contexto.py`: `ContextoValidacao` (trabalha numa cópia; leituras da 3A não mudam).
  - Pipeline em cadeia (`pipeline.gerar_previa`): `duplicatas` → `referencial` → `semantico` → `previa`. Cada estágio é uma classe `Estagio`.
  - `duplicatas.py`: chave repetida no arquivo; idêntica = AVISO (ignorada), valores diferentes = ERRO (mantém a 1ª). Histórico repetido só avisa.
  - `referencial.py`: catálogo = banco + `disciplinas.csv`; requisito/turma/histórico para disciplina inexistente = ERRO (descarta a linha).
    Códigos comparados com `normalizar` e **reescritos no código canônico** (`inf110` → `INF110`). Impede requisito para outro curso.
  - `semantico.py`: regras em `REGRAS` (uma função cada): ciclo de pré-requisito (ERRO; via grupo OR = AVISO), encontros sobrepostos na turma (ERRO, descarta a turma),
    requisito em período igual/posterior, grupo OR com membro único, razão créditos/CH fora de 10–20 h/crédito, período > duração do curso,
    mudança de `tipo`, notas > 10 (um aviso por arquivo). Avaliam o estado FINAL (banco + arquivo).
  - `previa.py`: `ImportPreview` (contadores novo/atualizar/inalterado/erros/avisos, itens por linha com `mudancas` antes→depois, `mantidos_no_banco`,
    `pode_confirmar`, `para_dict()` JSON). `registros` = o que a 3C gravará. Determinística (issues ordenadas; ordem dos arquivos irrelevante).
- `planner/services/previa_importacao.py`: `PreviaImportacaoService.gerar(arquivos, curso_id=None, dono_id=None)` lê os CSVs, carrega o estado pelos
  repositories (somente leitura, consultas fixas) e roda o pipeline. Arquivo com nome desconhecido vira ERRO na prévia (não exceção).
- 293 testes passando: 233 anteriores + 60 novos (`test_domain_ciclos`, `test_importers_validacao`, `test_previa_servico`). Exemplo de CC: 0 erros e 0 avisos;
  importado (com stand-in de commit nos testes) e reimportado → 2ª vez tudo "inalterado". Mutação: 4 mutações derrubadas.

### Decisões/limites da 3B (para quem continuar) — REVISAR

- **Upsert**: chaves = curso→nome; disciplina→código; requisito→(disciplina, requisito, tipo); turma→(disciplina, período, código). **Célula vazia nunca apaga
  valor conhecido** do banco e **o que está só no banco é mantido** (a importação não remove nada; a prévia mostra `mantidos_no_banco`).
- **`pode_confirmar` = sem nenhum ERRO e algo a gravar** (tudo-ou-nada). Linhas com erro são descartadas na prévia, mas a 3C não deve gravar "o resto" quando há erro.
  Se preferir importação parcial, é mudar essa propriedade.
- Histórico: sem chave natural e sem usuário (só na 5A) → toda linha válida é "novo"; nenhuma checagem contra o banco.
- Ciclo por requisitos obrigatórios descarta TODAS as linhas do arquivo que o formam (não escolhe qual quebrar). Ciclo só no banco não é reportado.
- Correquisito mútuo (A co B, B co A) é aceito. Pré-requisito no MESMO período ou posterior = aviso (não erro).
- Faixa 10–20 h/crédito e "nota > 10" são constantes em `semantico.py` (convenção de 15 h/crédito; escala é do curso).
- `curso.csv` com nome diferente do curso alvo (`curso_id` dado) aparece como renomeação (`atualizar`).
- Se `disciplinas.csv` teve erro, a mensagem de referência quebrada avisa que a disciplina pode ter sido descartada.

## Etapa 3C — o que foi feito

- `planner/services/importacao.py`: `ImportacaoService.confirmar(arquivos, curso_id=None, dono_id=None, visibilidade=None)` → `RelatorioImportacao`.
  Refaz a prévia, exige `pode_confirmar` (senão `AppError` 422 com a prévia em `detalhes`), grava **numa transação** (rollback em qualquer exceção),
  na ordem curso → disciplinas → requisitos → turmas/encontros, e só toca o que a prévia marcou `novo`/`atualizar`. Sem `commit` nos repositories.
- `planner/api/importacao.py`: `POST /api/importacao/validar`, `POST /api/importacao/confirmar` (multipart; 201 se criou o curso),
  `GET /api/importacao/modelos[/<arquivo>]`, `GET /api/importacao/prompt-ia`, `GET /importar` (tela). `MAX_CONTENT_LENGTH` = 5 MB.
- `planner/importers/modelos.py`: modelos CSV (cabeçalho do `Esquema` + 1 linha de exemplo) e `gerar_prompt_ia()` (colunas vêm dos esquemas; não divergem).
- `planner/templates/importacao.html`: tela autônoma (upload → prévia com contadores, problemas e tabela por linha → Confirmar/Cancelar; download dos modelos; copiar prompt).
  O `index.html` original **não foi tocado** (ainda nem é servido; a 4A o modulariza).
- `docs/IMPORTACAO.md`: guia do usuário (formato, o que é erro/aviso, regra do upsert, API, uso de IA).
- 319 testes passando: 293 anteriores + 26 novos (`test_importacao_commit`, `test_api_importacao`). Exemplo de CC importado ponta a ponta pela API (201: 1 curso, 49 disciplinas,
  46 requisitos, 61 turmas); repetir = 422 "Nada a importar"; falha simulada no meio = rollback total. Mutação: 7 mutações (3A–3C) derrubadas.

### 🛑 Para você validar (marco)

1. `flask --app planner run --debug`, abrir `/importar`, enviar os 4 CSVs de `examples/ciencia-da-computacao/` e conferir prévia → confirmar. (Requer `flask db upgrade` antes, se usar o SQLite de dev.)
2. Enviar de novo (deve dizer "nada a importar"); alterar uma célula e ver "a atualizar".
3. Testar um CSV com erro (código inexistente em requisitos) e ver o bloqueio.
4. Usar o prompt de IA com o PPC de um curso real e revisar a prévia.
5. Decisões a confirmar: importação **tudo-ou-nada** (erro bloqueia); curso criado **privado** por padrão; célula vazia não apaga; nada é removido. (Histórico: decidido que sai da importação — ver 3D.)

### Decisões/limites da 3C (para quem continuar)

- Sem autenticação: `dono_id` é sempre `None` (curso sem dono) até a 5A; curso de mesmo nome é localizado entre os sem dono.
- Nenhuma rota lista/escolhe cursos ainda (onboarding é a 4A); a tela de importação só cria/atualiza.
- Atualizar encontros de uma turma **substitui** todos os encontros dela (quando o arquivo traz horários); sem horários no arquivo, mantém os do banco.
- Não há remoção por CSV; para apagar algo, só por serviço futuro.
- **Windows**: `tools/export_legacy_seed.py` falhava ao apagar a pasta temporária (`WinError 32`, 10 testes em erro no PowerShell do usuário); corrigido com `ignore_cleanup_errors=True` + `try/finally` + `gc.collect()`. Rodar `pytest` no Windows é parte da verificação.
- A tela usa `fetch` sem CSRF (API sem sessão por enquanto); revisar na 5A/6.

## Etapa 3D — o que foi feito

- **Histórico fora da importação.** Removidos `importers/historico.py`, `TentativaCsv`, a regra `notas_fora_da_escala_10`, o aviso de histórico repetido,
  `ARQUITETURA`/modelos/prompt/tela do histórico, `ARQUIVO_IGNORADO` e `ignorados` do relatório. `IMPORTADORES` = 4 arquivos. Enviar `historico.csv` gera um ERRO
  orientado na prévia ("o histórico será informado dentro do app"). Modelo `Historico` e repository continuam no banco (5B).
- **Coluna `local` (sala) em `turmas.csv`** (opcional; alias `sala`): vale para todos os encontros da turma e é gravada em `Encontro.local`.
  Entra no diff da prévia (`TurmaExistente.local`); se só a sala mudar, atualiza os encontros já gravados.
- **Prompt de IA por fonte** (`importers/modelos.py`: `FONTES`, `gerar_prompt_ia(fonte)`, `listar_fontes()`): `matriz` (curso/disciplinas/requisitos),
  `horarios` (só `turmas.csv`, uma linha por turma, `local`), `web` (pede a URL de cada dado duvidoso). `GET /api/importacao/prompt-ia?fonte=...` (400 se inválida).
- **Tela `/importar` em 5 passos** (stepper): fontes → prepare (abas por fonte, copiar, modelos) → envie → confira (resumo em frase, contadores em linguagem comum,
  problemas **agrupados** com "como resolver", detalhe linha a linha) → sucesso. Sem jargão; identidade visual do `index.html` mantida; sem regra de negócio no front.
- `docs/IMPORTACAO.md` (guia por fonte + como combinar) e `docs/ARQUITETURA.md §5` atualizados.
- Testes ajustados (histórico removido; novos: `local`, prompts por fonte, histórico → erro orientado).

### ⚠️ Verificação desta etapa (ler antes de confiar)

O ambiente da 3D **não tinha SQLAlchemy/Flask-SQLAlchemy nem rede**. Portanto:
- Rodaram e passaram (stub do SQLAlchemy, `--noconftest`): 203 testes sem banco (`test_importers_*`, `test_domain_*`) e os de prompt/modelos.
- **NÃO rodaram**: os que usam `app`/`client` (`test_importacao_commit`, parte de `test_api_importacao`, `test_previa_servico`, repositories, schema, migração).
  **Rode `pytest` completo (também no Windows) e traga a saída se algo falhar.** Maior risco: `test_importacao_commit`
  (`test_historico_nao_faz_parte_da_importacao`, gravação de `local`) e `test_previa_servico`.
- A tela foi testada num navegador real (Playwright) contra um servidor Flask que reusa o pipeline de validação, com os CSVs reais do curso:
  fluxo completo, bloqueio por erro, zero erros de JS. A gravação real no banco não foi exercitada.

### Decisões/limites da 3D (para quem continuar)

- `local` é **um por turma** (não por encontro). Se um quadro tiver salas diferentes por dia, vira coluna por encontro no futuro.
- Os "como resolver" da tela são sugestões por padrão de texto; o texto do problema vem do servidor.
- A tela avisa que escolher curso no planejador chega na próxima etapa: `index.html` ainda não é servido (4A).
- Os CSVs reais do usuário (CC/UFV, 111 disciplinas, 84 requisitos, 153 turmas; 0 erros, 13 avisos "turma sem horários") **não** foram para `examples/`
  (o teste de drift do exportador do legado exige que `examples/ciencia-da-computacao` não mude).

## Etapa 4A — o que foi feito

- **Frontend modular (refatoração pura, verificada byte a byte).** O `index.html` de 1427 linhas virou um *shell* (HTML + `<script src>`).
  CSS → `planner/static/css/app.css`; JS → `planner/static/js/` em 9 módulos: `core.js` (estado, API, toast, modal, navegação, helpers),
  `page_dashboard|planner|fluxograma|calendario|historico|disciplinas.js`, `disc_detalhe.js`, `main.js`. São scripts clássicos carregados em ordem
  (compartilham o escopo global; os `onclick` do HTML dependem disso). Concatenar os módulos na ordem reproduziu o `<style>`/`<script>` originais idênticos
  (antes das adaptações abaixo).
- **Backend de cursos:** `services/cursos.py` (`CursoService.listar/obter/catalogo`), `api/cursos.py`, `CursoRepository.contagens` (2 consultas agrupadas, sem N+1).
  `GET /api/cursos`, `GET /api/cursos/<id>`, `GET /api/cursos/<id>/disciplinas` (curso + disciplinas + requisitos já resolvidos por código/nome; campos desconhecidos = `null`).
  Páginas: `GET /` (onboarding, `inicio.html`) e `GET /curso/<id>` (planejador; curso inexistente/inacessível redireciona para `/`).
- **Onboarding:** `/` sem curso explica em 3 passos e leva a `/importar`; com cursos, mostra cartões (nome, instituição, matriz, nº de disciplinas/turmas) → "Abrir planejador".
  A tela de sucesso da importação agora tem **"Abrir o planejador"** (`/curso/<curso_id>`) e a `/importar` tem link "← Início". Barra lateral mostra o curso ativo + "Trocar de curso".
- **Sem constantes de curso no JS:** o `CURSO_ID` vem de `<body data-curso-id>`; `loadData()` busca `/api/cursos/<id>/disciplinas`. `adaptarDisciplina()` é o único ponto que traduz
  nomes do banco (`periodo_sugerido`, `requisitos`) para os que as telas herdadas esperam (`periodo`, `prerequisitos`). Teste garante que o `core.js` não chama mais a API do legado.
- **`NULL` = desconhecido também na tela:** `valorOu()` mostra "–" (nunca `null`/0); `credStr`/`periodStr` null-safe; disciplinas sem período vão para a coluna
  **"Sem período sugerido"** do fluxograma (no curso real são 75 das 111, as optativas e INF496).
- **Telas ainda sem backend ficam explícitas, não quebradas:** `RECURSOS` e `PAGINAS_PENDENTES` (em `core.js`). Dashboard, Planejamento, Calendário e Histórico mostram
  "Esta tela chega na Etapa 4B/5B" (itens esmaecidos na barra lateral). Ficam **ativos**: Fluxograma (página inicial) e Disciplinas (somente leitura; o botão vira
  "Atualizar por importação"; Editar/Del e "Adicionar ao histórico" ficam ocultos). O fluxograma não mostra status (concluída/disponível/bloqueada) sem histórico,
  para não afirmar o que não se sabe (a primeira versão mostrava tudo como "Disponível", inclusive disciplinas com pré-requisito; corrigido).
- Testes novos em `tests/test_api_cursos.py` (13): app sem curso, lista com contadores, privado alheio não lista/abre (404 igual ao inexistente), público com dono lista,
  catálogo com requisitos, `null` ≠ 0, 404 JSON, redirect de `/curso/<id>` inexistente, assets servidos, módulos JS no shell na ordem certa, sem curso fixo, sem API legada.

### ⚠️ Verificação desta etapa (ler antes de confiar)

O ambiente da 4A **não tinha SQLAlchemy/Flask-SQLAlchemy, pytest nem rede**. Portanto:
- **Rodaram e passaram:** `py_compile` de todo Python novo; `node --check` de todos os módulos JS; 3 checagens do shell (ordem dos módulos, sem curso fixo, sem API legada) feitas à mão.
- **Testado em navegador real (Playwright/Chromium)**, com um servidor Flask que usa os **templates e estáticos reais** e uma API falsa montada dos CSVs do usuário (CC/UFV: 111 disciplinas, 153 turmas):
  app sem curso → tela de boas-vindas e `/curso/1` volta a `/`; com curso → cartão (111 disciplinas · 153 turmas) → planejador; 9 colunas no fluxograma (8 períodos + "Sem período sugerido");
  INF496 aparece sem "null/NaN"; sem badges de status; 4 páginas pendentes mostram o aviso; "Trocar de curso" volta ao início; **0 erros de JS**.
- **NÃO rodaram:** `CursoService`, `CursoRepository.contagens`, as rotas `/api/cursos*` reais e os 13 testes de `test_api_cursos.py` (usam banco).
  **Rode `pytest` completo (também no Windows) e traga a saída se algo falhar.** Maiores riscos: `contagens` (`dict(execute(...).all())`),
  o teste `test_campos_desconhecidos_saem_null_e_nunca_zero` (importa só `curso.csv` + `disciplinas.csv`; se a prévia exigir outro arquivo, ajustar o teste) e a rota `""` do Blueprint `/api/cursos`.

### Correção pós-entrega

- `tests/test_importacao_commit.py` (da 3D) tinha quebras de linha reais dentro de um literal de string em `test_historico_nao_faz_parte_da_importacao`
  (`SyntaxError` na coleta do `pytest`; o ambiente da 3D não rodou esses testes). Trocadas por `\n`. Verificado: `ast.parse` de todos os `.py` do projeto sem erro.

- **Resultado do `pytest` no Windows do usuário (Python 3.14): 309 passaram, 10 erros** — todos em `tests/test_export_legacy_seed.py`
  (`WinError 32`: `seed.db` travado ao apagar a pasta temporária). Isso confirma, rodando de verdade, os 13 testes novos da 4A e os da 3D que nunca tinham rodado (`test_importacao_commit`, `test_previa_servico`, repositories).
  Causa: o legado usa `with get_db() as conn`, que confirma mas não fecha a conexão. **A correção descrita na 3C (`ignore_cleanup_errors` + `try/finally` + `gc.collect()`) não estava no código entregue** (regrediu);
  reaplicada em `tools/export_legacy_seed.py:ler_seed_legado()` (+ `conexao.close()` no `finally`). Verificado só no Linux (função devolve 49/95/46 linhas e CSVs idênticos aos de `examples/`);
  **a eliminação do erro no Windows precisa ser confirmada rodando o `pytest` lá.** Se ainda falhar, o próximo passo é trocar a pasta temporária por `tmp_path` do pytest ou abrir o legado em memória.

### 🛑 Para você validar (marco)

1. `pytest` completo.
2. `flask --app planner run --debug` → abrir `/` com banco vazio (deve guiar até `/importar`), importar os 4 CSVs, clicar em **Abrir o planejador** e navegar Fluxograma/Disciplinas.
3. Decisões a confirmar abaixo.

### Decisões/limites da 4A (para quem continuar)

- **Cursos sem dono aparecem para todos até a 5A.** A importação cria curso privado sem dono; sem isso ele sumiria do onboarding. `listar_acessiveis(incluir_sem_dono=True)` e
  `CursoService._curso_acessivel` têm essa regra, marcada para sair quando houver login. **Não publicar (Etapa 6) sem a 5A**: hoje qualquer visitante veria os cursos.
- Catálogo é **somente leitura** na UI: edição vem só da importação (`RECURSOS.editarCatalogo = false`). Os modais herdados de criar/editar/excluir continuam em `page_disciplinas.js`
  (código morto, ainda apontando para a API do legado) — reescrever ou apagar quando decidirmos se haverá edição na UI.
- Horários: `adaptarDisciplina` devolve `horarios: []`; vêm das turmas na 4B. Por isso a coluna "Horários" da tabela e o modal aparecem vazios.
- Cores: se a disciplina não tem `cor`, a tela usa uma cor por tipo (só exibição, não é gravada).
- **Risco para 5A/6:** as telas herdadas montam HTML com `innerHTML` usando nomes/códigos vindos do CSV (XSS armazenado se cursos públicos de terceiros). `inicio.html` já usa `textContent`;
  as páginas herdadas precisam ser escapadas antes de qualquer curso ser compartilhado.
- Atualizar um curso existente depende de o nome em `curso.csv` ser igual ao do curso (comportamento da 3C).
- Achados dos CSVs reais do usuário (não alterados): INF496 e INF497 têm o mesmo nome ("Projeto Final de Curso"); INF496 sem créditos/carga/período/requisitos e INF497 com 0/0;
  13 turmas sem horário (a maioria `P1`); docentes "André/Júlio" e "André/Salles" num só campo.

## Etapa 4B — o que foi feito

- **Domínio (puro):** `domain/grade.py` (`derivar_grade`: dias = `dias_letivos` ∪ dias com encontro; horas pelo menor início/maior fim; padrão visual SEG–SEX 07–22 só se não houver dado) e
  `domain/analise.py` (`analisar_plano`: carga + requisitos + conflitos por turma, semestre a semestre; itens que não batem com o catálogo vão para `invalidos`, não derrubam a análise).
- **Serviços/rotas:** `services/oferta.py` + `GET /api/cursos/<id>/turmas[?periodo=AAAA/N]` (turmas, encontros, períodos, grade); `services/analise_plano.py` + `services/analise_json.py` (leitura/serialização, sem banco)
  + `POST /api/cursos/<id>/plano/analisar` (sem estado, não grava nada; 400 em formato inválido). `api/oferta.py` registrado em `api/__init__.py`.
- **Frontend:** `plano_local.js` (planos no `localStorage`, uma chave por curso), `page_planner.js` e `page_calendario.js` reescritos. Planejador: período letivo por semestre, escolha de turma por disciplina,
  selos "Conflito / Conflito possível / Sem turma compatível / Requisito pendente", rodapé `créditos / limite do curso`, modal de validação. Calendário: encontros da turma escolhida, dias e horas vindos de `S.grade`,
  eventos que se sobrepõem dividem a coluna, lista "fora da grade" (sem turma/período). Detalhe da disciplina lista as turmas ofertadas; coluna "Turmas" na base de disciplinas. Planejamento e Calendário saíram de `PAGINAS_PENDENTES` e do menu esmaecido.
  Textos do CSV nas telas novas passam por `esc()` (XSS).
- Testes novos: `test_domain_grade_analise.py`, `test_analise_json.py`, `test_api_oferta.py`, + ajustes em `test_api_cursos.py` (menu, sem API do legado nos módulos migrados).

### ⚠️ Verificação desta etapa (ler antes de confiar)

O ambiente **não tinha SQLAlchemy, pytest nem rede**. Por pedido do usuário, **o `pytest` completo não foi rodado**.
- Rodaram (executor mínimo, fora do projeto): 92 testes de domínio/JSON, mutações derrubadas. Navegador real (Playwright) contra servidor falso com templates/estáticos/domínio reais e os CSVs do curso: criar plano, período, arrastar, escolher turmas, conflito, validar, persistir ao recarregar, calendário, detalhe — 0 erros de JS.
- **NÃO rodaram:** `test_api_oferta.py` (usa banco) e as alterações de `test_api_cursos.py`. **Rode `pytest` completo (também no Windows)** e traga a saída se algo falhar. A confirmação de que os 10 erros `WinError 32` do exportador sumiram (4A) também segue pendente.

### Decisões/limites da 4B (para quem continuar) — REVISAR

- **Plano mora no navegador** até a 5B; o servidor só o julga. Na 5B troca-se `PlanoLocal` por persistência no servidor (a rota de análise continua válida).
- Semestre **sem período letivo** = oferta desconhecida: nenhuma turma é oferecida e nenhum horário é julgado. Trocar o período limpa as turmas escolhidas.
- Sem histórico (5B): a paleta não afirma "elegível/bloqueada"; requisitos contam só semestres anteriores do próprio plano.
- No calendário, a disciplina inteira é marcada em vermelho quando há conflito **confirmado** (como no legado), mesmo nos dias em que não colide.
- Conflitos continuam par a par (limite da Etapa 2). `local` do encontro vem na API mas a grade só o exibe se existir.

## Etapa 5A — o que foi feito

- **Provedor/fluxo (decisão da §6):** login **sem senha, por link mágico enviado ao e-mail**; sem Supabase Auth nem Google (ver "Decisões"). Fluxo:
  `POST /api/auth/link` → e-mail com link → página `/entrar/confirmar?token=…` (botão) → `POST /api/auth/entrar` abre a sessão → `POST /api/auth/sair`; `GET /api/auth/eu`.
  Telas `entrar.html` e `entrar_confirmar.html` (+ `static/css/telas_simples.css`).
- **Token** (`services/auth/links.py`): assinado (`itsdangerous`, HMAC da `SECRET_KEY`, sal próprio), validade 15 min, **uso único sem tabela de tokens**: leva a `usuario.versao_login` de quando foi
  emitido; cada login incrementa o contador (UPDATE condicional, `UsuarioRepository.consumir_versao_de_login`), então o link usado — e os emitidos antes — deixam de valer. Nova coluna `usuario.versao_login`
  (migração `a3c91e7b5d20`, escrita à mão).
- **Envio = Strategy** (`services/auth/envio.py`): `EnviadorConsole` (log; dev/testes) e `EnviadorSMTP` (stdlib; produção). Fábrica `criar_autenticacao(config)`; o serviço fica em `app.extensions["autenticacao"]`.
- **Sessão** (`api/sessao.py`): cookie assinado do Flask (`HttpOnly`, `SameSite=Lax`, `Secure` em produção, 30 dias). `before_request` carrega `g.usuario`; decoradores `login_obrigatorio` (401 JSON) e `login_obrigatorio_pagina` (302 → `/entrar?proximo=…`).
- **CSRF** (`api/origem.py`): todo método que altera dados precisa vir do próprio site (`Sec-Fetch-Site`/`Origin`); 403 caso contrário. Sem token no front: nenhum `fetch` existente precisou mudar.
- **Domínio** (`domain/identidade.py`, puro): `normalizar_email`, `email_valido`, `caminho_interno_seguro` (impede open redirect; o destino pós-login viaja dentro do token assinado).
- **Posse de curso:** removida a regra "curso sem dono aparece para todos" (4A) em `CursoRepository.listar_acessiveis` e `CursoService._curso_acessivel`. Importação exige login, o curso nasce do usuário e **só o dono atualiza**
  (curso alheio, mesmo público, dá o mesmo 404 de inexistente — na prévia e na confirmação). `/importar` exige login; `modelos` e `prompt-ia` seguem públicos. Leitura/oferta/análise passam o usuário atual.
- **Cursos órfãos (criados antes do login):** invisíveis para todos até alguém reivindicá-los: `flask --app planner reivindicar-cursos SEU@EMAIL` (`services/posse.py`, `cli.py`).
- **Telas:** `inicio.html` mostra conta/Sair e adapta o onboarding a visitante × logado; `importacao.html` volta ao login em 401; `/curso/<id>` sem acesso leva ao login (visitante) ou ao início (logado), resposta igual exista o curso ou não.
- **Config** (`config.py`): `APP_URL_BASE`, `AUTH_ENVIO`, `SMTP_*`, `AUTH_LINK_VALIDADE_MIN`, cookies; `AUTH_DEVOLVER_LINK=True` só em dev/testes (a API devolve `link_dev`; a tela o mostra no lugar do e-mail).
  `ProductionConfig.validate()` agora exige `APP_URL_BASE` https, `AUTH_ENVIO=smtp`, `SMTP_HOST` e `SMTP_REMETENTE`.
- **Testes novos:** `test_domain_identidade`, `test_auth_links_envio`, `test_origem`, `test_api_auth`, `test_acesso_e_posse`, `test_config_producao`; fixtures `usuario`/`client_logado` em `conftest.py`.
  `test_api_cursos`, `test_api_oferta` e `test_api_importacao` ganharam um `client` logado (override de fixture no módulo). Nenhum teste existente foi apagado.

### ⚠️ Verificação desta etapa (ler antes de confiar)

O ambiente **não tinha SQLAlchemy, pytest nem rede**; por pedido do usuário o `pytest` completo **não foi rodado** (os testes foram escritos para ele rodar).
- Rodaram (script avulso): `domain/identidade` (e-mails e caminhos válidos/inválidos), `api/origem.origem_permitida`, `EmissorDeLinks` (ida e volta, adulterado, chave errada, expirado); `py_compile` de todo o Python novo/alterado.
- **NÃO rodaram:** tudo que usa banco ou Flask (`test_api_auth`, `test_acesso_e_posse`, ajustes nos 3 arquivos de API, `test_migracao` com a nova migração) e as telas HTML no navegador.
  **Rode `pytest` completo (também no Windows).** Maiores riscos: (1) a migração escrita à mão (`test_migracao_nao_diverge_dos_modelos` — `server_default="0"` vs. modelo); (2) `consumir_versao_de_login`
  (`UPDATE` ORM com `synchronize_session="fetch"`, `rowcount`); (3) `test_comando_de_linha` (`FlaskCliRunner`); (4) `test_link_usa_a_url_da_configuracao…` (cabeçalho `Host` no test client).

### 🛑 Para você validar (marco)

1. `pytest` completo; depois `flask --app planner db upgrade`.
2. `flask --app planner run --debug` → `/` (visitante) → **Entrar** → digitar e-mail → a tela mostra o link de desenvolvimento → abrir → **Entrar no Planejador** → importar o curso → listar → **Sair**.
3. Cursos que você já tinha no SQLite de dev: `flask --app planner reivindicar-cursos SEU@EMAIL` (senão ficam invisíveis).
4. Decisões a confirmar abaixo.

### Decisões/limites da 5A (para quem continuar) — REVISAR

- **Magic link próprio em vez de Supabase Auth/Google:** não depende de provedor, é testável e o Postgres continua podendo ser Supabase/Neon. Google/OIDC entra como nova forma de login (a sessão e `usuario_atual` não mudam).
- **Sem limite de pedidos de link** (alguém poderia mandar e-mails em massa a terceiros). Falta throttle: fica para a Etapa 6 (limite na borda/Vercel ou tabela de contagem), antes de publicar.
- **Em produção o e-mail é obrigatório** (SMTP). Provedores como Resend/SES/Brevo têm SMTP; se preferir API HTTP, é uma nova classe `EnviadorDeLink`.
- **O link usa `APP_URL_BASE`**, nunca o `Host` da requisição (evita sequestro por cabeçalho forjado). Em dev cai no host da requisição.
- Quem tem o link pode entrar (como em qualquer link mágico); a segurança depende da caixa de e-mail. Validade de 15 min, uso único.
- A proteção CSRF é por origem + `SameSite=Lax`; clientes que não mandam `Origin`/`Sec-Fetch-Site` passam (não carregam cookie de ninguém). Se um dia houver navegador muito antigo como público, avaliar token.
- `usuario.nome` continua vazio (nada o preenche ainda). Não há exclusão de conta nem "sair de todos os dispositivos" (poderia reaproveitar `versao_login`).
- Cursos públicos de terceiros agora só aparecem se `visibilidade=publico`; **não há tela/rota para publicar** (só o campo `visibilidade` na importação, na criação). Decidir na 5B/6 se entra na UI.
- **XSS armazenado (aviso da 4A) continua aberto** nas páginas herdadas (`innerHTML` com textos de CSV): resolver antes de qualquer curso ser público de verdade.
- O plano continua no `localStorage` (4B); a 5B troca por persistência por usuário.
- Os 4 CSVs reais enviados no chat (CC/UFV) **não** foram usados nesta etapa (não são necessários para a autenticação).

## Etapa 5B-1 — o que foi feito (login pelo Supabase)

Motivo: não há servidor para enviar e-mail; o Supabase Auth faz o envio e a confirmação.
- **Fluxo:** `/entrar` (navegador) → Supabase (`/auth/v1/otp`: e-mail com link **e** código) → volta em `/entrar#access_token=…` (ou código em `/auth/v1/verify`)
  → `POST /api/auth/entrar {access_token, proximo}` → servidor confere o token (`VerificadorSupabase`: `GET /auth/v1/user`, exige e-mail confirmado), cria a conta, abre o cookie de sessão. Sem biblioteca JS, sem CDN.
- **Código:** `services/auth/verificador.py` (Strategy: `VerificadorSupabase`, `VerificadorDeDesenvolvimento` = token `dev:<email>`), `autenticacao.py` simplificado, `fabrica.py` (`AUTH_PROVEDOR`), `api/auth.py`
  (rotas: `entrar`, `sair`, `eu`, página). `api/sessao.py`, CSRF e posse de curso **não mudaram**. `inicio.html` repassa um token que caia na raiz para `/entrar`.
- **Removido:** link mágico próprio (`links.py`, `envio.py`, SMTP, `APP_URL_BASE`, `/api/auth/link`, `/entrar/confirmar`, `entrar_confirmar.html`), `usuario.versao_login` e `consumir_versao_de_login`.
  Migração nova `b7d4e2a19c63` (drop da coluna, escrita à mão).
- **Config:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `AUTH_PROVEDOR` (`supabase` | `dev`; sem chaves, dev usa `dev`; testes usam `dev`; produção exige `supabase`). `.env.example` criado.
- **Testes:** `test_auth_verificador.py` (novo, sem banco/rede), `test_config_producao.py` e `test_api_auth.py` reescritos; `test_auth_links_envio.py` removido. Nenhum outro teste mudou.

### ⚠️ Verificação desta etapa (ler antes de confiar)
Ambiente sem SQLAlchemy e sem rede; por pedido do usuário o `pytest` completo **não foi rodado**.
- Rodaram (com stubs, fora do projeto): 61 testes — `test_auth_verificador`, `test_config_producao`, `test_domain_identidade`. `py_compile` de todo o Python alterado.
- **NÃO rodaram:** `test_api_auth.py` (HTTP + banco), `test_migracao.py` com a migração nova (maior risco: `test_migracao_nao_diverge_dos_modelos`), e a tela `entrar.html` no navegador / contra um Supabase real.

### 🛑 Para você validar
1. `pytest` completo (Windows também). 2. `flask --app planner db upgrade`. 3. Sem `.env`: `/entrar` aceita qualquer e-mail (provedor dev).
4. Com Supabase: criar projeto, preencher `.env`, cadastrar `http://127.0.0.1:5000/entrar` em Redirect URLs, e incluir `{{ .Token }}` no template de e-mail "Magic Link" (para o código). Testar link e código.

### Decisões/limites da 5B-1 — REVISAR
- Identidade = e-mail (sem `supabase_id`): se a pessoa trocar o e-mail no Supabase, vira outra conta.
- O token é conferido por chamada ao Supabase no login (1 por login). Se o Supabase cair, login responde 503 (quem já tem sessão não é afetado).
- Limite de pedidos de e-mail: do Supabase (a tela trata 429). O item "throttle" da 5A deixa de existir.
- Link de e-mail pode ser consumido por antivírus/leitores de e-mail; por isso a tela também aceita o código.
- Sem SRI/CDN: nenhuma biblioteca de terceiros é carregada na tela de entrada.
- Pendente (antes da Etapa 6): escape de HTML nas telas herdadas (XSS armazenado, ver 4A/5A).

## Etapa 5B-2 — o que foi feito

- **Domínio:** `domain/painel.py` (`montar_painel`: status por disciplina concluída/cursando/elegível/bloqueada + `reprovada_antes`, progresso, média de créditos por período, previsão de formatura);
  `previsao.normalizar_periodo` ("2024.1" → "2024/1"); `Progresso.creditos_validos/creditos_exigidos`. Previsão sem inventar: média do aluno → senão média do curso (créditos exigidos ÷ duração) → senão `None`;
  sem período no histórico não há "a partir de quando" (sem data).
- **Histórico:** `services/historico.py` + `historico_json.py`; rotas `GET/POST /api/cursos/<id>/historico`, `PUT/DELETE .../historico/<hid>`, `GET .../painel` (tudo exige login; tentativa alheia = 404).
- **Planos no servidor:** `services/planos.py` + `planos_json.py`; `GET/POST /api/cursos/<id>/planos`, `PUT/DELETE .../planos/<pid>`. O cliente edita e envia o plano INTEIRO; o servidor troca os semestres numa transação
  (`PlanoRepository.substituir_semestres`, com `flush` entre apagar e inserir por causa do UNIQUE de ordem). Valida: disciplina do curso, sem repetição no plano, turma da disciplina e do período do semestre (422). Máx. 20 planos por curso.
- **Análise com histórico:** `/plano/analisar` passa aprovadas/cursando do usuário ao domínio. `services/catalogo_dominio.py` concentra a conversão modelos → entidades.
- **Frontend:** `plano_local.js` → `plano_store.js` (fila de gravação, migração única do `localStorage` para a conta); fluxograma com status reais e dashboard/histórico ligados (editar/remover/N tentativas);
  `PAGINAS_PENDENTES`/`RECURSOS` removidos; `api()` nunca lança e leva ao login em 401; botão de excluir plano. `/curso/<id>` agora exige login. **Escape de HTML** nas telas herdadas;
  código morto de edição do catálogo (API do legado) removido de `page_disciplinas.js`.
- **Testes novos (escritos, NÃO executados por completo):** `test_domain_painel`, `test_json_historico_planos_painel`, `test_api_historico`, `test_api_planos` (isolamento entre usuários), + casos em `test_repositories` e `test_api_cursos`; fixtures `curso_pequeno`, `outro_usuario`, `client_outro` no `conftest`.

### ⚠️ Verificação desta etapa (ler antes de confiar)
Sem SQLAlchemy/rede e, a pedido do usuário, **o `pytest` não foi rodado**. Apenas os testes de domínio/JSON sem banco (`test_domain_painel`, `test_json_historico_planos_painel`, `test_domain_*`, `test_analise_json`) foram executados com um plugin que finge o SQLAlchemy: passaram (inclui a pureza do domínio).
`node --check` em todos os JS. **Não rodaram:** `test_api_historico`, `test_api_planos`, os casos novos de repositório, `test_api_cursos`, a tela no navegador. Rode `pytest` completo (Windows também).
Maiores riscos: `substituir_semestres` (ordem de DELETE/INSERT), `test_excluir_remove_plano...` (cascata), `contar_consultas` = 5 e 2, e o fluxo de migração do `localStorage` no navegador.

### 🛑 Para você validar
1. `pytest` completo. 2. `flask --app planner run --debug`, entrar, abrir um curso. 3. Histórico: adicionar aprovação → fluxograma/dashboard mudam; reprovar e aprovar de novo; editar/remover. 4. Planejador: criar plano, recarregar (persiste), abrir em outro navegador logado (aparece), excluir. 5. Se tinha plano da 4B no navegador, deve ser movido para a conta com aviso. 6. Segunda conta não vê nada da primeira.

### Decisões/limites da 5B-2 — REVISAR
- Gravação do plano é "última escrita vence" (duas abas editando o mesmo plano: a última grava por cima). Sem controle de versão.
- Nota aceita 0–100 (escala é do curso). Período do histórico é opcional; sem ele a tentativa não entra na média nem na previsão.
- Previsão assume o próximo período livre = último período do histórico + 1, não o calendário de hoje.
- Planejador exige login mesmo em curso público; cursos públicos de terceiros continuam sem tela para publicar.
- Disciplina já concluída aparece esmaecida na paleta, mas o servidor não rejeita planejá-la.
- Conflitos continuam par a par (limite da Etapa 2). O XSS armazenado das telas herdadas foi tratado com `esc()`; vale uma revisão antes da Etapa 6.

## Próximo passo (Etapa 6 — deploy 🛑)

Antes: `pytest` completo e validar a 5B-2. Depois: `vercel.json`, Postgres gerenciado, `psycopg2-binary`, variáveis de ambiente, remover `debug`, CI (GitHub Actions: pytest). Revisar o limite do plano por usuário e a gravação concorrente.

## Tarefas futuras
- **Melhorar a UI e a comunicabilidade da ferramenta. Nada explicativo: aprende-se só testando** (rótulos curtos, estados vazios acionáveis, feedback imediato; menos texto de ajuda).

## Como retomar (prompt para colar em chat novo)

```
Estou continuando o projeto "Planejador Acadêmico multi-curso". Anexei o zip
mais recente e docs/PROGRESSO.md. Leia docs/PROGRESSO.md, docs/PLANO_IMPLEMENTACAO.md
e docs/ARQUITETURA.md, e execute APENAS a etapa marcada como "Próxima".
Regras: código legível, padrões de projeto, comentários em português, não
reescrever o que funciona, testes verdes ao final, atualizar PROGRESSO.md,
entregar PROGRESSO.md avulso no chat além do zip.
```

## Regras de trabalho (valem para todas as etapas)

1. Uma sub-etapa por conversa/turno; ao terminar, rodar `pytest` e atualizar este arquivo.
2. Nunca inventar dados acadêmicos (créditos, horários, requisitos): vazio = desconhecido.
3. Regra de negócio só em `planner/domain/` (funções puras, sem SQL/HTTP).
4. SQL só em `planner/repositories/`. Rotas só em `planner/api/`.
5. Preservar identidade visual e UX do `index.html`; mudanças de frontend são cirúrgicas.


## Etapa 5B-3 — calendário livre (horários próprios)

Problema: o calendário só mostrava encontros de **turmas importadas**; sem quadro de horários (ou sem período letivo) ficava vazio e o aluno não podia organizar nada.

- **Modelo/migração:** `plano_item.encontros_livres` (JSON, NULL = nenhum) — migração `c5e8f1a2b704`. Excludente com `turma_id` (regra do serviço: 422 se vierem os dois).
- **Domínio:** `ItemPlano.encontros_livres`; na análise viram uma **turma própria já escolhida** (id negativo, `codigo_turma="própria"`), então a detecção de conflitos é a mesma de sempre (inclusive contra turmas do quadro). Funciona **sem período letivo e sem nenhuma turma no curso**.
- **JSON:** `ler_encontros_livres` / `encontros_para_json` em `analise_json.py` (dia SEG–DOM, `HH:MM`, início < fim, sem sobreposição na mesma disciplina, máx. 14). `serializar_plano` só inclui `encontros_livres` quando existe (contrato anterior intacto).
- **Frontend:** `horarios_proprios.js` (editor em modal); `plano_store.definirEncontros`; cartão do planejador ganha "🕐 Definir horários"; calendário: **clicar numa célula vazia** cria horário, evento próprio abre o editor, "Fora da grade" tem link "definir horários", grade se amplia para nunca esconder um horário próprio.
- Testes: `tests/test_horarios_proprios.py` (18 casos, rodados com stubs mínimos de flask/pytest fora do projeto). `node --check` em todos os JS.

### Decisões/limites da 5B-3 — REVISAR
- Turma **ou** horários próprios (escolher turma remove os próprios; salvar próprios remove a turma). Não dá para "ajustar um horário da turma".
- Clique no calendário só lista disciplinas **sem turma** do quadro (as com turma já têm horário).
- Horário próprio não tem `local` ainda.
- **Não rodei** `pytest` completo nem testei no navegador (ambiente sem Flask/SQLAlchemy). Rode `flask db upgrade` e `pytest`; `test_migracao_nao_diverge_dos_modelos` deve confirmar a migração.


## Etapa 6 — o que foi feito (arquivos; deploy real é com você)
- `api/index.py` (entrada WSGI, força `APP_ENV=production`), `vercel.json` (rewrite para a função), `psycopg2-binary` em `requirements.txt`,
  `ProductionConfig` com `NullPool` + `pool_pre_ping` (serverless), `.github/workflows/ci.yml` (pytest + `db upgrade` + `db check`), `docs/DEPLOY.md`,
  `iniciar.py` reescrito (o antigo apontava para o `app.py` legado), `tests/test_deploy_arquivos.py`.
- **Não testado:** nenhum deploy foi feito e o `pytest` completo não rodou. Falta: criar projeto Supabase/Vercel, `db upgrade` no Postgres, configurar variáveis e URLs do Supabase Auth.
- Pendente: limite de pedidos de login, concorrência na gravação do plano, revisão de XSS nas telas herdadas.

## Etapa 7 (parcial)
- `docs/DEPLOY.md` reescrito (Supabase: pooler de transação p/ o app e de sessão p/ migrações; Vercel: variáveis; URLs de redirect `/entrar`). `README.md` com descrição e link. Falta revisar `IMPORTACAO.md` e executar o deploy (com o usuário).


## Tarefa futura — UI/comunicabilidade (1ª passada)
- Início: estado vazio sem tutorial (título + 1 botão "+ Trazer meu curso"); removidos subtítulo e dicas; cartão "Abrir"; "Seus cursos".
- Dashboard/Fluxograma: aviso de histórico vazio reduzido a "Histórico vazio." + botão "+ Informar histórico".
- Planejador: sem plano → só "+ Criar plano". Calendário: "Escolha um semestre"; semestre vazio → botão "+ Adicionar disciplinas". Histórico vazio → "+ Adicionar disciplina".
- Login: só Google (formulário de e-mail escondido; ver `entrar.html`); espera visível entre pedidos de e-mail.
- Desempenho: `loadData` carrega tudo em paralelo e uma vez (não refaz a cada aba); CSS/JS com cache de 10 min em produção.
- **Passada visual (CSS/JS):** `app.css` (bloco "UX/UI" no fim): contraste do texto secundário, piso de 11px, foco de teclado visível, esqueleto de carregamento, toasts com ícone/clique para fechar, janela fecha com Esc e foca o 1º campo, menu acessível por teclado, **layout de celular** (menu vira barra inferior), `prefers-reduced-motion`. Planejador sem plano: barra vazia + "Nenhum plano"/"+ Criar plano".
- Verificação: `pytest` = 603 passaram (10 erros pré-existentes em `test_export_legacy_seed`/legacy, ambiente sem `flask_cors`); app subido localmente com o curso exemplo e capturas de tela de todas as telas (desktop e 390px) sem erros de JS.
- Falta revisar `importacao.html` (353 linhas, ainda com muito texto) e o modal de histórico/planejador (feedback imediato).


## Rebranding — Trilha
- **Nome/símbolo:** "Trilha" (antes "Planejador Acadêmico"); símbolo = linha de metrô com início vazado e terminal amarelo (`static/img/trilha.svg`, também favicon). Conceito: o curso é uma linha; períodos são estações; a formatura é o terminal.
- **Tokens:** `static/css/tokens.css` é a fonte única de cores/tipografia (claro "papel de mapa" por padrão; escuro automático via `prefers-color-scheme`). Cada estado é uma "linha" com cor própria: verde=concluída, amarelo=cursando, azul=disponível, magenta=planejada, cinza=bloqueada, vermelho=conflito. Variantes `--*-ink` garantem contraste de texto nos dois temas.
- **Tipografia:** Bricolage Grotesque (títulos, números) + Public Sans (interface), **hospedadas em `static/fonts/`** (sem CDN; licença OFL em `static/fonts/LICENSE-*.txt`).
- **Elemento de assinatura:** fluxograma com linha de metrô (estação do período: verde=concluído, amarelo=em curso) e "caminho" de progresso na barra lateral.
- Telas `inicio`, `entrar`, `entrar_confirmar`, `importacao` e o app usam os mesmos tokens. Cores de disciplina vindas dos dados agora só aparecem como borda/ponto (nunca como texto).
- Verificação: capturas em claro, escuro e 390px; 0 erros de JS. Falta revisar `importacao.html` visualmente e o modal de detalhe da disciplina nos dois temas.


## Peças 3 e 4 — Simulador de futuro, sugestão otimizada e rebranding da tela inicial

Trabalho dividido em PARTES. Cada parte termina com algo verificável; o estado de cada uma está marcado.
Legenda: ✅ pronto e testado · 🟡 escrito, ainda NÃO testado · ⬜ não começado.

| Parte | Conteúdo | Estado |
|---|---|---|
| A | Domínio do simulador: `domain/restante.py` (calendário de oferta par/ímpar/sempre, o que falta cursar), `domain/replanejamento.py` ("e se eu reprovar em X"), `domain/simulacao.py` (riscos, caminho crítico, horários projetados, conflitos futuros) | 🟡 teste rápido manual passou (riscos, caminho crítico e cenários saíram corretos); falta `pytest` próprio |
| B | Domínio do otimizador: `domain/otimizador.py` (grafo → limite inferior; guloso; recozimento simulado; alocação de turmas; optativas) | 🟡 escrito; tem um ponto pendente (requisitos originais para o replanejamento) e NUNCA foi executado |
| C | Serviço + API: `POST /api/cursos/<id>/simulacao`, `POST /api/cursos/<id>/simulacao/sugerir`, edição da periodicidade na tela (dono do curso) | ⬜ |
| D | Tela "Simulador" em blocos (visão geral, linha do tempo, riscos, caminho crítico, e se eu reprovar, sugestão) + CSS | ⬜ |
| E | Rebranding da tela inicial (`inicio.html`): novo hero, "o que o Rumo faz", passos atualizados, dúvidas | ⬜ |
| F | Testes (`test_simulacao_dominio`, `test_otimizador`, `test_api_simulacao`), docs e este arquivo | ⬜ |

Baseline antes das peças: 637 testes passando.

### Decisões já tomadas
- Periodicidade desconhecida nunca vira "sempre": o simulador usa a cadastrada, senão ESTIMA pelo período sugerido (marcada "estimada"), senão "desconhecida".
- Horário de período futuro é PROJEÇÃO (último período de mesma paridade) e a tela diz isso.
- Quem está cursando conta como concluído no início do plano; o planejado antes conta como concluído depois (premissas devolvidas pela API).
- Créditos de optativas que faltam viram um bloco "reservar N créditos", sem inventar disciplinas.
- Período inicial da simulação: o primeiro semestre do plano, ou o informado na tela (nunca assumido pela data do servidor).
- Otimizador determinístico (semente) e só com a biblioteca padrão; domínio continua puro (`test_domain_pureza`).


## Rodada: periodicidade obrigatória na validação, exclusão de curso, CSV atualizado
- **Validação:** `periodicidade_nao_informada` (aviso único com a lista) e `turma_em_periodo_incompativel` (turma em período de paridade diferente da cadastrada) em `importers/validacao/semantico.py`. Continuam avisos (vazio = desconhecido).
- **Tela Disciplinas:** alerta quando há disciplina sem oferta informada.
- **Exclusão de curso:** `DELETE /api/cursos/<id>` (só dono; 403 não dono, 404 inexistente/privado alheio, 409 se outra conta tem histórico). Apaga o histórico do dono antes (FK `RESTRICT`). Botão **Excluir** nos cartões da tela inicial (`/api/cursos` devolve `meu`).
- **CSV de exemplo:** `disciplinas.csv` ganhou a coluna `periodicidade` (INF497 fica vazia: sem turma no quadro). Por isso a prévia do exemplo agora tem **1 aviso** (testes ajustados).
- **Não executado por mim:** `pytest` completo e navegador (ambiente sem SQLAlchemy). Só rodei os testes novos de validação (sem banco) e a prévia do exemplo real.


## Melhoria — FASE 1: otimização, grafos e metaheurísticas (`planner/domain/`) — ✅ concluída, 🛑 aguardando ok

### Antes de começar: 17 testes vermelhos herdados (corrigidos)
A rodada anterior ("periodicidade obrigatória…") não tinha rodado o `pytest`. Linha de base real: 681 ✅ / 17 ❌.
- `api/__init__.py`: o blueprint `simulacao` **nunca era registrado** → todas as rotas do simulador/sugestão davam 404.
- `services/cursos.py`: catálogo passa a devolver `pode_editar_oferta` (só o dono edita par/ímpar).
- `tools/export_legacy_seed.py`: exporta `periodicidade` (paridade das turmas; sem turma = vazio) e preserva a
  revisão manual já gravada (`PERIODICIDADE_REVISADA`: ERU324, INF280, MAT135, MAT140, MAT147, MAT241, MAT271 = "sempre").
- Testes: `_gravar` de `test_previa_servico` não copiava `periodicidade`; o auxiliar `problemas()` de
  `test_importers_validacao` passa a ignorar o aviso de periodicidade (tem teste próprio).

### O que foi feito
1. **Dívida técnica:** `_Modelo(nos, grafo, disciplinas, requisitos, …)` recebe os requisitos no construtor;
   `requisitos_originais` e `_requisitos_de` foram removidos.
2. **Grafos (`grafo.py`):**
   - `alturas` (caminho mais longo até um sumidouro, pré = 1, co = 0) e `pesos_posicionais` (créditos do nó + descendentes).
     O guloso ordena por (último semestre possível, −altura, −peso posicional, −créditos, sugerido, id) — estilo Hu/Coffman-Graham.
     Há também um guloso "cheio até o teto"; fica o ponto de partida com menos violações.
   - `cadeia_critica`: sequência explícita A → B → C que define o prazo. Sai em `ResultadoOtimizacao.cadeia_critica`,
     em `CaminhoCritico.cadeia` (simulador) e no JSON (`cadeia_critica`/`critico.cadeia` + `cadeia_mensagem` pronta).
   - Limites inferiores novos: `limite_energetico` (para todo (a, b): H ≥ a + b + ⌈créditos dos nós com primeiro ≥ a e
     cauda ≥ b / teto⌉ — cabeças e caudas juntas) e `horizonte_por_janelas` (H fixo → janela [primeiro, último(H)] de cada nó;
     toda janela tem de comportar os créditos presos nela, **inclusive por paridade**: condição de Hall sobre os semestres
     em que cada nó é ofertado). Todos são limites válidos; vale o maior.
3. **Recozimento simulado (`otimizador.py`):**
   - `_Estado`: avaliação **incremental** — mover uma disciplina só recalcula oferta dela, carga dos 2 semestres, risco,
     sugerido, colisões com os colegas dos 2 semestres (linha de colisão em cache) e os termos de requisito em que ela aparece.
     Teste compara o delta com o cálculo completo em 1500 movimentos.
   - Vizinhança: mover dentro da **janela** [mais cedo pelos requisitos, mais tarde pelos dependentes que só ela atende],
     ofertado e com espaço; **cadeia** (move e empurra dependentes / puxa requisitos); **troca** entre semestres; com a
     solução inviável, movimento de **reparo** (disciplina em violação → janela/semestre com espaço).
   - T0 calibrada por amostra de pioras (aceitar a piora média com 50%); **reaquecimento** ao estagnar (volta ao melhor);
     **3 reinícios** com sementes derivadas da semente do pedido; prazo `tempo_max_s` respeitado.
   - Fase "menor nº de semestres": orçamento cheio, para na 1ª solução viável e o custo vira "nº de violações"
     (macios só desempatam), para atravessar platôs.
4. **Alocação de turmas (`alocacao.py` + novo `semana.py`):** custo = (colisões, penalidade) em ordem lexicográfica.
   Penalidade por `PreferenciasSemana`: encontro em bloco indisponível, horas de janela, dias com aula, encontro fora do
   turno, aula em dia que se quer livre (pesos configuráveis). A poda usa só a parte monótona (janelas entram na folha).
   **Sem preferências o resultado é idêntico** (teste compara com o algoritmo antigo em 300 instâncias aleatórias).
5. **Testes:** `test_otimizador.py` (+15), `test_alocacao_preferencias.py` (novo, 7), JSON da cadeia. Carregador do exemplo
   sem banco em `tests/exemplo_cc.py`. Desempenho: exemplo de CC completo (teto 24) em **< 5 s** (roda em ~0,4 s).

### Como medi (`python -m tools.medir_otimizador`)
- **Velocidade:** uma corrida de recozimento, modo refino, teto 24, h = 9, mesma solução inicial, 6000 iterações.
  Antes × depois intercalados na mesma sessão (o código antigo carregado do git), mediana de 5:
  **12,6 mil → 39,5 mil iterações/s (≈ 3,1×)**. Pipeline completo: 0,7–1,2 s → 0,3–0,9 s, mesma qualidade
  (mesmos semestres, 0 colisões, carga equivalente).
- **Prova de ótimo** (10 cenários: tetos 18/16/14/12/10 × começando do zero / do meio do curso):
  **5/10 → 8/10 com `otimo_comprovado`**. Ganharam prova: meio+teto 14 (LB 6→8), meio+teto 12 (7→8), meio+teto 10 (8→10).

### Decisões / limites
- Calibrar T0 para aceitar 80% das pioras deixou a busca quente demais (custo pior por iteração); 50% ficou equivalente à
  temperatura fixa antiga. Mantido o orçamento padrão de 9000 iterações (24 mil não mudou o resultado).
- **Teto 14 do zero** (138 créditos em 10 semestres = 2 de folga) é viável, mas a busca só acha às vezes: sai 11 semestres
  "melhor encontrado" (limite 10). **Teto 10 do zero**: limite 14 = horizonte máximo e a busca não fecha → "sem solução".
- A cadeia crítica vem dos "primeiros semestres possíveis" (sem teto de créditos): mostra a cadeia de requisitos/oferta;
  quando o prazo é limitado por créditos, a frase de `explicar_sugestao` continua dizendo isso.
- Preferências da semana ainda não chegam pela API (é a Fase 2); por ora só o domínio e os testes as usam.
- `pytest`: **720 passaram**. Sem mudança de modelo (nenhuma migração).


## Melhoria — FASE 2 + complementos (preocupações do aluno, importação sem duplicar, cursar junto) — ✅ concluída, 🛑 aguardando ok

`pytest`: **803 passaram** (720 ao fim da Fase 1). `flask db check` limpo num SQLite novo (migração `e7a4b9c2d013`).
⚠️ O Postgres do `.env` ainda NÃO recebeu a migração: rodar `flask --app planner db upgrade` (não foi feito por mim).

### Fase 2 — simulação com as preocupações reais
- **Preferências** (`domain/preferencias.py`, `domain/semana.py`): blocos indisponíveis, turno, dias livres, teto por
  período, períodos trancados, máximo de "pesadas" (pesada = já reprovada no histórico ∪ marcada pelo aluno; nada
  inventado). Validadas em `simulacao_json.ler_preferencias` com erro **por campo** (`detalhes.campo`).
- **Prazo** (`domain/prazo.py`): regular (duração) e máximo (duração × fator, padrão 1,5). Sem duração ou sem ingresso,
  nada é afirmado. Ingresso: informado › período mais antigo do histórico › início do plano se o histórico está vazio.
  Trancamento não conta no prazo.
- **Monte Carlo** (`domain/monte_carlo.py`): 500 execuções (semente fixa) de `replanejar` com reprovação sorteada a cada
  tentativa (pode reprovar de novo). Taxa = histórico do aluno suavizada para 85% com 4 tentativas fictícias; disciplina
  já reprovada × 0,8 (uma vez só — compor virava espiral). Devolve distribuição por período, P50/P80/P90, chance até o fim
  do plano e sensibilidade (**atraso a mais** quando ela reprova vs. quando não; a média bruta enganava porque incluía as
  outras reprovações).
- **Semana** por semestre: horas em aula, dias livres (dias letivos do curso ou SEG–SEX), janelas, choques com indisponíveis.
- **Otimizador** respeita: teto por período e trancamento (duros, capacidade por semestre e calendário sem o período);
  turno, dias livres, pesadas e "todas as turmas caem no indisponível" (macios). Turma que bate no indisponível sai das
  candidatas quando há outra (regra dura na alocação).

### Complemento 1
1. **Importar sem duplicar** (`domain/cursos_parecidos.py`): candidatos por nome normalizado (+ instituição) ou ≥ 60% dos
   códigos, só do mesmo dono. A prévia compara com o mais parecido e exige a decisão; a confirmação sem `curso_id` nem
   `criar_novo` dá **409** com os candidatos. `/importar` pergunta "Atualizar um curso meu / Criar curso novo" e mostra
   "Parece o curso X (N disciplinas em comum)". Atualizar sem curso.csv não mexe no curso (a prévia diz).
2. **Selo par/ímpar único** (`seloOferta` em core.js): a oferta efetiva (cadastrada/estimada/desconhecida) vem no catálogo;
   cartão do semestre mostra "✕ Não abre em AAAA/N" (cadastrada) ou "⚠ Talvez não abra" (estimada) sem esperar a análise.
   Mesmo selo na lista, cartão, calendário, simulador, sugestão, fluxograma e detalhe.
3. **Formatura pelo plano no Painel** (`painel.formatura_pelo_plano`): duas datas, "pelo seu ritmo" e "pelo seu plano"
   (o plano aberto ou o mais recente), com optativas (exigidas − cumpridas − planejadas, encaixadas com o teto).
4. **Histórico opcional**: passo "(opcional)" com "Pular"; uma linha em cada tela diz o que melhora com ele. **Colar a
   tabela** do sistema acadêmico (`importers/historico_colado.py`): reconhece pelo conteúdo (código, período, situação,
   nota), prévia (reconhecidas / não encontradas / repetidas / não entendidas) e confirmação.
5. **Preferências salvas** (modelo `preferencia_aluno` + migração; `GET/PUT /api/cursos/<id>/preferencias`), usadas por
   Simulador, Sugestão, Planejamento e Calendário sem perguntar de novo. Planejamento/Calendário: "Não cabe na sua
   disponibilidade", "A turma Tx cabe" (botão), "Sem horário — choque e disponibilidade não verificados"; o Calendário
   desenha os blocos indisponíveis. **Optativas que cabem** (`domain/optativas.py`, botão em cada semestre): oferta,
   requisitos e disponibilidade, ordenadas por encaixe; só "Adicionar" põe no plano.

### Complemento 2
- **Optativas no Simulador**: exigidas/cumpridas/planejadas/faltam, risco "Faltam N créditos", as duas datas e
  "Cabem mais N créditos de optativa aqui" por semestre; optativa planejada passa por oferta, requisitos, choques e cenários.
- **Choque visível no item** (`alocacao.choques_por_disciplina`, `analise_json.marcas_do_item`): "Choque com X (Seg 14–16)"
  vermelho, "Possível choque" amarelo (horário projetado), "Bate com sua disponibilidade", "Sem horário — choque não
  verificado"; contador "N choques" no topo do semestre leva ao item. Mesma regra e texto no Planejamento e no Calendário
  (que agora também projetam o quadro de mesma paridade).

### Complemento 3 — cursar junto
- `domain/juntas.py`: candidatas (TCC/Monografia/Projeto Final × Seminário/Estágio no mesmo período sugerido, ou
  correquisito mútuo; nunca regra automática) e problemas (ofertas só ímpar × só par; uma exige a outra, mesmo indiretamente).
- Otimizador: grupo **obrigatório** vira bloco (oferta = interseção, requisitos = união, créditos = soma; turmas = combinações
  das turmas dos membros no mesmo período). **Preferência** só custa quando separado. Grupo impossível é ignorado e avisado.
- Simulador: "X e Y estão em semestres diferentes" → "Mova para o semestre N"; replanejamento: obrigatório entra completo
  e reprovar em um adia o grupo; preferência não arrasta.
- Tela: pergunta única no Simulador ("Sim, essas juntas / Escolher outras / Não, obrigado"), edição em Preferências,
  "Cursar junto com…" no detalhe, tag "Junto com X" nos cartões, ao arrastar pergunta se leva a outra (com Desfazer em
  toast de 8 s) e a sugestão diz "Para manter X e Y juntas, a formatura fica em AAAA/N".

### Validação no navegador
Playwright (instalado nesta rodada), exemplo de CC num SQLite temporário com login dev: Painel, Planejamento (+ optativas
que cabem), Calendário, Histórico (+ colar), Simulador (+ preferências, sugestão, erro de campo) e /importar, em 1366 px e
390 px, claro e escuro. Sem `pageerror`; o único erro de console é o 422 provocado de propósito pelo teste de erro de campo
(que aparece junto ao campo, com `aria-invalid`/`aria-describedby`). Corrigidos durante a validação: selo "Sem horário"
duplicado, linha de horário espremida, faixa de status espalhada, bloco de colar sumindo ao redesenhar, inconsistência
"créditos exigidos" entre progresso e formatura pelo plano.

### Limites conhecidos
- Monte Carlo do exemplo de CC leva ~2–3 s (500 execuções); a tela mostra "Simulando…".
- "Pular histórico" é lembrado só no navegador (conveniência; o app funciona igual sem histórico).
- O contador de "pesadas" no otimizador conta um bloco "cursar junto" como 1.
- Capturas de tela em `…/scratchpad/capturas` (temporárias). As de "antes" ficam para a Fase 3.


## Melhoria — FASE 3: usabilidade (Nielsen), UI e UX + pontos parciais — ✅ concluída

`pytest`: **809 passaram**. `flask db check` limpo (sem modelo novo nesta fase). Os scripts da página foram checados
JUNTOS na ordem de carga (um `const hhmm` repetido entre arquivos derrubava o Simulador inteiro — achado na validação).

### Avaliação heurística (antes das correções)
| # | Heurística | Problema | Tela | Sev. | Correção |
|---|---|---|---|---|---|
| 1 | H4 Consistência | Marca "Trilha" no README × "Rumo" no app | README | 2 | README → Rumo |
| 2 | H4 Consistência | Títulos ≠ menu ("Planejamento de Matrícula", "Calendário Semanal"…) | todas | 2 | títulos = rótulos do menu |
| 3 | H8 Minimalismo | Dicas de página com 1–2 frases longas | todas | 2 | rótulos curtos ("Passo 2 de 4 · arraste…") |
| 4 | H8 Minimalismo | Simulador empilhava 7 blocos longos | Simulador | 3 | resumo fixo + abas Visão geral · Riscos · Semestres · E se reprovar · Probabilidade · Sugestão (setas/Home/End) |
| 5 | H5/H6 Prevenção, reconhecimento | "Começa em" em texto livre AAAA/N | Simulador, Sugestão | 3 | seletor dos próximos períodos + "Outro…" para digitar |
| 6 | H9 Erros | Erros de campo só em toast | Sugestão, período | 2 | erro junto ao campo (`aria-invalid` + `aria-describedby`) |
| 7 | H3 Controle | Remover disciplina/semestre/plano e trocar turma sem desfazer; não havia como remover semestre | Planejamento | 3 | toast "Desfazer" (~8 s); confirmação só na exclusão do plano (que também desfaz); botão ✕ no semestre |
| 8 | H1 Status | Sugestão só dizia "Calculando…" | Sugestão | 2 | etapas grafo → guloso → recozimento → turmas → chance (estimativa enquanto espera; tempos reais ao terminar) |
| 9 | H2 Mundo real | "Ótimo comprovado/mínimo teórico" técnico | Sugestão | 2 | selo "Prazo mínimo garantido" × "Melhor plano encontrado" com frase simples |
| 10 | H2 Mundo real | Caminho crítico como lista de chips | Simulador, Sugestão | 2 | cadeia crítica como linha de metrô (terminal âmbar = formatura) |
| 11 | H6 Reconhecimento | Não dava para comparar o plano atual com a sugestão | Sugestão | 3 | tabela "Plano atual × Sugestão" (formatura, P50, chance, carga média/máx., choques, dias livres) antes de salvar |
| 12 | H6/H7 | Indisponibilidade digitada hora a hora | Preferências | 2 | grade semanal clicável (clique/arraste/teclado) + presets "Trabalho manhã", "Estágio tarde", "Noturno (só à noite)"; horários exatos recolhidos |
| 13 | A11y | `--text3` abaixo de 4,5:1 (claro: 4,0 sobre `bg4`; escuro: 4,4) | todas | 2 | claro `#56667D`, escuro `#8D9DB6` (≥ 4,5 em todas as superfícies) |
| 14 | A11y | Botão "remover" do cartão `display:none` fora do hover: inalcançável por teclado | Planejamento | 3 | sempre presente (discreto), realçado no hover/foco |
| 15 | A11y | Alvos pequenos e foco só em alguns elementos | todas | 2 | mínimo 24 px (28 px nos `btn-sm`), foco visível em links, abas e células |
| 16 | H1/H6 | Calendário abria vazio ("Escolha um semestre") com plano pronto | Calendário | 2 | abre no 1º semestre com disciplinas |
| 17 | H8 | Na sugestão, a frase "é o MENOR prazo…" repetia o selo | Sugestão | 1 | a frase só aparece sem selo |
| 18 | A11y | Gráfico do Monte Carlo sem alternativa textual | Simulador | 2 | já resolvido na Fase 2 (tabela `sr-only` + frase "X% de chance de formar até AAAA/N") |

### Pontos parciais da rodada anterior (fechados)
- Selo par/ímpar também nos blocos de aula do Calendário (quando a disciplina não abre no período).
- Contador "N choques" no topo do semestre também no Planejamento (leva ao cartão) e no Calendário (`choques_texto` da análise).
- Grupo "cursar junto" impossível é avisado AO SALVAR (`avisos_juntas`, com o motivo).
- Fluxos verificados no navegador: remover + Desfazer, excluir plano (confirmação + Desfazer), pergunta "cursar junto"
  (uma vez só), "levar junto" + Desfazer, abas pelo teclado, grade e presets, período inválido com erro no campo,
  etapas e comparação da sugestão, decisão "atualizar × criar" na importação.

### Validação no navegador
- `tools/validacao_ui/capturar.py` (telas em 1366/390 px × claro/escuro) e `tools/validacao_ui/fluxos.py` (fluxos acima),
  contra o app local com login dev (`AUTH_PROVEDOR=dev`, SQLite à parte). Resultado: **0 falhas, 0 erros de console,
  sem rolagem horizontal em 390 px**.
- Capturas em `docs/capturas/fase3/`: `antes/`, `depois/`, `fluxos/` e `lado-a-lado/` (antes | depois).
- Achado da validação: um servidor antigo continuava preso à porta e respondia pelo código velho; as capturas finais
  foram refeitas com o processo novo.

### Limites
- O progresso por etapas durante a espera é uma ESTIMATIVA (a resposta vem de uma vez); os tempos reais aparecem no fim.
- Sugestão com grupo "cursar junto" leva ~5 s no exemplo de CC (roda o otimizador também sem o grupo, para a frase
  "Para manter X e Y juntas…", mais o Monte Carlo).
- A lista de períodos parte do histórico/plano; sem nenhum dos dois, do período corrente do relógio da pessoa (é só uma
  lista para escolher; continua havendo "Automático" e "Outro…").
- Contraste verificado nos tokens de texto; cores de selos/badges usam as variantes `*-ink` já existentes.


## Arquitetura de informação + turmas automáticas + TCC no fim + histórico por CSV — ✅ concluída

`pytest`: **821 passaram**. `flask db check` limpo com a migração nova `f1b2c3d4e5f6` (`plano_item.turma_auto`).
⚠️ No Postgres do `.env`: `flask --app planner db upgrade` (duas migrações pendentes: `e7a4b9c2d013` e `f1b2c3d4e5f6`).

### Diagnóstico (por que parecia bagunçado)
1. O **Simulador fazia dois trabalhos opostos**: avaliar o plano montado e CRIAR um plano novo (Sugestão), cada um com
   seu "Começa em". As optativas só existiam na Sugestão, então os dois chegavam a números diferentes sem dizer por quê.
2. **Preferências no lugar errado**: valiam para Planejamento, Calendário, Simulador e Sugestão, mas só eram editáveis
   dentro do Simulador.
3. **Turma era trabalho manual sem ajuda**: o servidor já calculava a melhor combinação, mas só usava para avisar.
4. O **Calendário era um "passo"**, mas é só uma forma de VER o plano.

### Como ficou (modelo mental: de onde venho → minha rotina → monto o caminho → testo o caminho)
| Passo | Tela | Faz |
|---|---|---|
| 1 (opcional) | Histórico | o que já cursei; colar OU enviar .csv do sistema acadêmico |
| 2 (opcional) | **Minha rotina** (nova) | horários em que não posso (grade), turno, dias livres, pesadas, teto por período, trancamento, cursar junto, **optativas** (ainda preciso N; já fiz fora do histórico), prazo |
| 3 | Planejamento | montar à mão **ou "✨ Sugerir plano"** (a sugestão mudou-se para cá, comparada com o plano aberto; "Usar este plano" cria e abre um plano novo). Turmas **automáticas**. Botão "📅 Semana" |
| — | Calendário | "a semana do plano" (sem número; no celular sai da barra inferior e fica no botão "Semana") |
| 4 | Simulador | **só avalia** o plano aberto, com a mesma rotina; diz o que está simulando e leva a "Sugerir um plano melhor" |

- **Optativas únicas**: a rotina guarda "ainda preciso de N créditos" e "já fiz fora do histórico"; a simulação e a
  sugestão usam os MESMOS números (antes só a sugestão perguntava).
- **Turmas automáticas** (`plano_item.turma_auto`): com quadro real no período, o Rumo escolhe a turma da melhor
  combinação do semestre (sem choque, respeitando a rotina — `marcas.turma_sugerida` da análise) e REFAZ a escolha
  quando o semestre muda. O seletor mostra "Automática: T1 · Qui 08–10" e "✓ escolhida pelo Rumo · troque se quiser";
  escolher outra turma a deixa fixa ("escolhida por você"); "Automática" devolve a escolha ao Rumo. Plano criado por
  sugestão já vem com as turmas automáticas.
- A pergunta "cursar junto?" aparece em Minha rotina e ao abrir "Sugerir plano" (não mais no Simulador).

### TCC no fim do curso e os dois TCCs
- `domain/fim_de_curso.py`: TCC, Trabalho de Conclusão, Monografia, Projeto Final, Elaboração de TCC — e seminários do
  último ano ou ligados por requisito a eles — recebem um **degrau** (0 = último semestre), pelo período sugerido
  (TCC I/Elaboração no 7º, TCC II/Seminários no 8º → 1 e 0) ou pela cadeia de requisitos.
- Sugestão: penalidade forte por semestre antes do degrau + o guloso não os adianta. No exemplo de CC: Projeto Final e
  Seminário I no penúltimo, Seminário II no último; a sugestão diz isso numa frase. Ótimo comprovado continua 8/10.
- Simulador: risco "X fecha o curso, mas está antes dos últimos semestres" → "Mova para o semestre N".
- "Cursar junto": TCC I + Elaboração de TCC (mesma família, mesmo período) agora são sugeridos como par.

### Histórico por CSV
- Botão para enviar o .csv/.txt exportado; mesma prévia do texto colado. O parser reconhece CSV (vírgula ou ponto e
  vírgula, 2+ separadores por linha de forma consistente, aspas respeitadas, BOM do Excel) e separa as colunas antes —
  senão "60,7" (CH, nota) viraria a nota 60,7. Texto colado com nota "8,5" continua sendo lido como antes.

### Validação no navegador
`tools/validacao_ui/fluxos.py` (reescrito para a nova arquitetura) e `capturar.py`: 0 falhas, 0 erros de console,
1366/390 × claro/escuro, sem rolagem horizontal. Capturas em `docs/capturas/arquitetura/`. Achados e corrigidos: ações do
topo cobrindo o título no celular; 8 itens na barra inferior (Simulador saía da tela); plano vindo da sugestão marcava
as turmas como "escolhidas por você".

### Limites
- A detecção de TCC/seminários é por nome e período sugerido (não há coluna "fim de curso" no CSV); um seminário que não
  é de conclusão, no meio do curso, não é afetado.
- Turma automática só com quadro REAL do período; em período futuro (projeção) a turma fica para quando o quadro sair.


## Sugestão que forma no tempo certo: optativas no meio, plano atual como partida, disciplina em período específico — ✅

`pytest`: **829 passaram**; `db check` limpo (sem modelo novo); ótimo comprovado continua 8/10.

### O problema ("consigo formar em 2029.1 e a sugestão dá 2029.2")
1. A sugestão otimizava só as obrigatórias e depois tentava ENCAIXAR as optativas nos semestres que sobravam; o que não
   cabia empurrava a formatura para o fim.
2. A sugestão começava do zero e ignorava o plano que a pessoa já montou (e que podia ser melhor).
3. A comparação "Plano atual × Sugestão" não era justa: a data do plano atual não contava as optativas que faltam.

### O que mudou
- **Optativas dentro da otimização**: os créditos que faltam viram blocos (do tamanho da optativa típica do curso, sem
  requisito, abrem todo período) otimizados junto com as obrigatórias, com preferência pelo **meio do curso**. Exemplo de
  CC com 12 créditos: 4 + 4 + 4 no 3º, 4º e 5º semestres, mesma formatura do plano atual (2029/2). A tela diz
  "Espaço para optativa: N créditos (você escolhe qual)".
- **Plano atual como ponto de partida**: "Sugerir plano" envia o plano aberto; ele entra como solução inicial da busca,
  então, sem pedidos novos, a sugestão não forma depois dele.
- **Comparação justa**: a formatura do plano atual inclui as optativas que faltam ("2030/1 (com as 12 cr de optativas…)").
- **Disciplina em período específico** (`fixas` na rotina; "Cursar em um período…" no detalhe da disciplina): a sugestão
  a põe exatamente lá; se ela não abre no período ou os requisitos não ficam prontos, o pedido é ignorado e a sugestão diz
  por quê. O Simulador avisa quando o plano não respeita o pedido.
- **Custo dos pedidos**: com disciplina fixada ou "cursar junto", a sugestão compara com a mesma busca sem os pedidos:
  "Seus pedidos (INF213 em 2028/1) deixam a formatura em 2030/2; sem eles seria 2029/2." O selo de prazo mínimo diz
  quando é "com os seus pedidos".

### Limites
- O tamanho do bloco de optativa é a mediana dos créditos das optativas do curso (4 se não houver).
- O ponto de partida usa as disciplinas do plano que ainda faltam; optativas específicas do plano não substituem os blocos.

## Usabilidade: avaliação de uso + edição de disciplinas

Feito a partir de uma avaliação com a jornada de um aluno novo (Playwright, 1366 px e 390 px, curso de exemplo de CC).

### Editar disciplinas pela tela (sem reimportar CSV)
- `PATCH /api/cursos/<id>/disciplinas/<d>` edita e `POST /api/cursos/<id>/disciplinas` cria (só quem trouxe o curso;
  outra conta recebe 403 em curso público e 404 em curso privado). Campos: código, nome, tipo, créditos, carga horária,
  período na matriz, oferta e requisitos (pré e co, mantendo grupos "ou"). Em branco = não informado (nunca zero).
- Recusa código repetido (409) e pré-requisitos em círculo (`domain/edicao_catalogo.py`); o erro aponta o campo.
- Tela Disciplinas: "+ Nova disciplina", "Editar" em cada linha e no detalhe, oferta editável direto na tabela,
  filtros (obrigatórias, optativas, sem oferta), "Desfazer" depois de salvar. No celular, colunas secundárias somem.

### Problemas da avaliação corrigidos
1. **"Dá pra trabalhar de manhã?"**: `semana.rotina_comporta` olha todas as turmas conhecidas das obrigatórias que faltam.
   Minha rotina, Sugestão e Simulador mostram uma resposta só ("Com a sua rotina, N obrigatórias não cabem…"), e
   `GET /api/cursos/<id>/rotina` a devolve. Riscos repetidos (3+ do mesmo tipo) viram um grupo com título.
2. **Quadro publicado manda na sugestão**: período com quadro em que a disciplina não está não abre para ela
   (`_CalendarioComQuadro`); pedido de período nessas condições é ignorado com o motivo.
3. **Página inicial**: "Como funciona" segue a rota atual (curso → histórico opcional → rotina opcional → planejamento → simulador).
4. **Período no Planejamento**: o seletor lista também períodos sem quadro ("· sem quadro"); o cartão diferencia
   "Turmas de 2027/1 ainda não saíram · horário estimado" de "Não está no quadro de 2027/1".
5. **Painel**: o cartão "pelo seu plano" mostra a melhor data conhecida (`cartao.valor`) e do que ela depende.
6. **Períodos sugeridos** começam no próximo período de matrícula, não no que está em andamento.
7. **Calendário**: semestres sem quadro mostram a turma projetada (tracejada, "estimado"), vinda de `turma_projetada`.
8. **Textos**: a Sugestão sem histórico pede o período sem contradição; a comparação só aparece quando há plano simulado.
9. **Celular**: toasts no topo (não cobrem o "Próximo passo") e avisos simples somem ao trocar de tela.
10. **Celular**: semestres empilhados no Planejamento; Calendário vira lista por dia.

### Limites
- A rotina × curso considera todas as turmas conhecidas, de qualquer período: uma turma antiga fora do horário conta como "cabe".
- Excluir disciplina pela tela não foi feito (o histórico e os planos dependem dela); continua pela importação.

## Teórica × prática separadas e créditos fora do limite

### Turma teórica e prática separadas
- `turmas.csv` aceita a coluna opcional `componente` (`teorica` | `pratica`; aceita "Teórica", "T", "Laboratório"…).
  Vazio = turma completa, como antes. Valor desconhecido é erro de importação.
- `domain/componentes.py`: no mesmo período, teóricas × práticas viram **opções de matrícula** combinadas
  (encontros das duas, código "T1+P2", id negativo que se desfaz nas partes). Alocação, otimizador, simulador,
  rotina e calendário continuam escolhendo UMA turma por disciplina e passam a enxergar a combinação certa.
- O plano guarda a teórica em `plano_item.turma_id` e a prática em `turma_pratica_id`; a tela vê um id só.
- Calendário: cada bloco diz a parte ("QUI100 · T1 teórica", "QUI100 · P2 prática").

### Créditos que não contam no limite do semestre
- `disciplina.conta_no_limite` (padrão: sim). Desmarcado, os créditos contam para formar mas não para o limite da
  matrícula: sobrecarga, sugestão (capacidade do semestre), replanejamento, espaço para optativas e formatura com
  optativas usam `Disciplina.creditos_no_limite`.
- Editável em Disciplinas ("Conta no limite de créditos do semestre"); a tabela mostra "fora do limite".
- Planejamento e Simulador mostram "10 / 20 créditos · +18 fora do limite".

### Limites
- A prática não fica presa a uma teórica específica (P1 só com T1): todas as combinações do período valem.
- Não há coluna `conta_no_limite` no CSV; o ajuste é pela tela.
- Migração nova: `a3c5e7f9b201` (rodar `flask --app planner db upgrade` no Postgres).
