// ═══════════════════════════════════════════════════════
// PAGE: MINHA ROTINA
// Tudo que é do ALUNO e vale para o resto do app: quando não pode ter aula, turno, dias livres,
// disciplinas pesadas, teto por período, trancamento, "cursar junto", optativas e prazo.
// Antes ficava escondido dentro do Simulador; agora é um passo (opcional) da rota.
// O formulário é o mesmo do Fase 2 (`desenharPreferencias`, em page_simulador.js); aqui só muda o lugar.
// ═══════════════════════════════════════════════════════
function rotina() {
  document.getElementById('topbar-actions').innerHTML = '';
  SIM.prefAberto = true;
  SIM.pref = null;                       // relê do servidor (pode ter mudado em outra tela)
  document.getElementById('content').innerHTML = `
    <div class="rotina-cabeca">
      <p>Conte como é a sua semana e o seu ritmo. O Rumo usa isso para escolher turmas no Planejamento,
        para montar a Sugestão e no Simulador. Nada aqui é obrigatório.</p>
      ${rotinaPreenchida() || rotinaPulada() ? '' : '<button class="btn btn-ghost btn-sm" onclick="pularRotina()">Pular por agora</button>'}
    </div>
    <div id="rotina-veredito" aria-live="polite"></div>
    <div id="sim-juntas"></div>
    <div id="sim-pref" class="rotina-pagina"></div>`;
  desenharPreferencias();
  desenharPerguntaJuntas();
  desenharVereditoRotina();
}
