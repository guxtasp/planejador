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
        <div style="font-size:12px;color:var(--text2)">${periodStr(d.periodo)} · ${seloOferta(d)}</div>
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
    ${grupoDe(d.id) ? `<div class="sim-nota">Cursar junto com ${grupoDe(d.id).disciplinas.filter(x => x !== d.id).map(x => esc(S.disciplinas.find(y => y.id === x)?.codigo || x)).join(', ')}
      <button class="btn btn-ghost btn-sm" onclick="desfazerJunto(${d.id})">Desfazer</button></div>` : ''}
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal()">Fechar</button>
      ${S.podeEditarCatalogo ? `<button class="btn btn-ghost" onclick="closeModal(); editarDisciplina(${d.id})">✏️ Editar dados</button>` : ''}
      ${sit?.situacao !== 'concluida' && !grupoDe(d.id) ? `<button class="btn btn-ghost" onclick="cursarJuntoCom(${d.id})">Cursar junto com…</button>` : ''}
      ${sit?.situacao !== 'concluida' ? `<button class="btn btn-ghost" onclick="cursarEmPeriodo(${d.id})">Cursar em um período…</button>` : ''}
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


// "Cursar junto com…": a pessoa escolhe a outra disciplina; vira um grupo obrigatório (editável em Preferências).
function cursarJuntoCom(discId) {
  const d = S.disciplinas.find(x => x.id === discId);
  const outras = S.disciplinas.filter(x => x.id !== discId && !['concluida'].includes(situacaoDe(x.id)?.situacao) && !grupoDe(x.id));
  openModal(`<h2>Cursar ${esc(d.codigo)} junto com…</h2>
    <p class="sim-texto">As duas ficam no mesmo semestre na sugestão, e o Simulador avisa se estiverem separadas.</p>
    <label class="form-label" for="junto-outra">Outra disciplina</label>
    <select class="form-select" id="junto-outra">${outras.map(x => `<option value="${x.id}">${esc(x.codigo)} · ${esc(x.nome)}</option>`).join('')}</select>
    <div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="confirmarJunto(${discId})">Cursar juntas</button></div>`);
}
async function confirmarJunto(discId) {
  const outra = Number(document.getElementById('junto-outra').value);
  const juntas = [...(S.preferencias?.juntas || []), {disciplinas: [discId, outra], regra: 'obrigatoria'}];
  if (await salvarPreferencias({juntas, juntas_respondida: true})) {
    closeModal();
    toast('Pronto: as duas vão juntas. Dá para desfazer em Preferências ou no detalhe da disciplina.', 'success', 4000);
    if (typeof render === 'function') render();
  }
}
async function desfazerJunto(discId) {
  const antes = S.preferencias?.juntas || [];
  if (await salvarPreferencias({juntas: antes.filter(g => !g.disciplinas.includes(discId))})) {
    closeModal();
    toastAcao('Grupo desfeito.', 'Desfazer', () => salvarPreferencias({juntas: antes}).then(() => render()));
    render();
  }
}


// "Cursar em um período…": a sugestão põe a disciplina nesse período (se abrir e os requisitos deixarem).
function cursarEmPeriodo(discId) {
  const d = S.disciplinas.find(x => x.id === discId);
  const atual = (S.preferencias?.fixas || []).find(f => f.disciplina_id === discId)?.periodo || '';
  openModal(`<h2>Cursar ${esc(d.codigo)} em…</h2>
    <p class="sim-texto">${esc(d.nome)}. ${seloOferta(d)} A sugestão de plano vai respeitar; o Simulador avisa se o seu plano não respeitar.</p>
    <label class="form-label" for="fixa-periodo">Período</label>
    <select class="form-select" id="fixa-periodo">${periodosSugeridos(12).map(p =>
      `<option ${p === atual ? 'selected' : ''} ${abreEm(ofertaDe(d), p) ? '' : 'disabled'}>${p}${abreEm(ofertaDe(d), p) ? '' : ' (não abre)'}</option>`).join('')}</select>
    <div class="modal-footer">
      ${atual ? `<button class="btn btn-danger" style="margin-right:auto" onclick="salvarFixa(${discId}, null)">Tirar o pedido</button>` : ''}
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="salvarFixa(${discId}, document.getElementById('fixa-periodo').value)">Salvar</button></div>`);
}
async function salvarFixa(discId, periodo) {
  const outras = (S.preferencias?.fixas || []).filter(f => f.disciplina_id !== discId);
  const fixas = periodo ? [...outras, {disciplina_id: discId, periodo}] : outras;
  if (await salvarPreferencias({fixas})) {
    closeModal();
    toast(periodo ? 'Pedido salvo: a sugestão vai respeitar.' : 'Pedido retirado.', 'success');
    SIM.pref = null;                        // a rotina relê do servidor
  }
}
