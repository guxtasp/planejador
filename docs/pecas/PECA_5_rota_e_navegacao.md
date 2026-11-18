# Peça 5 — A rota: navegação na ordem de uso

## Problema
O menu agrupava por tipo de tela ("Dados" no fim), o app abria no Fluxograma e o Simulador não estava ligado.
Quem chegava não sabia por onde começar: o **Histórico**, que é o primeiro passo, ficava escondido.

## O que mudou (só o que o usuário vê; nenhum identificador interno foi renomeado)
| Item | Arquivo | Mudança |
|---|---|---|
| Menu em 3 blocos | `templates/index.html` | **Início** (Painel) · **Sua rota** (1 Histórico, 2 Planejamento, 3 Calendário, 4 Simulador) · **Mapas e dados** (Fluxograma, Disciplinas). Cada item tem subtítulo em linguagem comum |
| ✓ nos passos feitos | `core.js` (`atualizarRota`), `app.css` | o número do passo vira ✓ verde quando o passo está feito; Calendário aparece tracejado quando o curso não tem quadro de horários |
| Barra "Próximo passo" | `index.html`, `core.js`, `app.css` | rodapé que diz o que fazer agora e leva até lá; some na tela do próprio passo, no Painel e quando tudo está feito |
| Fonte única dos passos | `core.js` (`ROTA`) | menu, barra e cartão "Sua rota" do Painel leem da mesma lista (antes o cartão tinha 3 passos próprios) |
| Abertura | `core.js` | o app abre no **Painel**, não no Fluxograma |
| Textos | `core.js` (`DICAS_DE_PAGINA`), `inicio.html` | cada tela diz "Passo N de 4"; a tela inicial passa a ter 4 passos e cita o Simulador |
| Nome | — | **Rumo** foi mantido (Peça 2): o conceito de rota/paradas é o que justifica a navegação por passos |

Rotas, banco, API e nomes das telas (`Histórico`, `Planejamento`…) não mudaram; as mensagens do servidor que citam essas telas continuam corretas.

## Como atestar (no navegador)
1. Curso novo, sem histórico: abre no **Painel** com "Sua rota"; no menu os passos 1–4 sem ✓.
2. Abra **Planejamento**: no rodapé aparece "Próximo passo · 1 de 4 — Informe o que você já cursou".
3. Registre uma disciplina no Histórico: o passo 1 ganha ✓ e o rodapé passa a apontar o passo 2.
4. Monte um plano, escolha uma turma no Calendário e rode o Simulador: cada passo ganha ✓; no fim o rodapé some.
5. Curso sem quadro de horários: o passo 3 fica tracejado e é pulado no "próximo passo".
6. Celular (≤640px): barra de abas com os 7 itens, sem subtítulo; no tablet (≤900px) só ícones, com o número em miniatura.

## Atenção
- `tests/test_api_cursos.py` agora espera 7 telas no menu (inclui `simulador`).
- A lógica da rota foi conferida em Node com DOM simulado; o visual precisa de olho humano no navegador.
