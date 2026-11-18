# Peça 1 — Periodicidade da disciplina (par / ímpar / sempre)

## O que foi feito

**Regra adotada:** a paridade é a do **número do período** no ano. `2026/1` é ímpar, `2026/2` é par.
- `impar`: só existe em `AAAA/1` · `par`: só em `AAAA/2` · `sempre`: todo período.
- **Vazio = desconhecido** (segue a regra de ouro do projeto). Nunca é gravado como "sempre".

| Camada | Arquivo | Mudança |
|---|---|---|
| Vocabulário | `planner/models/enums.py` | enum `Periodicidade` |
| Banco | `planner/models/disciplina.py` | coluna `periodicidade` (nullable) + CHECK |
| Migração | `migrations/versions/d6f2a3b8c915_periodicidade_disciplina.py` | nova, depois de `c5e8f1a2b704` |
| Importação | `planner/importers/disciplinas.py`, `registros.py`, `modelos.py` | coluna opcional `periodicidade` (apelidos: `oferta`, `paridade`; aceita "ímpar", "2º semestre", "todo semestre"…) |
| Prévia/commit | `validacao/estado.py`, `validacao/previa.py`, `services/previa_importacao.py`, `services/importacao.py` | a coluna entra no diff e na gravação |
| API | `services/cursos.py` | `GET /api/cursos/<id>/disciplinas` devolve `periodicidade` |
| Domínio | `domain/entidades.py`, `services/catalogo_dominio.py` | `Disciplina.periodicidade` |
| Domínio (novo) | `domain/periodicidade.py` | `ofertada_em`, `proximo_periodo_ofertado`, `periodicidade_efetiva` (cadastrada / **estimada** pelo período sugerido / desconhecida), `turmas_para_periodo` (projeta horários do último período de mesma paridade) |
| Tela | `core.js`, `page_disciplinas.js`, `page_planner.js`, `disc_detalhe.js` | selo de oferta na tabela, no detalhe e na paleta do planejador |
| Docs | `docs/IMPORTACAO.md`, prompt de IA | coluna documentada |
| Testes | `tests/test_periodicidade.py` | domínio, importador, CHECK do banco |

Já adiantados para as próximas peças (ainda **não ligados** a nenhuma tela): `domain/grafo.py` (grafo de dependências + caminho crítico com calendário) e `domain/alocacao.py` (escolha de turmas sem colisão no semestre).

## Como atestar

1. `pip install -r requirements-dev.txt && pytest` (deve passar; os 622 testes antigos + `test_periodicidade.py`).
2. `flask --app planner db upgrade` (aplica `d6f2a3b8c915`).
3. Importe um `disciplinas.csv` com a coluna `periodicidade` (ex.: `INF110,Programação I,obrigatoria,...,impar`) e abra **Disciplinas**: deve aparecer o selo "Só ímpar".
4. Sem a coluna, o selo mostra **"Oferta não informada"** (não "sempre").

## Atenção

- O CSV de exemplo (`examples/ciencia-da-computacao`) **não** foi alterado: não inventei oferta real. O simulador vai *estimar* pela paridade do período sugerido e marcar como "estimada".
- Hoje a oferta só entra por **CSV**. Não há edição na tela (o catálogo inteiro é assim).

## Próxima fase (Peça 2): rebranding + onboarding claro

- Novo nome e símbolo; reescrever a **tela inicial** e a **tela de login** (`inicio.html`, `entrar.html`, `entrar_confirmar.html`) e a marca na barra lateral.
- Explicabilidade na primeira vez: passo a passo "1 Trazer curso → 2 Informar o que já cursou → 3 Planejar", estados vazios que dizem o que fazer, textos de login que explicam *por que* só pede e-mail.
- Depois: Peça 3 (simulador de futuro) e Peça 4 (sugestão otimizada com grafos + recozimento simulado).
