# Importação de cursos por CSV

Qualquer curso entra no planejador por arquivos CSV. O fluxo é sempre: **validar (prévia, nada é gravado) → confirmar**.
Tela: `/importar`. API: `POST /api/importacao/validar` e `POST /api/importacao/confirmar`.

## De onde vêm os dados? (guia por fonte)

Você não precisa ter tudo de uma vez. Cada fonte alimenta arquivos diferentes, e dá para combiná-las:

| Fonte | O que ela costuma ter | Arquivos que você gera |
|-------|----------------------|------------------------|
| **Matriz curricular (PPC)** | disciplinas, créditos, carga horária, período, pré/correquisitos | `curso.csv`, `disciplinas.csv`, `requisitos.csv` |
| **Quadro de horários** (oferta do período) | turmas, docentes, vagas, dias/horários, salas | `turmas.csv` (uma linha por turma) |
| **Sites institucionais** (curso, departamento, catálogo) | um pouco de tudo, de forma desigual | o que a IA encontrar; ementas não têm coluna |

**Como combinar:** importe a **matriz primeiro**; depois o **quadro de horários de cada período**, um de cada vez. Turmas só exigem que a
disciplina já exista (neste curso ou no mesmo envio), e a importação é upsert: um quadro novo cria as turmas novas e atualiza as que mudaram,
sem apagar as de outros períodos. Para cada fonte há um prompt de IA próprio (`GET /api/importacao/prompt-ia?fonte=matriz|horarios|web`).

## Os arquivos

Só `disciplinas.csv` é indispensável. Para **criar** um curso, envie também `curso.csv` (ou indique um curso existente com `curso_id`).
Os nomes das colunas ignoram caixa e acento. Os modelos para download têm o cabeçalho completo e uma linha de exemplo
(`GET /api/importacao/modelos/<arquivo>` ou botões na tela). Referência completa de colunas e formatos: `docs/ARQUITETURA.md §5`.

| Arquivo | Para quê | Obrigatórias |
|---------|----------|--------------|
| `curso.csv` (1 linha) | dados do curso | nome |
| `disciplinas.csv` | matriz curricular | codigo, nome, tipo |
| `requisitos.csv` | pré/correquisitos | disciplina, requisito, tipo |
| `turmas.csv` | oferta de um período | disciplina, periodo_letivo, codigo_turma |

`disciplinas.csv` aceita ainda **`periodicidade`**: `sempre` (todo período), `impar` (só `AAAA/1`) ou `par` (só `AAAA/2`).
**Toda disciplina deve ter `periodicidade`.** Vazio continua sendo "desconhecido" (nunca vira `sempre`; o simulador estima pela paridade
do período sugerido e marca como estimativa), mas a validação mostra um aviso com a lista do que falta, e a tela **Disciplinas** exibe um alerta.
A validação também avisa quando uma disciplina `par`/`impar` tem turma num período de outra paridade (`2026/1` é ímpar, `2026/2` é par).
Como preencher: disciplina com turma só em `AAAA/1` → `impar`; só em `AAAA/2` → `par`; nos dois → `sempre`; sem turma no quadro → deixe vazio
até saber. Apelidos aceitos na coluna: `oferta`, `paridade`.

`turmas.csv` aceita ainda `docente`, `vagas`, `horarios` e **`local`** (sala; vale para todos os encontros da turma).
O **histórico do aluno não entra por CSV**: ele será informado dentro do app (o que você já cursou é pessoal, não do curso).

Regras de ouro:
- **Vazio = desconhecido.** Nunca escreva `0`, `N/A` ou `-` para "não sei". (`0` explícito é preservado.)
- `tipo` da disciplina e `codigo_turma` **não têm padrão**: vazios são erro.
- Horários: `SEG 16:00-18:00 | QUI 14:00-16:00` — o `|` separa encontros da MESMA turma; alternativas de matrícula são linhas diferentes.
- Requisito "A ou B": mesmo `grupo_alt` nas linhas alternativas; sem grupo = todos obrigatórios.

## O que a validação confere

**Erros** (a linha é descartada e a importação não pode ser confirmada até corrigir):
- schema: coluna obrigatória ausente, valor fora do vocabulário, número/horário/período inválido;
- chave repetida no arquivo com valores diferentes (disciplina, requisito, turma);
- requisito ou turma apontando para disciplina que não existe neste curso;
- pré-requisitos circulares (A exige B, B exige A);
- encontros da mesma turma que se sobrepõem.

**Avisos** (importa, mas confira):
- linha repetida e idêntica; código que só difere na caixa do já cadastrado;
- pré-requisito em período igual ou posterior ao da disciplina; ciclo que passa por "A ou B"; grupo "A ou B" com uma só disciplina;
- créditos × carga horária fora de 10–20 h por crédito; período sugerido acima da duração do curso;
- mudança de `tipo` de disciplina já cadastrada; turma sem horários.

## Como a importação grava (upsert)

- Chaves: curso = nome · disciplina = código · requisito = (disciplina, requisito, tipo) · turma = (disciplina, período, código da turma).
- Registro novo é criado; existente com valores diferentes é atualizado; igual fica como está. A prévia mostra cada mudança (antes → depois).
- Excluir um curso é pela tela inicial (botão **Excluir**, só para o dono) ou `DELETE /api/cursos/<id>`: apaga disciplinas, turmas, planos e o histórico dele. Recusa (409) se outra conta tem histórico no curso.
- **Célula vazia nunca apaga** um valor já gravado, e **o que não está no arquivo é mantido** (a importação nunca remove).
- Tudo numa única transação: se algo falhar, nada é gravado.
- Códigos são comparados sem caixa/acento; `inf110` é a mesma disciplina que `INF110`.
- Enviar `historico.csv` é um erro orientado: o histórico não faz parte da importação.
- O curso criado é **privado** por padrão (campo `visibilidade` = `publico` para publicar).

## API (multipart/form-data)

Envie cada CSV como campo de arquivo cujo **nome de arquivo** é o do formato (`disciplinas.csv`…). Campos opcionais: `curso_id`, `visibilidade`.

- `validar` → `{"ok": true, "previa": {pode_confirmar, totais, arquivos[itens], issues[]}}`
- `confirmar` → 201 (curso criado) ou 200, com `{"relatorio": {curso_id, por_arquivo, avisos}}`;
  422 com `detalhes` (a prévia) se houver erros ou nada a gravar. Limite de upload: 5 MB.

## Gerando os CSVs com uma IA

Na tela `/importar` (ou `GET /api/importacao/prompt-ia?fonte=...`) há um prompt pronto para cada fonte (`matriz`, `horarios`, `web`):
cole-o numa IA junto com o documento (ou os links). Todos mandam a IA **não inventar** dados e deixar vazio o que a fonte não traz;
o de sites institucionais pede ainda a **URL de cada dado duvidoso**. Sempre revise a prévia antes de confirmar.
