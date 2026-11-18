// ═══════════════════════════════════════════════════════
// PAGE: DASHBOARD
// Tudo vem do painel do servidor (S.painel): progresso, previsão e status por
// disciplina. Aqui só se formata; desconhecido (null) aparece como "–", nunca como 0.
// ═══════════════════════════════════════════════════════
function textoPrevisao(prev, concluido) {
  if (concluido) return {valor: '🎓', sub: 'Curso concluído'};
  const n = prev.semestres_restantes;
  const origem = prev.origem_media === 'aluno' ? 'sua média' : prev.origem_media === 'curso' ? 'média do curso' : null;
  const sub = n == null ? '–' : `${n} semestre${n === 1 ? '' : 's'}${origem ? ` · ${origem}` : ''}`;
  return {valor: valorOu(prev.formatura), sub};
}

function dashboard() {
  const c = document.getElementById('content');
  const p = S.painel;
  if (!p) {
    c.innerHTML = `<div class="empty">Não foi possível carregar seu painel.<br>
      <button class="btn btn-primary" onclick="navTo('dashboard',document.querySelector('.nav-item[data-page=dashboard]'))">Tentar de novo</button></div>`;
    return;
  }
  const pg = p.progresso;
  const pct = pg.percentual;
  const prev = textoPrevisao(p.previsao, pg.concluido);
  const semHistorico = S.historico.length === 0;

  const porStatus = situacao => p.disciplinas.filter(d => d.situacao === situacao)
    .map(d => ({...S.disciplinas.find(x => x.id === d.id), painel: d})).filter(d => d.id != null);
  const elegiveis = porStatus('elegivel');
  const bloqueadas = porStatus('bloqueada');

  c.innerHTML = `
  ${semHistorico ? `<div class="hint" style="margin-bottom:16px;display:flex;align-items:center;gap:12px;font-size:12px;color:var(--text3)">
    Os números abaixo partem de um histórico vazio.
    <button class="btn btn-primary btn-sm" onclick="irPara('historico')">Informar histórico</button></div>` : ''}
  <div class="grid-4" style="margin-bottom:20px">
    <div class="stat-card">
      <div class="stat-label">Progresso Geral</div>
      <div class="stat-value">${pct == null ? '–' : pct + '%'}</div>
      <div class="progress-bar"><div class="progress-fill" style="width:${pct == null ? 0 : pct}%"></div></div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Créditos</div>
      <div class="stat-value">${pg.creditos_validos}</div>
      <div class="stat-sub">de ${valorOu(pg.creditos_exigidos)} exigidos</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Previsão de Formatura</div>
      <div class="stat-value" style="font-size:22px">${esc(prev.valor)}</div>
      <div class="stat-sub">${esc(prev.sub)}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Disciplinas</div>
      <div class="stat-value">${p.resumo.disciplinas_concluidas}</div>
      <div class="stat-sub">de ${p.resumo.total_disciplinas} concluídas</div>
    </div>
  </div>

  <div class="grid-2" style="margin-bottom:20px">
    ${blocoLista('Disciplinas Elegíveis', 'var(--green)', elegiveis, 'Nenhuma disciplina elegível no momento',
      d => ({dot: esc(d.cor), meta: `${esc(d.codigo)} · ${periodStr(d.periodo)} · ${credStr(d.creditos)}`, selo: '<span class="badge badge-green">Elegível</span>'}))}
    ${blocoLista('Disciplinas Bloqueadas', 'var(--red)', bloqueadas, 'Nenhuma disciplina bloqueada!',
      d => ({dot: 'var(--red)', meta: `${esc(d.codigo)} · ${esc(d.painel.pendencias.map(textoPendenciaPainel).join('; '))}`, selo: '<span class="badge badge-red">Bloqueada</span>'}))}
  </div>

  <div class="card">
    <div style="font-size:13px;font-weight:700;margin-bottom:14px">📊 Distribuição por Período</div>
    <div style="display:flex;gap:16px;overflow-x:auto;padding-bottom:8px">
      ${renderPeriodBars()}
    </div>
  </div>
  `;
}

// Cartão com até 6 disciplinas; `linha(d)` devolve {dot, meta, selo} já escapados.
function blocoLista(titulo, corPonto, lista, vazio, linha) {
  return `<div class="card">
    <div style="font-size:13px;font-weight:700;margin-bottom:14px;display:flex;align-items:center;gap:8px">
      <span style="color:${corPonto}">●</span> ${esc(titulo)} (${lista.length})
    </div>
    ${lista.length === 0 ? `<div class="empty">${esc(vazio)}</div>` : lista.slice(0, 6).map(d => {
      const l = linha(d);
      return `<div class="disc-list-item" onclick="showDiscDetail(${d.id})">
        <div class="dli-dot" style="background:${l.dot}"></div>
        <div class="dli-info">
          <div class="dli-nome">${esc(d.nome)}</div>
          <div class="dli-meta">${l.meta}</div>
        </div>
        ${l.selo}
      </div>`;
    }).join('')}
    ${lista.length > 6 ? `<div style="font-size:12px;color:var(--text3);margin-top:8px;text-align:center">+${lista.length - 6} mais</div>` : ''}
  </div>`;
}

function renderPeriodBars() {
  const planejadas = getPlannedIds();
  const grupos = {};
  S.disciplinas.forEach(d => {
    const chave = d.periodo == null ? 'sem' : d.periodo;
    const g = grupos[chave] = grupos[chave] || {total: 0, concluidas: 0, cursando: 0, planejadas: 0};
    g.total++;
    const sit = situacaoDe(d.id)?.situacao;
    if (sit === 'concluida') g.concluidas++;
    else if (sit === 'cursando') g.cursando++;
    else if (planejadas.has(d.id)) g.planejadas++;
  });
  return Object.entries(grupos).sort((a, b) => (a[0] === 'sem' ? 1e9 : +a[0]) - (b[0] === 'sem' ? 1e9 : +b[0])).map(([p, g]) => {
    const pct = Math.round(g.concluidas / g.total * 100);
    return `<div style="min-width:60px;text-align:center">
      <div style="font-size:10px;color:var(--text3);margin-bottom:6px">${p === 'sem' ? '–' : esc(p) + 'º'}</div>
      <div style="height:80px;width:40px;background:var(--bg4);border-radius:4px;margin:0 auto;position:relative;overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end">
        ${g.cursando > 0 ? `<div style="height:${g.cursando / g.total * 100}%;background:#f59e0b;opacity:.8"></div>` : ''}
        <div style="height:${pct}%;background:var(--green);opacity:.9"></div>
      </div>
      <div style="font-size:11px;color:var(--text);margin-top:4px">${pct}%</div>
      <div style="font-size:10px;color:var(--text3)">${g.concluidas}/${g.total}</div>
    </div>`;
  }).join('');
}
