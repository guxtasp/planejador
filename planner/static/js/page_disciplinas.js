// ═══════════════════════════════════════════════════════
// PAGE: DISCIPLINAS — catálogo do curso. Quem trouxe o curso edita aqui mesmo
// (dados, oferta par/ímpar e requisitos); os outros só consultam.
// ═══════════════════════════════════════════════════════
const DISC_F = {q: '', filtro: 'todas'};     // busca e filtro sobrevivem ao redesenho
const FILTROS_DISC = {
  todas: {rotulo: 'Todas', ok: () => true},
  obrigatoria: {rotulo: 'Obrigatórias', ok: d => d.tipo === 'obrigatoria'},
  optativa: {rotulo: 'Optativas e eletivas', ok: d => d.tipo !== 'obrigatoria'},
  sem_oferta: {rotulo: 'Sem oferta informada', ok: d => !d.periodicidade},
};

function disciplinas() {
  const dono = S.podeEditarCatalogo;
  document.getElementById('topbar-actions').innerHTML = dono
    ? `<a class="btn btn-ghost btn-sm" href="/importar" title="Trocar o catálogo inteiro por arquivos CSV">Importar CSV</a>
       <button class="btn btn-primary btn-sm" onclick="editarDisciplina(null)">+ Nova disciplina</button>`
    : '';
  const semOferta = S.disciplinas.filter(d => !d.periodicidade).length;
  const aviso = !dono
    ? `<div class="alert alert-blue" style="margin-bottom:16px"><span>ℹ</span><div>Este curso foi trazido por outra pessoa: aqui você só consulta.
        Se algo estiver errado, avise quem o cadastrou.</div></div>`
    : semOferta ? `<div class="alert alert-yellow" role="status" style="margin-bottom:16px"><span>⚠</span><div>
        <b>${semOferta} disciplina${semOferta > 1 ? 's' : ''} sem oferta informada.</b>
        Sem ela, o Rumo estima pelo período sugerido. Escolha a oferta direto na coluna <i>Oferta</i>.
        ${DISC_F.filtro !== 'sem_oferta' ? `<button class="btn btn-ghost btn-sm" onclick="filtrarDisc('sem_oferta')">Mostrar só essas</button>` : ''}</div></div>`
    : '';
  document.getElementById('content').innerHTML = aviso + `
  <div class="card disc-busca">
    <div class="search-wrap">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <input class="search-input" placeholder="Buscar por nome ou código…" id="disc-search" aria-label="Buscar disciplina"
             value="${esc(DISC_F.q)}" oninput="DISC_F.q = this.value; renderDiscTable()"/>
    </div>
    <div class="disc-filtros" role="group" aria-label="Filtrar">
      ${Object.entries(FILTROS_DISC).map(([k, f]) => `<button class="btn btn-ghost btn-sm ${DISC_F.filtro === k ? 'ativo' : ''}"
        aria-pressed="${DISC_F.filtro === k}" onclick="filtrarDisc('${k}')">${f.rotulo}</button>`).join('')}
    </div>
  </div>
  <div id="disc-table-wrap"></div>`;
  renderDiscTable();
}

function filtrarDisc(k) { DISC_F.filtro = k; disciplinas(); }

window.renderDiscTable = function() {
  const q = DISC_F.q.trim().toLowerCase();
  const lista = S.disciplinas.filter(d => FILTROS_DISC[DISC_F.filtro].ok(d)
    && (!q || d.nome.toLowerCase().includes(q) || d.codigo.toLowerCase().includes(q)));
  const wrap = document.getElementById('disc-table-wrap');
  if (!wrap) return;
  if (!lista.length) {
    wrap.innerHTML = `<div class="card empty"><p>Nenhuma disciplina encontrada${q ? ` para “${esc(DISC_F.q)}”` : ''}.</p>
      ${DISC_F.filtro !== 'todas' || q ? `<button class="btn btn-ghost btn-sm" onclick="DISC_F.q=''; filtrarDisc('todas')">Limpar busca e filtro</button>` : ''}</div>`;
    return;
  }
  const dono = S.podeEditarCatalogo;
  wrap.innerHTML = `<div class="card disc-tabela-card"><div class="disc-tabela-rolagem">
    <table class="disc-tabela">
      <caption class="sr-only">${lista.length} disciplina(s)</caption>
      <thead><tr>${['Código', 'Nome', 'Período', 'Oferta', 'Créditos', 'CH', 'Turmas', 'Pré-requisitos', '']
        .map((h, k) => `<th scope="col" class="${[5, 6].includes(k) ? 'col-opc' : ''}">${h}</th>`).join('')}</tr></thead>
      <tbody>${lista.map(d => {
        const pre = (d.prerequisitos || []).filter(p => p.tipo === 'pre');
        const n = turmasDaDisciplina(d.id).length;
        return `<tr>
          <td><span class="disc-cod" style="border-left-color:${esc(d.cor)}">${esc(d.codigo)}</span></td>
          <td><button class="link-disc" onclick="showDiscDetail(${d.id})">${esc(d.nome)}</button>
            ${d.tipo !== 'obrigatoria' ? `<span class="badge badge-gray">${d.tipo === 'optativa' ? 'Optativa' : 'Eletiva'}</span>` : ''}</td>
          <td>${periodStr(d.periodo)}</td>
          <td>${dono ? seletorOferta(d) : periodicidadeBadge(d.periodicidade)}</td>
          <td>${valorOu(d.creditos)}${d.conta_no_limite === false ? ' <span class="badge badge-gray" title="Conta para formar, não para o limite do semestre">fora do limite</span>' : ''}</td>
          <td class="col-opc">${valorOu(d.carga_h, 'h')}</td>
          <td class="col-opc">${n ? `${n} turma${n > 1 ? 's' : ''}` : '–'}</td>
          <td>${pre.map(p => `<span class="tag">${esc(p.codigo)}</span>`).join(' ') || '–'}</td>
          <td class="disc-acoes">${dono ? `<button class="btn btn-ghost btn-sm" onclick="editarDisciplina(${d.id})" aria-label="Editar ${esc(d.codigo)}">Editar</button>` : ''}</td>
        </tr>`;
      }).join('')}</tbody>
    </table></div></div>`;
};

// Oferta na própria tabela (o caso mais comum de correção): muda na hora, com "Desfazer".
function seletorOferta(d) {
  return `<select class="form-select disc-oferta ${d.periodicidade ? '' : 'vazia'}" aria-label="Oferta de ${esc(d.codigo)}"
    onchange="mudarOferta(${d.id}, this.value)">
    ${[['', 'Não informada'], ['sempre', 'Todo período'], ['impar', 'Só ímpar (…/1)'], ['par', 'Só par (…/2)']]
      .map(([v, r]) => `<option value="${v}" ${(d.periodicidade || '') === v ? 'selected' : ''}>${r}</option>`).join('')}</select>`;
}
async function mudarOferta(id, valor, comDesfazer = true) {
  const d = S.disciplinas.find(x => x.id === id);
  const antes = d?.periodicidade || null;
  const r = await PATCH(`/api/cursos/${CURSO_ID}/disciplinas/periodicidade`,
    {itens: [{disciplina_id: id, periodicidade: valor || null}]});
  if (!r.ok) { toast(r.erro || 'Não foi possível salvar a oferta.', 'error'); return render(); }
  await recarregarCatalogo();
  if (comDesfazer) toastAcao(`Oferta de ${d.codigo} salva.`, 'Desfazer', () => mudarOferta(id, antes, false));
}

// ── editor (criar e editar) ───────────────────────────────────────────────
const EDIT_DISC = {id: null, req: []};

function editarDisciplina(id) {
  const d = id ? S.disciplinas.find(x => x.id === id) : null;
  EDIT_DISC.id = id;
  EDIT_DISC.req = (d?.prerequisitos || []).map(r => ({id: r.id, tipo: r.tipo, grupo_alt: r.grupo_alt || null}));
  const v = c => d?.[c] ?? '';
  openModal(`<form onsubmit="event.preventDefault(); salvarDisciplina()" novalidate>
    <h2>${d ? `Editar ${esc(d.codigo)}` : 'Nova disciplina'}</h2>
    <p class="dica-campo" style="margin:-4px 0 14px">Campos em branco ficam como “não informado”; nunca viram zero.</p>
    <div class="form-row">
      <div class="form-group"><label class="form-label" for="ed-codigo">Código</label>
        <input class="form-input" id="ed-codigo" value="${esc(v('codigo'))}" maxlength="30" required autocomplete="off"></div>
      <div class="form-group"><label class="form-label" for="ed-tipo">Tipo</label>
        <select class="form-select" id="ed-tipo">${[['obrigatoria', 'Obrigatória'], ['optativa', 'Optativa'], ['eletiva', 'Eletiva']]
          .map(([k, r]) => `<option value="${k}" ${(d?.tipo || 'obrigatoria') === k ? 'selected' : ''}>${r}</option>`).join('')}</select></div>
    </div>
    <div class="form-group"><label class="form-label" for="ed-nome">Nome</label>
      <input class="form-input" id="ed-nome" value="${esc(v('nome'))}" maxlength="200" required></div>
    <div class="form-row">
      <div class="form-group"><label class="form-label" for="ed-creditos">Créditos</label>
        <input class="form-input" id="ed-creditos" type="number" inputmode="numeric" min="0" max="60" value="${v('creditos')}"></div>
      <div class="form-group"><label class="form-label" for="ed-carga_h">Carga horária (h)</label>
        <input class="form-input" id="ed-carga_h" type="number" inputmode="numeric" min="0" max="2000" value="${v('carga_h')}"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label class="form-label" for="ed-periodo_sugerido">Período na matriz</label>
        <input class="form-input" id="ed-periodo_sugerido" type="number" inputmode="numeric" min="1" max="20" value="${v('periodo_sugerido')}"
               aria-describedby="ed-periodo-dica"><div class="dica-campo" id="ed-periodo-dica">1º, 2º… como na grade do curso.</div></div>
      <div class="form-group"><label class="form-label" for="ed-periodicidade">Oferta</label>
        <select class="form-select" id="ed-periodicidade" aria-describedby="ed-oferta-dica">
          ${[['', 'Não informada'], ['sempre', 'Todo período'], ['impar', 'Só ímpar (2027/1, 2028/1…)'], ['par', 'Só par (2027/2, 2028/2…)']]
            .map(([k, r]) => `<option value="${k}" ${(d?.periodicidade || '') === k ? 'selected' : ''}>${r}</option>`).join('')}</select>
        <div class="dica-campo" id="ed-oferta-dica">Em quais semestres ela abre.</div></div>
    </div>
    <div class="form-group">
      <label class="ed-check"><input type="checkbox" id="ed-conta_no_limite" ${d?.conta_no_limite === false ? '' : 'checked'}>
        Conta no limite de créditos do semestre</label>
      <div class="dica-campo">Desmarque para estágio, TCC ou atividades com muitos créditos e pouca aula, se o seu curso
        não os soma no limite da matrícula. Os créditos continuam contando para formar.</div>
    </div>
    <div class="form-group" id="ed-requisitos" tabindex="-1">
      <div class="form-label">Requisitos</div>
      <div id="ed-req-listas"></div>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button type="submit" class="btn btn-primary" id="ed-salvar">${d ? 'Salvar alterações' : 'Criar disciplina'}</button>
    </div></form>`);
  desenharRequisitosEdicao();
}

function desenharRequisitosEdicao() {
  const el = document.getElementById('ed-req-listas');
  if (!el) return;
  const nome = id => S.disciplinas.find(x => x.id === id);
  const usadas = new Set(EDIT_DISC.req.map(r => `${r.id}:${r.tipo}`));
  const bloco = (tipo, titulo, dica) => {
    const itens = EDIT_DISC.req.map((r, k) => ({...r, k})).filter(r => r.tipo === tipo);
    const opcoes = S.disciplinas.filter(x => x.id !== EDIT_DISC.id && !usadas.has(`${x.id}:${tipo}`));
    return `<div class="req-bloco">
      <div class="req-titulo">${titulo} <span class="dica-campo">${dica}</span></div>
      <div class="req-chips">${itens.map(r => `<span class="tag req-chip" ${r.grupo_alt ? `title="Alternativa: basta cumprir uma das marcadas “ou”"` : ''}>
          ${esc(nome(r.id)?.codigo || r.id)}${r.grupo_alt ? ' <i>ou</i>' : ''}
          <button type="button" onclick="EDIT_DISC.req.splice(${r.k}, 1); desenharRequisitosEdicao()" aria-label="Tirar ${esc(nome(r.id)?.codigo || '')}">✕</button></span>`).join('')
        || '<span class="dica-campo">Nenhum.</span>'}</div>
      <select class="form-select req-add" aria-label="Adicionar ${titulo.toLowerCase()}"
        onchange="if (this.value) { EDIT_DISC.req.push({id: Number(this.value), tipo: '${tipo}', grupo_alt: null}); desenharRequisitosEdicao() }">
        <option value="">+ Adicionar…</option>
        ${opcoes.map(x => `<option value="${x.id}">${esc(x.codigo)} · ${esc(x.nome)}</option>`).join('')}</select></div>`;
  };
  el.innerHTML = bloco('pre', 'Pré-requisitos', 'cursar antes') + bloco('co', 'Correquisitos', 'antes ou no mesmo semestre');
}

function corpoDisciplina() {
  const val = id => document.getElementById(`ed-${id}`).value.trim();
  const num = id => (x => x === '' ? null : Number(x))(val(id));
  return {codigo: val('codigo'), nome: val('nome'), tipo: val('tipo'), creditos: num('creditos'), carga_h: num('carga_h'),
          periodo_sugerido: num('periodo_sugerido'), periodicidade: val('periodicidade') || null, requisitos: EDIT_DISC.req,
          conta_no_limite: document.getElementById('ed-conta_no_limite').checked};
}

async function salvarDisciplina() {
  ['codigo', 'nome', 'tipo', 'creditos', 'carga_h', 'periodo_sugerido', 'periodicidade'].forEach(c => limparErroCampo(`ed-${c}`));
  document.getElementById('ed-requisitos-erro')?.remove();
  const corpo = corpoDisciplina();
  if (!corpo.codigo) return erroNoCampo('ed-codigo', 'Preencha o código.');
  if (!corpo.nome) return erroNoCampo('ed-nome', 'Preencha o nome.');
  const id = EDIT_DISC.id;
  const antes = id ? S.disciplinas.find(x => x.id === id) : null;
  const botao = document.getElementById('ed-salvar');
  botao.disabled = true; botao.textContent = 'Salvando…';
  const r = id ? await PATCH(`/api/cursos/${CURSO_ID}/disciplinas/${id}`, corpo) : await POST(`/api/cursos/${CURSO_ID}/disciplinas`, corpo);
  if (!r.ok) {
    botao.disabled = false; botao.textContent = id ? 'Salvar alterações' : 'Criar disciplina';
    const campo = r.detalhes?.campo;
    if (campo === 'requisitos') {
      document.getElementById('ed-req-listas').insertAdjacentHTML('afterend',
        `<div class="campo-erro" id="ed-requisitos-erro" role="alert">${esc(r.erro)}</div>`);
      return;
    }
    return campo ? erroNoCampo(`ed-${campo}`, r.erro) : toast(r.erro || 'Não foi possível salvar.', 'error');
  }
  closeModal();
  await recarregarCatalogo();
  if (antes) {
    const volta = {codigo: antes.codigo, nome: antes.nome, tipo: antes.tipo, creditos: antes.creditos, carga_h: antes.carga_h,
                   periodo_sugerido: antes.periodo_sugerido, periodicidade: antes.periodicidade,
                   conta_no_limite: antes.conta_no_limite !== false,
                   requisitos: (antes.prerequisitos || []).map(x => ({id: x.id, tipo: x.tipo, grupo_alt: x.grupo_alt || null}))};
    toastAcao(`${r.disciplina.codigo} salva.`, 'Desfazer', async () => {
      const v = await PATCH(`/api/cursos/${CURSO_ID}/disciplinas/${id}`, volta);
      if (!v.ok) return toast(v.erro || 'Não foi possível desfazer.', 'error');
      await recarregarCatalogo();
      toast('Alteração desfeita.', 'success');
    });
  } else {
    toast(`${r.disciplina.codigo} criada. Ela já aparece no Planejamento e no Fluxograma.`, 'success', 4500);
  }
}
