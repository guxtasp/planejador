# Peça 2 — Rebranding (Rumo) e primeira vez sem confusão

## O que foi feito

**Marca nova: Rumo** ("do primeiro período ao diploma, sem surpresa"). Conceito: o curso é uma rota; cada período é uma parada; o diploma (âmbar) é o destino.

| Item | Arquivo | Mudança |
|---|---|---|
| Logo | `static/img/rumo.svg` (novo; `trilha.svg` removido) | rota pontilhada com ponto de partida e destino âmbar |
| Cores | `static/css/tokens.css` | cor da marca passa de azul para **índigo** (`--accent`), claro e escuro. As cores de **estado** (verde = concluída, amarelo = cursando, roxo = planejada, vermelho = conflito) não mudaram |
| Tela inicial | `templates/inicio.html` | reescrita: abertura com promessa, botão certo para cada situação (visitante / logado sem curso / com curso), bloco **"Como funciona"** em 3 passos, **"Dúvidas rápidas"** (senha, privacidade, sem CSV, o que é par/ímpar) |
| Login | `templates/entrar.html`, `static/css/telas_simples.css` | marca nova, frase que explica o método de entrada disponível, bloco **"Por que entrar?"**, dica "Não chegou? veja o spam" |
| Confirmar entrada | `templates/entrar_confirmar.html` | marca nova e texto que explica *por que* existe o clique extra |
| App | `templates/index.html`, `importacao.html`, `core.js` | nome e logo novos na barra lateral, abas e título |
| Explicabilidade | `core.js` (`DICAS_DE_PAGINA`), `app.css` | uma frase sob o título de cada tela: o que ela mostra e o que fazer |
| Primeira vez | `page_dashboard.js` | cartão **"Primeiros passos"** (curso → histórico → plano), com botão para o próximo; some quando tudo está feito |
| Estados vazios | `page_planner.js`, `page_historico.js`, `page_calendario.js`, `page_fluxograma.js` | dizem o que é, por que está vazio e o que fazer |

Nenhum identificador interno foi renomeado (rotas, banco, variáveis): só o que o usuário vê.

## Como atestar (no navegador)

1. `flask --app planner run --debug`, abra `/` **deslogado**: deve aparecer a promessa, "Entrar e começar", os 3 passos e as dúvidas.
2. Clique em Entrar: a tela de login traz a marca nova, a frase do método e "Por que entrar?".
3. Entre e abra um curso **sem histórico**: o Dashboard mostra "Primeiros passos" com o passo 2 destacado; sob o título aparece a frase da tela.
4. Vá em Planejamento sem plano: o texto explica o que é um plano. Faça o mesmo em Histórico e Calendário.
5. Teste o modo escuro do sistema (o índigo muda de tom) e a largura de celular (a dica sob o título some; o resto empilha).

## Atenção

- Os textos da tela inicial prometem **só o que existe hoje** (pré-requisito, choque de horário, créditos). O simulador de futuro entra na Peça 3, e então o texto é atualizado.
- Os testes não foram executados por mim, como combinado. Nada de Python mudou nesta peça, só templates, CSS e JS.

## Próxima fase (Peça 3): simulador de futuro

- Serviço + endpoint que **simula o plano que você já montou** semestre a semestre, com calendário real (`2027/1`, `2027/2`…): oferta par/ímpar, pré-requisitos, carga de créditos e conflitos de horário (projetando os horários do último período de mesma paridade).
- Resultado em **blocos** na tela (resumo, riscos, o que acontece se reprovar em X, caminho crítico), usando `domain/grafo.py` e `domain/alocacao.py`, que já estão no projeto.
- Depois, Peça 4: sugestão de plano otimizada (grafos + recozimento simulado).
