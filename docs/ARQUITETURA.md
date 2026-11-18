# ARQUITETURA

## 1. Camadas e responsabilidades

```
HTTP (planner/api)  →  Services (planner/services)  →  Domain (planner/domain)
                                   │                          (regras puras)
                                   ▼
                      Repositories (planner/repositories)  →  Models (planner/models)  →  Banco
Importers (planner/importers): parse → validar → prévia → commit (usa services/repositories)
```

| Camada | Pode importar | NÃO pode |
|--------|---------------|----------|
| `api` | services, errors | SQL, regras |
| `services` | repositories, domain | `flask.request` |
| `domain` | stdlib apenas | SQLAlchemy, Flask |
| `repositories` | models, `db` | regras de negócio |

## 2. Padrões de projeto adotados

| Padrão | Onde | Por quê |
|--------|------|---------|
| Application Factory | `planner/__init__.py` | testes isolados, várias configs |
| Objeto de configuração | `config.py` | ambientes sem `if` espalhado |
| Repository | `repositories/` | trocar/otimizar consultas sem tocar regras |
| Service Layer | `services/` | casos de uso reutilizáveis (API, importador) |
| Strategy | `importers/` | um importador por tipo de CSV, mesma interface |
| Pipeline / Chain | validação em 4 estágios | cada estágio simples e testável |
| Value Object (dataclass frozen) | `domain/` | regras puras e previsíveis |
| Blueprint | `api/` | uma rota-módulo por área |
| Erro de domínio centralizado | `api/errors.py` | camadas internas sem HTTP |

## 3. Convenções de código

- Nomes de domínio em português (`disciplina`, `turma`); nomes técnicos em inglês (`repository`, `service`).
- Docstring em todo módulo, classe e função pública; comentário explica o **porquê**.
- Funções curtas; um motivo para mudar por módulo; type hints.
- Frontend: sem lógica de regra de negócio duplicada; a API é a fonte da verdade.

## 4. Modelo de dados

```
curso(id, nome, instituicao, versao_matriz, creditos_obrigatorios, creditos_optativos_exigidos,
      ch_total, max_creditos_semestre NULL, duracao_semestres NULL, dias_letivos, visibilidade, dono_id)
disciplina(id, curso_id, codigo, nome, creditos NULL, carga_h NULL, periodo_sugerido NULL,
           tipo {obrigatoria|optativa|eletiva}, cor, UNIQUE(curso_id, codigo))
requisito(id, disciplina_id, requisito_id, tipo {pre|co}, grupo_alt NULL)   -- grupo vazio = AND; igual = OR
turma(id, disciplina_id, periodo_letivo, codigo_turma, docente NULL, vagas NULL,
      UNIQUE(disciplina_id, periodo_letivo, codigo_turma))
encontro(id, turma_id, dia, inicio, fim, local NULL)        -- todos obrigatórios p/ a turma
usuario(id, email, ...)
historico(id, usuario_id, disciplina_id, status, periodo_letivo, nota)   -- N tentativas
plano(id, usuario_id, curso_id, nome)
plano_semestre(id, plano_id, ordem, label, periodo_letivo NULL)
plano_item(semestre_id, disciplina_id, turma_id NULL)
```

Princípios: catálogo (estável) × oferta (semestral) × usuário (individual); `NULL` = desconhecido, nunca zero.

## 5. Formato dos CSVs (formalizado na Etapa 3A; revisado na 3D)

Quatro arquivos independentes (o histórico do aluno **não** vem de CSV: é informado no app, Etapa 5B); só `disciplinas.csv` é indispensável. **Negrito = coluna obrigatória**
(o cabeçalho precisa tê-la e a célula não pode ficar vazia). Nomes de colunas ignoram caixa e acento
(`Carga Horária` = `carga_h`); a coluna "apelidos" lista os nomes alternativos aceitos.

| Arquivo | Colunas | Apelidos aceitos |
|---------|---------|------------------|
| `curso.csv` (1 linha) | **nome**, instituicao, versao_matriz, creditos_obrigatorios, creditos_optativos_exigidos, ch_total, max_creditos_semestre, duracao_semestres, dias_letivos | curso→nome |
| `disciplinas.csv` | **codigo**, **nome**, **tipo**, creditos, carga_h, periodo_sugerido, cor | cod, carga_horaria, ch, periodo, semestre |
| `requisitos.csv` | **disciplina**, **requisito**, **tipo**, grupo_alt | codigo→disciplina, grupo→grupo_alt |
| `turmas.csv` | **disciplina**, **periodo_letivo**, **codigo_turma**, docente, vagas, horarios, local | turma→codigo_turma, periodo, horario, professor, sala→local |

- **Local (sala)**: coluna opcional `local` em `turmas.csv`; vale para todos os encontros da turma (`Encontro.local`).
- **Horários**: `"SEG 16:00-18:00 | QUI 14:00-16:00"` em uma célula; uma linha = uma turma;
  `|` separa encontros da MESMA turma; linhas diferentes = alternativas de matrícula.
  Dias: SEG TER QUA QUI SEX SAB DOM (também por extenso). Um encontro inválido descarta a turma inteira.
- **Vocabulários**: `tipo` de disciplina = obrigatoria | optativa | eletiva; `tipo` de requisito = pre | co
  (aceita "pré-requisito", "correquisito"…).
- **Formatos**: `periodo_letivo` = `AAAA/N` (aceita `2026.1`, `2026-01`); `cor` = `#rrggbb`;
  `dias_letivos` = `SEG|TER|...`; números inteiros (aceita `6.0` do Excel).
- **Arquivo**: UTF-8 com/sem BOM (Windows-1252 é lido com aviso); delimitador `,` `;` ou TAB detectado.
- **Vazio = desconhecido**, nunca zero (`0` explícito é preservado). Dois campos NÃO têm padrão e, se vazios,
  são erro: `tipo` da disciplina (decide o cálculo de progresso) e `codigo_turma` (identifica a opção de matrícula).

## 6. Decisões assumidas (revisáveis)

O usuário não respondeu às 5 perguntas do documento anterior; foram assumidas as
recomendações. **Dizer se quiser mudar antes da etapa indicada.**

| Decisão | Assumido | Revisar antes de |
|---------|----------|------------------|
| Autenticação | **Supabase Auth** (sem senha), verificado no servidor; sessão própria em cookie. Substituiu o link mágico próprio da 5A (não há servidor de e-mail). Google = nova opção no Supabase | — |
| Compartilhar cursos | privado por padrão, opção de publicar | 3C |
| Teoria/prática independentes | fora da v1 (turma combinada) | 4B |
| Optativas | "X créditos de uma lista" (`creditos_optativos_exigidos`); grupos de optativas depois | 2 |
| Provedor Postgres | **Supabase** (já traz Auth, reduz a 5A); Neon é alternativa válida | 5A |
| Framework | manter Flask + frontend vanilla | — |
| Banco | Postgres em produção, SQLite só em dev, via SQLAlchemy + Alembic | — |

## 7. Autenticação e acesso (Etapa 5A, revista na 5B)

- Fluxo: a tela `/entrar` fala com o Supabase Auth pelo navegador (`POST /auth/v1/otp` envia link+código; link volta em `/entrar#access_token=…`
  ou o código vai a `/auth/v1/verify`). O navegador entrega o token a `POST /api/auth/entrar`; o servidor o confere (`GET /auth/v1/user`,
  só e-mail **confirmado**), cria a conta se for nova e abre a sessão (cookie assinado do Flask). Depois disso o Supabase não é mais consultado.
- Camadas: regras puras em `domain/identidade.py`; `services/auth/` (Strategy `VerificadorDeToken`: `VerificadorSupabase` | `VerificadorDeDesenvolvimento`; fábrica por `AUTH_PROVEDOR`);
  HTTP/sessão/CSRF em `api/auth.py`, `api/sessao.py`, `api/origem.py`.
- Identidade do app = e-mail (sem `supabase_id`). Limite de envio de e-mails: do próprio Supabase (429 tratado na tela).
- Acesso a cursos: lê quem é dono ou se `visibilidade=publico`; **altera só o dono**; sem dono = invisível (comando `reivindicar-cursos`).
- Produção exige `SECRET_KEY`, `DATABASE_URL`, `SUPABASE_URL` (https), `SUPABASE_ANON_KEY` e `AUTH_PROVEDOR=supabase`; cookie `Secure`.

## 8. Dados do aluno (Etapa 5B-2)

- Histórico: N tentativas por disciplina (`historico`); a situação (concluída > cursando > reprovada) é derivada em `domain/historico.py`.
- Painel (`domain/painel.py`, `GET /api/cursos/<id>/painel`): status por disciplina, progresso e previsão; o front só desenha.
- Planos: guardados por usuário e curso; edição "documento inteiro" (`PUT` substitui os semestres). Plano/tentativa de outra conta = 404.
- Rotas do aluno ficam sob `/api/cursos/<id>/{historico,planos,painel}` e exigem login.
