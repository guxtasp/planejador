# DIAGNÓSTICO DO APP ORIGINAL

Fonte: `legacy/app_legacy.py` (776 linhas, Flask + sqlite3) e `index.html` (1427 linhas, SPA vanilla).

## Defeitos estruturais (cobertos por `tests/test_characterization_legacy.py`)

| # | Problema | Onde | Corrigido em |
|---|----------|------|--------------|
| 1 | Single-user; histórico e planos globais | todas as tabelas | 5B |
| 2 | SQLite em arquivo local não funciona na Vercel | `DB_PATH` | 6 |
| 3 | Apagar disciplina apaga histórico (`ON DELETE CASCADE`) | schema | 1A |
| 4 | 1 registro de histórico por disciplina (sem reprovação→aprovação) | `add_historico` | 2 / 5B |
| 5 | Pré-requisito só olha histórico, ignora semestres anteriores do plano | `check_prereqs` | 2 |
| 6 | Só AND; sem "A ou B" nem requisito por créditos | `prerequisitos` | 1A / 2 |
| 7 | Consultas N+1 | `/api/disciplinas`, `/api/planos`, `check_horario_conflict` | 1B |
| 8 | `debug=True`, `host=0.0.0.0`, CORS aberto | `__main__` | 6 |
| 9 | Histórico do seed usa códigos inexistentes (nasce vazio); README diz 40 disciplinas, são 49 | `_seed_if_empty` | 1B |

## Regras acopladas ao curso

| Hardcoded | Substituto |
|-----------|-----------|
| `creditos > 28` = sobrecarga | `curso.max_creditos_semestre` |
| `media_cred_sem = 20` | média do próprio aluno + fallback configurável |
| total = soma de todas as disciplinas | obrigatórias + optativas até o exigido |
| optativas = "período 9" | `disciplina.tipo` |
| dias SEG–SEX, grade 07–22h | derivada dos encontros |
| `periodStr` até 10º | derivado de `duracao_semestres` / dados |
| `getMonth() < 6` na previsão | calendário por `periodo_letivo` |
| horário sem semestre | `turma.periodo_letivo` |

## Contrato da API legada (o frontend depende dele; migrar mantendo formato quando possível)

`GET/POST /api/disciplinas`, `PUT/DELETE /api/disciplinas/<id>` ·
`GET/POST /api/historico`, `DELETE /api/historico/<id>` ·
`GET/POST /api/planos`, `DELETE /api/planos/<id>`, `POST /api/planos/<id>/semestres` ·
`POST /api/semestres/<id>/disciplinas`, `DELETE /api/semestres/<id>/disciplinas/<disc_id>` ·
`GET /api/assistente`, `GET /api/validar_semestre/<id>`

## Mapa do frontend (`index.html`)

Estado global `S`; helpers `GET/POST/PUT/DEL`; páginas: `dashboard`, `planner` (drag-and-drop),
`fluxograma`, `calendario`, `historico`, `disciplinas`. Constantes de curso a remover no JS:
`periodStr`, dias fixos, faixa 07–22h, previsão de formatura.
