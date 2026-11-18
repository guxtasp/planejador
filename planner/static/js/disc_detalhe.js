// ═══════════════════════════════════════════════════════
// DISC DETAIL MODAL
// ═══════════════════════════════════════════════════════
function showDiscDetail(id) {
  const d = S.disciplinas.find(x=>x.id===id);
  if (!d) return;

  const sit = situacaoDe(id);
  const tentativas = S.historico.filter(x => x.disciplina_id === id);
  const aprovados = getAprovados();
  const cursando = getCursando();

  const prereqs = (d.prerequisitos||[]).filter(p=>p.tipo==='pre');
  const coreqs = (d.prerequisitos||[]).filter(p=>p.tipo==='co');

  const rotuloSituacao = {concluida: '✅ Concluída', cursando: '⏳ Cursando', elegivel: '↗ Disponível', bloqueada: '🔒 Bloqueada'};
  const statusLabel = sit ? rotuloSituacao[sit.situacao] : '–';
  const cor = esc(d.cor);

  openModal(`
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">
      <div style="width:48px;height:48px;border-radius:10px;background:rgba(${hexToRgb(d.cor)},.2);border:2px solid ${cor};display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;color:var(--text)">${esc(d.codigo.slice(0,4))}</div>
      <div>
        <div style="font-size:11px;color:var(--text3);font-weight:700;letter-spacing:.06em">${esc(d.codigo)}</div>
        <h2 style="margin-bottom:2px;font-size:17px">${esc(d.nome)}</h2>
        <div style="font-size:12px;color:var(--text2)">${periodStr(d.periodo)} · ${periodicidadeBadge(d.periodicidade)}</div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px">
      <div class="card card-sm" style="text-align:center">
        <div class="stat-label">Créditos</div>
        <div style="font-size:20px;font-weight:700">${valorOu(d.creditos)}</div>
      </div>
      <div class="card card-sm" style="text-align:center">
        <div class="stat-label">Carga H.</div>
        <div style="font-size:20px;font-weight:700">${valorOu(d.carga_h, 'h')}</div>
      </div>
      <div class="card card-sm" style="text-align:center">
        <div class="stat-label">Status</div>
        <div style="font-size:12px;margin-top:4px">${statusLabel}</div>
      </div>
    </div>
    ${tentativas.length ? `<div class="form-group">
      <label class="form-label">Tentativas</label>
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        ${tentativas.map(t => `<span class="badge ${STATUS_HIST[t.status].cls}">${STATUS_HIST[t.status].rotulo}${t.periodo_letivo ? ' · ' + esc(t.periodo_letivo) : ''}${t.nota != null ? ' · ' + esc(t.nota) : ''}</span>`).join('')}
      </div>
    </div>` : ''}
    ${renderTurmasOfertadas(d.id)}
    ${prereqs.length ? `<div class="form-group">
      <label class="form-label">Pré-requisitos</label>
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        ${prereqs.map(p=>{
          const ok = aprovados.has(p.id);
          return `<span class="badge ${ok?'badge-green':'badge-red'}" style="cursor:pointer" onclick="closeModal();showDiscDetail(${p.id})">${ok?'✓':''} ${esc(p.codigo)}</span>`;
        }).join('')}
      </div>
    </div>` : ''}
    ${coreqs.length ? `<div class="form-group">
      <label class="form-label">Correquisitos</label>
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        ${coreqs.map(p=>{
          const ok = aprovados.has(p.id)||cursando.has(p.id);
          return `<span class="badge ${ok?'badge-yellow':'badge-red'}" style="cursor:pointer" onclick="closeModal();showDiscDetail(${p.id})">${esc(p.codigo)}</span>`;
        }).join('')}
      </div>
    </div>` : ''}
    ${sit?.situacao === 'bloqueada' ? `<div class="alert alert-red">
      <span>🔒</span>
      <div><strong>Disciplina bloqueada</strong><br>${sit.pendencias.map(p => esc(textoPendenciaPainel(p))).join('<br>')}</div>
    </div>` : ''}
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal()">Fechar</button>
      ${sit?.situacao !== 'concluida' ? `<button class="btn btn-primary" onclick="closeModal();historicoModal({disciplinaId:${d.id}})">+ Adicionar ao histórico</button>` : ''}
    </div>
  `);
}

// Turmas ofertadas (todas as épocas com oferta), agrupadas por período letivo.
function renderTurmasOfertadas(discId) {
  const turmas = turmasDaDisciplina(discId);
  if (!turmas.length) return '';
  const porPeriodo = {};
  turmas.forEach(t => (porPeriodo[t.periodo_letivo] = porPeriodo[t.periodo_letivo] || []).push(t));
  return `<div class="form-group">
    <label class="form-label">Turmas ofertadas</label>
    ${Object.keys(porPeriodo).sort().map(p => `
      <div style="margin-bottom:6px"><span style="font-size:11px;color:var(--text3);font-weight:700">${esc(p)}</span>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:3px">
          ${porPeriodo[p].map(t => `<span class="badge badge-blue" title="${esc(t.docente || '')}">${esc(turmaRotulo(t))}</span>`).join('')}
        </div></div>`).join('')}
  </div>`;
}
