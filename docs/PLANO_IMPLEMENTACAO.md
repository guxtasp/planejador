# PLANO DE IMPLEMENTAÇÃO

Cada sub-etapa cabe em uma conversa curta e termina com testes verdes e algo executável.
Critério de pronto = "Verificação". 🛑 = parar e pedir validação ao usuário.

## Etapa 0 — Fundação ✅
Entregue. Ver `PROGRESSO.md`.

## Etapa 1A — Modelos e migração
- Modelos: `Curso, Disciplina, Requisito, Turma, Encontro, Usuario, Historico, Plano, PlanoSemestre, PlanoItem`
  (campos em `ARQUITETURA.md §4`). Campos acadêmicos opcionais são `nullable`.
- Constraints: `UNIQUE(curso_id, codigo)`, FKs com `ondelete` adequado
  (**apagar disciplina não pode apagar histórico**: histórico guarda `disciplina_id` com `RESTRICT`).
- Migração inicial via Flask-Migrate.
- Verificação: `db upgrade` em SQLite; testes de constraints (duplicata, FK, cascade correto).

## Etapa 1B — Repositories e exemplos
- Repositories finos (`CursoRepository`, `DisciplinaRepository`, `TurmaRepository`, …) sem N+1 (`selectinload`).
- `tools/export_legacy_seed.py`: gera `examples/ciencia-da-computacao/{curso,disciplinas,requisitos,turmas}.csv`
  a partir do seed do `legacy/app_legacy.py`. Os horários 2026/1 e 2026/2 viram `periodo_letivo` distintos.
- Verificação: testes de repositório; CSVs de exemplo gerados e revisados.

## Etapa 2 — Motor de regras (`planner/domain/`)
- Módulos: `requisitos.py` (pré/co com grupos OR e plano sequencial), `progresso.py`
  (obrigatórias + optativas até o exigido), `carga.py` (sobrecarga parametrizada),
  `previsao.py` (formatura pela média do próprio aluno), `conflitos.py` (por turma; "sem turma compatível").
- Estruturas imutáveis (`@dataclass(frozen=True)`) como entrada; nenhuma dependência de SQL.
- Verificação: testes unitários, **invertendo** os testes `legacy_bug` (bugs #4, #5 e regras hardcoded).

## Etapa 3A — Importação: parse + schema
- `importers/base.py`: interface `CsvImporter` (Strategy) + `Issue{arquivo,linha,coluna,severidade,mensagem}`.
- Detecção de encoding (UTF-8/BOM) e delimitador (`,` ou `;`); cabeçalhos obrigatórios.
- Parser de horários `"SEG 16:00-18:00 | QUI 14:00-16:00"` → encontros.
- Importers: curso, disciplinas, requisitos, turmas, histórico (validação de tipos/enums/HH:MM).
- Verificação: testes com CSV válido, malformado, BOM, `;`.

## Etapa 3B — Importação: referencial/semântico + prévia
- Referencial: requisito/turma apontando para disciplina inexistente; duplicatas no arquivo e no banco.
- Semântico: ciclos de pré-requisito, requisito em período posterior, encontros sobrepostos na mesma turma, razão créditos/CH incomum.
- `ImportPreview`: contadores (novos/atualizar/erros/avisos) + diff por upsert. **Nada é gravado.**
- Verificação: testes com CSVs inconsistentes; prévia determinística.

## Etapa 3C — Importação: commit + API + UI 🛑
- Commit atômico (uma transação) com relatório final; endpoints `validate` e `commit`.
- Tela de prévia (contadores, tabela com status por linha, Confirmar/Cancelar); download dos modelos CSV.
- `docs/IMPORTACAO.md` + prompt de IA (também embutido na tela, botão "copiar").
- Verificação: importar `examples/ciencia-da-computacao` ponta a ponta.

## Etapa 4A — Frontend modular + onboarding
- Extrair CSS/JS do `index.html` para `planner/static/{css,js}` **sem mudar lógica**; dividir em módulos por página.
- Onboarding: escolher curso existente ou criar/importar. Remover constantes de curso do JS.
- Verificação: app abre sem nenhum curso e guia o usuário até importar um.

## Etapa 4B — Turmas no planejador
- Planejador escolhe turma; calendário renderiza encontros da turma escolhida; grade derivada dos dados (sábado/noturno).
- Conflitos: "conflito" vs "conflito possível" vs "sem turma compatível".
- Verificação: cenários de múltiplas turmas e encontros.

## Etapa 5A — Autenticação
- Provedor e fluxo conforme `ARQUITETURA.md §6`. Middleware de usuário atual; rotas protegidas.

## Etapa 5B — Login Supabase + dados por usuário
- 5B-1: login pelo Supabase (substitui o link mágico da 5A). 5B-2: histórico, planos no servidor, dashboard.
- Histórico com N tentativas; planos por usuário; isolamento entre usuários testado.

## Etapa 6 — Deploy 🛑
- `vercel.json`, Postgres gerenciado, `psycopg2-binary`, variáveis de ambiente, remover `debug`/CORS aberto, CI (GitHub Actions: pytest).
- Verificação: URL pública funcional.

## Etapa 7 — Documentação final
- `IMPORTACAO.md` completo (exemplos, ausentes/ambíguos), README atualizado, revisão com um PPC real.

## Tarefas futuras (pedidas pelo usuário)
- **Melhorar a UI e a comunicabilidade da ferramenta.** Nada explicativo: a pessoa deve aprender testando
  (menos textos de ajuda e avisos longos; rótulos curtos, estados vazios acionáveis, feedback imediato nas ações).
