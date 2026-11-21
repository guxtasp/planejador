// ═══════════════════════════════════════════════════════
// PAGE: PLANNER (Etapa 4B)
// O plano é guardado no servidor, por conta (Planos, em plano_store.js); o servidor o
// analisa a cada mudança e esta tela só mostra o resultado (S.analise). Nenhuma regra
// de negócio aqui.
// ═══════════════════════════════════════════════════════

// ── apresentação da análise ──────────────────────────────────────────────
const GRAVIDADE_CONFLITO = {conflito: 3, sem_turma_compativel: 2, conflito_possivel: 1};

function textoConflito(c) {
  const par = `${c.a.codigo} × ${c.b.codigo}`;
  const quando = `${diaLabel(c.dia)} ${c.horario_a} / ${c.horario_b}`;
  if (c.tipo === 'conflito')
    return {cls: 'alert-red', icon: '🔴', titulo: 'Conflito de horário', msg: `${par} se sobrepõem (${quando}).`};
  if (c.tipo === 'sem_turma_compativel')
    return {cls: 'alert-red', icon: '🔴', titulo: 'Sem turma compatível',
      msg: `${par}: toda combinação de turmas se sobrepõe (ex.: ${quando}).`};
  return {cls: 'alert-yellow', icon: '🟡', titulo: 'Conflito possível',
    msg: `${par} se sobrepõem em algumas turmas (ex.: ${quando}). Escolha as turmas para resolver.`};
}

function textoPendencia(p) {
  const nomes = p.alternativas.map(a => a.codigo).join(' ou ');
  const o = p.tipo === 'pre' ? 'Pré-requisito' : 'Correquisito';
  return `${o} pendente: ${nomes}`;
}

const analiseDoSemestre = semId => {
  const plano = Planos.atual();
  const i = plano ? plano.semestres.findIndex(s => s.id === semId) : -1;
  return i >= 0 ? S.analise[i] || null : null;
};

// disciplina → pior conflito em que está envolvida
function conflitosPorDisciplina(analise) {
  const mapa = new Map();
  (analise?.conflitos || []).forEach(c => [c.a.id, c.b.id].forEach(id => {
    const atual = mapa.get(id);
    if (!atual || GRAVIDADE_CONFLITO[c.tipo] > GRAVIDADE_CONFLITO[atual]) mapa.set(id, c.tipo);
  }));
  return mapa;
}

// ── página ───────────────────────────────────────────────────────────────
function planner() {
  const tb = document.getElementById('topbar-actions');
  // Sem plano não há o que escolher nem excluir: a barra fica vazia e a tela oferece "+ Criar plano".
  tb.innerHTML = S.planos.length ? `
    <select class="form-select" aria-label="Plano" style="width:200px;padding:6px 10px;font-size:13px" onchange="switchPlano(+this.value)">
      ${S.planos.map(p=>`<option value="${p.id}" ${p.id===S.currentPlano?'selected':''}>${esc(p.nome)}</option>`).join('')}
    </select>
    <button class="btn btn-primary btn-sm" onclick="abrirSugestao()">✨ Sugerir plano</button>
    <button class="btn btn-ghost btn-sm" onclick="irPara('calendario')" title="Ver a semana do plano">📅 Semana</button>
    <button class="btn btn-ghost btn-sm" onclick="newPlanoModal()">+ Novo plano</button>
    <button class="btn btn-ghost btn-sm" title="Excluir este plano" aria-label="Excluir este plano" onclick="excluirPlanoAtual()">🗑</button>
  ` : '';

  const plano = Planos.atual();
  const c = document.getElementById('content');

  if (!plano) {
    c.innerHTML = `<div class="empty"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/></svg><div style="font-size:15px;font-weight:600;color:var(--text);margin-bottom:6px">Você ainda não tem um plano</div><div style="max-width:420px;margin:0 auto 14px">Um plano é a sua previsão de matrícula, semestre a semestre. Crie um, depois arraste disciplinas da lista para cada semestre e veja na hora se há conflito ou pré-requisito faltando. Você pode ter vários planos e comparar.</div><button class="btn btn-primary" onclick="newPlanoModal()">+ Criar meu primeiro plano</button>
      <button class="btn btn-ghost" onclick="abrirSugestao()">✨ Pedir uma sugestão</button></div>
      <div id="sug-bloco" class="sug-no-planner" ${SIM.sugAberta ? '' : 'hidden'}></div>`;
    if (SIM.sugAberta) desenharSugestao();
    return;
  }

  const aprovados = getAprovados();
  const plannedIds = getPlannedIds();
  const periodosDisc = [...new Set(S.disciplinas.map(d=>d.periodo).filter(p=>p!=null))].sort((a,b)=>a-b);

  c.innerHTML = `
  <div id="sim-juntas" ${SIM.sugAberta ? '' : 'hidden'}></div>
  <div id="sug-bloco" class="sug-no-planner" ${SIM.sugAberta ? '' : 'hidden'}></div>
  <div id="planner-wrap">
    <div id="disc-palette" class="card" style="padding:0">
      <div style="padding:12px;border-bottom:1px solid var(--border)">
        <div style="font-size:12px;font-weight:700;color:var(--text2);margin-bottom:8px;text-transform:uppercase;letter-spacing:.05em">Disciplinas</div>
        <div class="search-wrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input class="search-input" placeholder="Buscar..." oninput="filterPalette(this.value)"/>
        </div>
        <div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap" id="palette-period-filter">
          <button class="btn btn-ghost btn-sm active-filter" onclick="setPeriodFilter(0,this)" style="font-size:11px;padding:3px 8px">Todos</button>
          ${periodosDisc.map(p=>
            `<button class="btn btn-ghost btn-sm" onclick="setPeriodFilter(${p},this)" style="font-size:11px;padding:3px 8px">${p}º</button>`
          ).join('')}
          ${S.disciplinas.some(d=>d.periodo==null) ? `<button class="btn btn-ghost btn-sm" onclick="setPeriodFilter(-1,this)" style="font-size:11px;padding:3px 8px">Sem período</button>` : ''}
        </div>
      </div>
      <div class="palette-list" id="palette-list">
        ${renderPaletteItems(S.disciplinas, aprovados, plannedIds)}
      </div>
    </div>

    <div id="planner-right">
      <div id="planner-board">
        ${plano.semestres.map(s => renderSemCol(s)).join('')}
        <div style="padding:8px">
          <button class="btn btn-ghost" onclick="addSemestre()" style="white-space:nowrap">+ Semestre</button>
        </div>
      </div>
    </div>
  </div>
  `;
  if (SIM.sugAberta) desenharSugestao();
}

let _periodFilter = 0;   // 0 = todos, -1 = sem período sugerido
let _searchFilter = '';

function renderPaletteItems(discs, aprovados, plannedIds) {
  let filtered = discs;
  if (_periodFilter > 0) filtered = filtered.filter(d => d.periodo === _periodFilter);
  if (_periodFilter === -1) filtered = filtered.filter(d => d.periodo == null);
  if (_searchFilter) {
    const q = _searchFilter.toLowerCase();
    filtered = filtered.filter(d => d.nome.toLowerCase().includes(q) || d.codigo.toLowerCase().includes(q));
  }

  if (filtered.length === 0) return '<div class="empty">Nenhuma disciplina encontrada</div>';

  return filtered.map(d => {
    const isAprov = aprovados.has(d.id);
    let badge = '';
    if (isAprov) badge = '<span class="badge badge-green" style="font-size:9px">Aprovado</span>';
    else if (plannedIds.has(d.id)) badge = '<span class="badge badge-purple" style="font-size:9px">Planejado</span>';

    return `<div class="disc-card" draggable="true" data-id="${d.id}"
      style="margin-bottom:6px;border-left:3px solid ${esc(d.cor)};${isAprov?'opacity:.5;pointer-events:none':''}"
      ondragstart="dragStart(event,${d.id})"
      onclick="showDiscDetail(${d.id})"
    >
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:2px">
        <span class="disc-codigo">${esc(d.codigo)}</span>
        ${badge}
      </div>
      <div class="disc-nome">${esc(d.nome)}</div>
      <div class="disc-info">
        <span class="tag">${credStr(d.creditos)}</span>
        <span class="tag">${valorOu(d.carga_h, 'h')}</span>
        <span class="tag">${periodStr(d.periodo)}</span>
        ${seloOferta(d)}
      </div>
    </div>`;
  }).join('');
}

function atualizarPaleta() {
  document.getElementById('palette-list').innerHTML =
    renderPaletteItems(S.disciplinas, getAprovados(), getPlannedIds());
}

function setPeriodFilter(p, el) {
  _periodFilter = p;
  document.querySelectorAll('#palette-period-filter .btn').forEach(b => b.classList.remove('active-filter'));
  el.classList.add('active-filter');
  atualizarPaleta();
}

function filterPalette(q) {
  _searchFilter = q;
  atualizarPaleta();
}

// ── semestre ─────────────────────────────────────────────────────────────
function renderSemCol(sem) {
  const a = analiseDoSemestre(sem.id);
  const porDisc = conflitosPorDisciplina(a);
  const pendPorDisc = new Map();
  (a?.pendencias || []).forEach(p => pendPorDisc.set(p.disciplina.id, [...(pendPorDisc.get(p.disciplina.id) || []), p]));

  // Todo período possível aparece (com quadro publicado ou não): o semestre nunca fica "sem período"
  // só porque as turmas dele ainda não saíram.
  const opcoesPeriodo = [...new Set([...S.periodos, ...periodosSugeridos(12), sem.periodo_letivo].filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, 'pt', {numeric: true}));
  const periodoSel = `<label class="sr-only" for="per-${sem.id}">Período letivo de ${esc(sem.rotulo)}</label>
    <select class="form-select" id="per-${sem.id}" title="Período letivo deste semestre (define quais turmas aparecem)"
      style="padding:3px 6px;font-size:11px;width:auto;margin-left:auto"
      onchange="mudarPeriodo(${sem.id},this.value)">
      <option value="">Período…</option>
      ${opcoesPeriodo.map(p=>`<option value="${esc(p)}" ${p===sem.periodo_letivo?'selected':''}>${esc(p)}${S.periodos.length && !S.periodos.includes(p) ? ' · sem quadro' : ''}</option>`).join('')}
    </select>`;

  return `<div class="sem-col" id="sem-${sem.id}" data-sem-id="${sem.id}" style="min-width:260px">
    <div class="sem-header">
      <span style="width:24px;height:24px;border-radius:6px;background:var(--accent);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0">${Planos.atual().semestres.indexOf(sem)+1}</span>
      <h3>${esc(sem.rotulo)}</h3>
      ${a?.choques_texto ? `<a class="badge badge-red" href="#" onclick="irParaChoque(${sem.id});return false">⛔ ${esc(a.choques_texto)}</a>` : ''}
      <button class="btn btn-ghost btn-sm" onclick="validarSemestre(${sem.id})" style="font-size:10px;padding:3px 7px">✓ Validar</button>
      <button class="btn btn-ghost btn-sm" onclick="removerSemestre(${sem.id})" style="font-size:10px;padding:3px 7px" aria-label="Remover ${esc(sem.rotulo)}" title="Remover semestre">✕</button>
    </div>
    ${periodoSel ? `<div style="display:flex;padding:0 12px 6px">${periodoSel}</div>` : ''}
    <div class="sem-body" id="sem-body-${sem.id}"
      ondragover="event.preventDefault();this.classList.add('drag-over')"
      ondragleave="this.classList.remove('drag-over')"
      ondrop="dropOnSem(event,${sem.id})"
    >
      ${sem.itens.map(i => renderDiscInSem(i, sem, porDisc.get(i.disciplina_id), pendPorDisc.get(i.disciplina_id), a?.marcas?.[i.disciplina_id])).join('')}
      ${sem.itens.length === 0 ? '<div style="font-size:11px;color:var(--text3);text-align:center;padding:20px 0">Arraste disciplinas aqui</div>' : ''}
    </div>
    ${renderRodape(a)}
    <button class="btn btn-ghost btn-sm sem-optativas" onclick="optativasQueCabem(${sem.id})">Optativas que cabem</button>
  </div>`;
}

// "N choques" no topo do semestre leva ao primeiro cartão com choque.
function irParaChoque(semId) {
  const marcas = analiseDoSemestre(semId)?.marcas || {};
  const id = Object.keys(marcas).find(k => marcas[k].choques?.length);
  const el = id && document.getElementById(`pl-item-${semId}-${id}`);
  if (el) { el.scrollIntoView({block: 'center'}); el.classList.add('destaque'); setTimeout(() => el.classList.remove('destaque'), 1600); }
}

// Lista as optativas que cabem neste semestre (oferta, requisitos e disponibilidade — regra do servidor).
// Só sugere: quem decide é a pessoa, no botão "Adicionar".
async function optativasQueCabem(semId) {
  const plano = Planos.atual();
  const posicao = plano.semestres.findIndex(s => s.id === semId) + 1;
  openModal(`<h2>Optativas que cabem</h2><div role="status" class="sim-faixa sim-carregando"><span class="sim-spin" aria-hidden="true"></span> Procurando…</div>`);
  const r = await POST(`/api/cursos/${CURSO_ID}/simulacao/optativas`, {...Planos.paraAnalise(), posicao});
  if (!r.ok) {
    openModal(`<h2>Optativas que cabem</h2><div class="sim-faixa sim-erro" role="alert">${esc(r.erro || 'Não foi possível buscar.')}</div>
      <div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">Fechar</button></div>`);
    return;
  }
  const cor = {green: 'badge-green', yellow: 'badge-yellow', gray: 'badge-gray'};
  openModal(`<h2>Optativas que cabem · ${esc(r.periodo)}</h2>
    <p class="sim-texto">${esc(r.mensagem)}</p>
    <ul class="opt-lista">${r.optativas.map(o => `<li>
      <div><b>${esc(o.disciplina.codigo)}</b> ${esc(o.disciplina.nome)} <small>${credStr(o.disciplina.creditos)}</small>
        <div class="sim-selos">${o.tags.map(t => `<span class="badge ${cor[t.cor] || 'badge-gray'}">${esc(t.texto)}</span>`).join(' ')}</div></div>
      <button class="btn btn-primary btn-sm" onclick="adicionarOptativa(${semId},${o.disciplina.id},${o.turma_id ?? 'null'},this)">Adicionar</button></li>`).join('')}</ul>
    <div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">Fechar</button></div>`);
}
async function adicionarOptativa(semId, discId, turmaId, botao) {
  Planos.adicionar(semId, discId);
  if (turmaId) Planos.definirTurma(semId, discId, turmaId);
  botao.disabled = true; botao.textContent = '✓ Adicionada';
  await atualizarPlano();
}

function renderRodape(a) {
  if (!a) return '<div class="sem-footer">…</div>';
  const limite = a.limite_creditos != null ? ` / ${a.limite_creditos}` : '';
  const sem_cred = a.disciplinas_sem_creditos.length
    ? ` <span style="color:var(--text3)" title="Créditos não informados no curso: não entram na soma">(+${a.disciplinas_sem_creditos.length} sem créditos)</span>` : '';
  // estágio/TCC marcados "fora do limite" contam para formar, não para o limite do semestre
  const fora = a.creditos_fora_do_limite || 0;
  return `<div class="sem-footer" style="${a.sobrecarga?'color:var(--red)':''}">
    ${fora ? a.creditos_no_limite : a.creditos}${limite} créditos ${a.sobrecarga?'⚠️ Sobrecarga':''}${sem_cred}
    ${fora ? `<span style="color:var(--text3)" title="Disciplinas marcadas como fora do limite de créditos (ex.: estágio)">· +${fora} fora do limite</span>` : ''}
  </div>`;
}

function renderDiscInSem(item, sem, tipoConflito, pendencias, marcas) {
  const d = S.disciplinas.find(x => x.id === item.disciplina_id);
  if (!d) {
    // Plano antigo: a disciplina saiu do catálogo (curso reimportado).
    return `<div class="disc-card" style="opacity:.7"><div class="disc-nome">Disciplina removida do curso</div>
      <button class="btn btn-danger btn-sm" onclick="removeFromSem(${sem.id},${item.disciplina_id})">✕ Tirar do plano</button></div>`;
  }
  const ofertadas = turmasDaDisciplina(d.id, sem.periodo_letivo);
  const livres = encontrosLivresDe(item);
  let escolhaTurma = '';
  if (livres.length) {
    escolhaTurma = `<div style="font-size:10px;color:var(--text2);margin-top:6px">🕐 ${esc(resumoHorarios(livres))}</div>`;
  } else if (sem.periodo_letivo && ofertadas.length) {
    // "Automática" = o Rumo escolhe a melhor combinação do semestre (sem choque, na sua rotina) e
    // acompanha as mudanças; escolher uma turma a deixa fixa.
    const auto = item.turma_auto || item.turma_id == null;
    const atual = ofertadas.find(t => t.id === item.turma_id);
    escolhaTurma = `<label class="sr-only" for="turma-${sem.id}-${d.id}">Turma de ${esc(d.codigo)}</label>
    <select class="form-select turma-sel" id="turma-${sem.id}-${d.id}" style="margin-top:6px;padding:3px 6px;font-size:10px"
      onclick="event.stopPropagation()" onchange="this.value === 'auto' ? turmaAutomatica(${sem.id},${d.id}) : escolherTurma(${sem.id},${d.id},+this.value)">
      <option value="auto" ${auto ? 'selected' : ''}>Automática${auto && atual ? ': ' + esc(turmaRotulo(atual)) : ''}</option>
      ${ofertadas.map(t=>`<option value="${t.id}" ${!auto && t.id===item.turma_id?'selected':''}>${esc(turmaRotulo(t))}</option>`).join('')}
    </select>
    <div class="turma-origem">${auto ? '✓ escolhida pelo Rumo · troque se quiser' : 'escolhida por você · fica fixa'}</div>`;
  } else if (sem.periodo_letivo && turmasDaDisciplina(d.id).length) {
    // quadro do período ainda não saiu (normal para semestres futuros) × saiu e ela não está nele (problema)
    escolhaTurma = S.periodos.includes(sem.periodo_letivo)
      ? `<div class="turma-origem turma-alerta">Não está no quadro de ${esc(sem.periodo_letivo)}</div>`
      : `<div class="turma-origem" title="Usamos o horário do último quadro publicado como estimativa">Turmas de ${esc(sem.periodo_letivo)} ainda não saíram · horário estimado</div>`;
  } else if (!sem.periodo_letivo && turmasDaDisciplina(d.id).length) {
    escolhaTurma = `<div style="font-size:10px;color:var(--text3);margin-top:4px">Escolha o período letivo para ver as turmas</div>`;
  }

  // Mesma regra e mesmo texto do Simulador: o servidor devolve as tags prontas (choque, disponibilidade,
  // sem horário, optativa). O selo de oferta aparece sempre, sem esperar a análise.
  const tags = [seloOferta(d, sem.periodo_letivo), tagsProntas(marcas?.tags)];
  if (marcas?.turma_que_cabe && marcas.turma_que_cabe !== item.turma_id) tags.push(
    `<button class="btn btn-ghost btn-sm" style="font-size:10px;padding:2px 8px" onclick="event.stopPropagation();escolherTurma(${sem.id},${d.id},${marcas.turma_que_cabe})">Usar a turma que cabe</button>`);
  if (pendencias?.length) tags.push(`<span class="badge badge-yellow" style="font-size:9px" title="${esc(pendencias.map(textoPendencia).join('; '))}">🔒 Requisito pendente</span>`);

  return `<div class="disc-card" draggable="true" data-id="${d.id}" data-sem="${sem.id}" id="pl-item-${sem.id}-${d.id}"
    style="border-left:3px solid ${esc(d.cor)}"
    ondragstart="dragStart(event,${d.id},${sem.id})"
    onclick="showDiscDetail(${d.id})"
  >
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:2px">
      <span class="disc-codigo">${esc(d.codigo)}</span>
      <div class="disc-actions">
        <button class="btn btn-danger btn-sm" style="padding:2px 6px;font-size:10px"
          onclick="event.stopPropagation();removeFromSem(${sem.id},${d.id})">✕</button>
      </div>
    </div>
    <div class="disc-nome">${esc(d.nome)}</div>
    <div class="disc-info">
      <span class="tag">${credStr(d.creditos)}</span>
      ${tags.join('')}
    </div>
    ${escolhaTurma}
    <button class="btn btn-ghost btn-sm" style="margin-top:6px;padding:2px 8px;font-size:10px"
      onclick="event.stopPropagation();editarHorarios(${sem.id},${d.id})">${livres.length ? '✎ Editar horários' : '🕐 Definir horários'}</button>
  </div>`;
}

// ── ações (alteram o plano local e pedem nova análise) ───────────────────
async function atualizarPlano() {
  S.planos = Planos.planos();
  S.currentPlano = Planos.atualId();
  await analisarPlano();
  planner();
}

let _dragId = null;
let _dragFromSem = null;

function dragStart(e, id, fromSem) {
  _dragId = id;
  _dragFromSem = fromSem || null;
  e.dataTransfer.effectAllowed = 'move';
}

async function dropOnSem(e, semId) {
  e.preventDefault();
  e.currentTarget.classList.remove('drag-over');
  if (!_dragId) return;
  const discId = _dragId;
  _dragId = null; _dragFromSem = null;

  Planos.adicionar(semId, discId);
  await atualizarPlano();
  avisarProblemasDe(semId, discId);
  perguntarLevarJunto(semId, discId);
}

// Movi uma disciplina de um grupo "cursar junto": oferece levar as outras para o mesmo semestre.
function perguntarLevarJunto(semId, discId) {
  const g = grupoDe(discId);
  if (!g) return;
  const plano = Planos.atual();
  const semDe = id => plano.semestres.find(s => s.itens.some(i => i.disciplina_id === id))?.id ?? null;
  const fora = g.disciplinas.filter(x => x !== discId && semDe(x) !== semId);
  if (!fora.length) return;
  const nomes = fora.map(x => S.disciplinas.find(y => y.id === x)?.codigo || x).join(', ');
  openModal(`<h2>Levar ${esc(nomes)} junto?</h2>
    <p class="sim-texto">Você quer cursá-las no mesmo semestre.</p>
    <div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">Só esta</button>
      <button class="btn btn-primary" onclick="levarJunto(${semId},[${fora.join(',')}])">Levar junto</button></div>`);
}
async function levarJunto(semId, ids) {
  closeModal();
  const plano = Planos.atual();
  const antes = ids.map(id => ({id, sem: plano.semestres.find(s => s.itens.some(i => i.disciplina_id === id))?.id ?? null}));
  ids.forEach(id => Planos.adicionar(semId, id));
  await atualizarPlano();
  toastAcao('Levadas para o mesmo semestre.', 'Desfazer', async () => {
    antes.forEach(a => a.sem ? Planos.adicionar(a.sem, a.id) : Planos.remover(semId, a.id));
    await atualizarPlano();
  });
}

// Avisos de quem acabou de entrar no semestre (vêm da análise do servidor).
function avisarProblemasDe(semId, discId) {
  const a = analiseDoSemestre(semId);
  if (!a) return;
  const avisos = [];
  a.pendencias.filter(p => p.disciplina.id === discId)
    .forEach(p => avisos.push(['⚠️ ' + textoPendencia(p), 'warn']));
  a.conflitos.filter(c => c.a.id === discId || c.b.id === discId).forEach(c => {
    const t = textoConflito(c);
    avisos.push([`${t.icon} ${t.titulo}: ${c.a.codigo} × ${c.b.codigo}`, c.tipo === 'conflito_possivel' ? 'warn' : 'error']);
  });
  if (!avisos.length) toast('Disciplina adicionada!', 'success');
  avisos.forEach(([msg, tipo]) => toast(msg, tipo, 5000));
}

// Ações que tiram algo do plano: sem confirmação, com "Desfazer" por ~8 s (controle e liberdade).
async function comDesfazer(mensagem, acao) {
  const antes = Planos.instantaneo();
  acao();
  await atualizarPlano();
  if (antes) toastAcao(mensagem, 'Desfazer', async () => { Planos.restaurar(antes); await atualizarPlano(); });
}

async function removeFromSem(semId, discId) {
  const d = S.disciplinas.find(x => x.id === discId);
  await comDesfazer(`${d?.codigo || 'Disciplina'} removida do plano.`, () => Planos.remover(semId, discId));
}

async function removerSemestre(semId) {
  const sem = Planos.atual()?.semestres.find(s => s.id === semId);
  await comDesfazer(`${sem?.rotulo || 'Semestre'} removido.`, () => Planos.removerSemestre(semId));
}

async function addSemestre() {
  Planos.adicionarSemestre();
  await atualizarPlano();
}

async function mudarPeriodo(semId, periodo) {
  Planos.definirPeriodo(semId, periodo);
  await atualizarPlano();
}

async function turmaAutomatica(semId, discId) {
  await comDesfazer('Turma volta a ser escolhida pelo Rumo.', () => Planos.turmaAutomatica(semId, discId));
}

async function escolherTurma(semId, discId, turmaId) {
  const d = S.disciplinas.find(x => x.id === discId);
  await comDesfazer(`Turma de ${d?.codigo || 'disciplina'} trocada.`, () => Planos.definirTurma(semId, discId, turmaId));
}

async function switchPlano(id) {
  Planos.selecionar(id);
  await atualizarPlano();
}

function newPlanoModal() {
  openModal(`<h2>Novo Plano de Estudo</h2>
    <div class="form-group">
      <label class="form-label">Nome do plano</label>
      <input id="m-nome" class="form-input" placeholder="Ex: Plano 2026.2"/>
    </div>
    <div class="form-group">
      <label class="form-label">Número de semestres</label>
      <select id="m-sems" class="form-select">
        ${[2,4,6,8].map(n=>`<option value="${n}" ${n===4?'selected':''}>${n} semestres</option>`).join('')}
      </select>
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="savePlano()">Criar</button>
    </div>`);
}

async function savePlano() {
  const nome = document.getElementById('m-nome').value.trim();
  const sems = +document.getElementById('m-sems').value;
  if (!nome) { toast('Informe o nome do plano','error'); return; }
  if (!await Planos.criar(nome, sems)) return;   // o erro já foi avisado; a janela fica aberta
  closeModal();
  await atualizarPlano();
}

// Excluir plano é a única ação com confirmação (perde tudo); ainda assim dá para desfazer (recria o plano).
function excluirPlanoAtual() {
  const plano = Planos.atual();
  if (!plano) return;
  openModal(`<h2>Excluir o plano “${esc(plano.nome)}”?</h2>
    <p class="sim-texto">Os semestres e as turmas escolhidas deste plano saem da sua conta.</p>
    <div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-danger" onclick="confirmarExcluirPlano(${plano.id})">Excluir plano</button></div>`);
}
async function confirmarExcluirPlano(id) {
  closeModal();
  const conteudo = Planos.conteudo(id);
  if (!await Planos.excluir(id)) return;
  await atualizarPlano();
  toastAcao(`Plano “${conteudo.nome}” excluído.`, 'Desfazer', async () => {
    if (await Planos.criarComConteudo(conteudo)) { S.planos = Planos.planos(); S.currentPlano = Planos.atualId(); await atualizarPlano(); }
  });
}

// ── validação (resumo do que o servidor encontrou) ───────────────────────
function validarSemestre(semId) {
  const a = analiseDoSemestre(semId);
  if (!a) { toast('A análise ainda não terminou. Tente de novo.', 'warn'); return; }

  const blocos = [];
  a.conflitos.forEach(c => {
    const t = textoConflito(c);
    blocos.push(`<div class="alert ${t.cls}"><span>${t.icon}</span><div><strong>${t.titulo}</strong><br>${esc(t.msg)}</div></div>`);
  });
  a.pendencias.forEach(p => blocos.push(
    `<div class="alert alert-yellow"><span>${p.tipo==='pre'?'🔒':'🔗'}</span><div><strong>${esc(p.disciplina.codigo)} — ${esc(p.disciplina.nome)}</strong><br>${esc(textoPendencia(p))}</div></div>`));
  if (a.sobrecarga) blocos.push(
    `<div class="alert alert-red"><span>⚠️</span><div><strong>Sobrecarga</strong><br>${a.creditos_no_limite ?? a.creditos} créditos, acima do limite do curso (${a.limite_creditos}).</div></div>`);
  if (a.sem_turma_escolhida.length) {
    const nomes = a.sem_turma_escolhida.map(id => S.disciplinas.find(d=>d.id===id)?.codigo).filter(Boolean).join(', ');
    blocos.push(`<div class="alert alert-blue"><span>🕐</span><div><strong>Falta escolher a turma</strong><br>${esc(nomes)}. Sem a turma, o horário não pode ser conferido por completo.</div></div>`);
  }
  if (a.invalidos.length) blocos.push(
    `<div class="alert alert-yellow"><span>🧹</span><div><strong>Itens que não batem com o curso</strong><br>${a.invalidos.length} item(ns) do plano referem-se a disciplinas ou turmas que já não existem; as turmas foram ignoradas.</div></div>`);

  const problemas = a.conflitos.length + a.pendencias.length + (a.sobrecarga ? 1 : 0);
  openModal(`<h2>Validação do Semestre</h2>
    ${problemas === 0 && !a.invalidos.length ? '<div class="alert alert-blue">✅ Nenhum problema encontrado neste semestre.</div>' : ''}
    ${blocos.join('')}
    <div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border);font-size:13px;color:var(--text2)">
      Total de créditos: <strong>${a.creditos}</strong>${a.limite_creditos != null ? ` (limite ${a.limite_creditos})` : ' (o curso não informa limite)'}
      ${a.sobrecarga ? '<span class="badge badge-red" style="margin-left:8px">Sobrecarga</span>' : ''}
    </div>
    <div class="modal-footer"><button class="btn btn-primary" onclick="closeModal()">Fechar</button></div>`);
}


// ── "Sugerir plano": a sugestão mora aqui (cria um plano novo; o atual não muda) ──
// O painel usa o mesmo motor do Simulador e compara com o plano aberto (que é simulado em segundo plano).
window.abrirSugestao = () => {
  SIM.sugAberta = true;
  const bloco = document.getElementById('sug-bloco');
  if (bloco) { bloco.hidden = false; desenharSugestao(); bloco.scrollIntoView({block: 'start'}); }
  const pergunta = document.getElementById('sim-juntas');      // "cursar junto?" só importa para a sugestão
  if (pergunta) { pergunta.hidden = false; desenharPerguntaJuntas(); }
  if (planoTemItens() && !precisaDoPeriodo() && SIM.sim.assinatura !== assinaturaDoPedido()) simRodar();
};
window.fecharSugestao = () => {
  SIM.sugAberta = false;
  ['sug-bloco', 'sim-juntas'].forEach(id => { const b = document.getElementById(id); if (b) b.hidden = true; });
};
