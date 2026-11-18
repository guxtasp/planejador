// ═══════════════════════════════════════════════════════
// PAGE: FLUXOGRAMA
// O status de cada disciplina vem do painel do servidor (S.situacoes), calculado
// com o histórico do aluno; aqui só se desenha.
// ═══════════════════════════════════════════════════════
const STATUS_FLUXO = {      // situação do servidor → classe CSS / rótulo / selo
  concluida: {css: 'aprovado',   rotulo: '✓ Concluída',  selo: 'badge-green'},
  cursando:  {css: 'cursando',   rotulo: '● Cursando',   selo: 'badge-yellow'},
  elegivel:  {css: 'disponivel', rotulo: '↗ Disponível', selo: 'badge-accent'},
  bloqueada: {css: 'bloqueada',  rotulo: '🔒 Bloqueada', selo: 'badge-gray'},
  planejada: {css: 'planejada',  rotulo: '◉ Planejada',  selo: 'badge-purple'},
};

function fluxograma() {
  const plannedIds = getPlannedIds();

  const byPeriod = {};
  // Disciplinas sem período sugerido (ex.: optativas) vão para a última coluna.
  S.disciplinas.forEach(d => {
    const chave = d.periodo == null ? 'sem' : d.periodo;
    if (!byPeriod[chave]) byPeriod[chave] = [];
    byPeriod[chave].push(d);
  });

  const c = document.getElementById('content');
  const semHistorico = S.historico.length === 0;
  c.innerHTML = `
  ${semHistorico ? `<div class="hint" style="margin-bottom:16px;display:flex;align-items:center;gap:12px;font-size:12px;color:var(--text3)">
    Você ainda não informou o histórico, então nada aparece como concluído.
    <button class="btn btn-primary btn-sm" onclick="irPara('historico')">+ Informar histórico</button></div>` : ''}
  <div class="legend" style="margin-bottom:16px">
    <div class="legend-item"><div class="legend-dot" style="background:var(--green)"></div>Concluída</div>
    <div class="legend-item"><div class="legend-dot" style="background:var(--yellow)"></div>Cursando</div>
    <div class="legend-item"><div class="legend-dot" style="background:var(--accent)"></div>Disponível</div>
    <div class="legend-item"><div class="legend-dot" style="background:var(--purple)"></div>Planejada</div>
    <div class="legend-item"><div class="legend-dot" style="background:var(--text3)"></div>Bloqueada</div>
  </div>
  <div id="fluxo-wrap">
    <div class="fluxo-grid">
      ${Object.entries(byPeriod).sort((a,b)=>(a[0]==='sem'?1e9:+a[0])-(b[0]==='sem'?1e9:+b[0])).map(([p, discs]) => {
        // Estação do período: verde = tudo concluído, amarela = há disciplina em curso.
        const sits = discs.map(d => situacaoDe(d.id)?.situacao);
        const estado = sits.length && sits.every(x => x === 'concluida') ? 'feito' : sits.includes('cursando') ? 'atual' : '';
        return `
        <div class="fluxo-col ${estado}">
          <div class="fluxo-period-label"><span class="estacao"></span>${p === 'sem' ? 'Sem período' : esc(p) + 'º período'}</div>
          ${discs.map(d => {
            const sit = situacaoDe(d.id);
            let chave = sit ? sit.situacao : null;
            // "Planejada" só vale para o que ainda não foi feito nem está bloqueado.
            if (chave === 'elegivel' && plannedIds.has(d.id)) chave = 'planejada';
            const st = STATUS_FLUXO[chave] || null;
            const dica = sit?.pendencias?.length ? sit.pendencias.map(textoPendenciaPainel).join('; ') : '';

            return `<div class="fluxo-disc status-${st ? st.css : 'neutro'}" onclick="showDiscDetail(${d.id})" data-id="${d.id}" ${dica ? `title="${esc(dica)}"` : ''}>
              <div class="fd-code">${esc(d.codigo)}</div>
              <div class="fd-name" style="color:${chave==='bloqueada'?'var(--text3)':'var(--text)'}">${esc(d.nome)}</div>
              <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:4px">
                ${st ? `<span class="badge ${st.selo} fd-badge" style="font-size:9px">${st.rotulo}</span>` : ''}
                ${sit?.reprovada_antes ? '<span class="badge badge-red" style="font-size:9px">↻ Reprovada</span>' : ''}
                <span class="tag" style="font-size:9px">${credStr(d.creditos)}</span>
              </div>
            </div>`;
          }).join('')}
        </div>
      `;}).join('')}
    </div>
  </div>
  `;
}
