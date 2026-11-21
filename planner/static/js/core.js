// ═══════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════
const S = {
  curso: null,
  disciplinas: [],
  historico: [],       // tentativas do aluno neste curso (N por disciplina)
  painel: null,        // status por disciplina, progresso e previsão (servidor)
  situacoes: new Map(),// disciplina_id → {situacao, reprovada_antes, pendencias} (derivado de `painel`)
  planos: [],
  currentPlano: null,
  currentPage: 'dashboard',
  calendarSemId: null,
  // Oferta e análise (Etapa 4B)
  turmas: [],          // turmas do curso, com encontros
  periodos: [],        // períodos letivos com oferta ("2026/1", ...)
  grade: null,         // {dias, hora_inicio, hora_fim}, derivada dos dados no servidor
  analise: [],         // resultado do servidor, um item por semestre do plano atual
};

// ═══════════════════════════════════════════════════════
// CONTEXTO DO CURSO (Etapa 4A)
// O planejador agora sempre trabalha sobre UM curso, escolhido no onboarding
// (`/`) e identificado na URL (`/curso/<id>`). Nada de curso fixo no código.
// ═══════════════════════════════════════════════════════
const CURSO_ID = Number(document.body.dataset.cursoId);

// ═══════════════════════════════════════════════════════
// API
// ═══════════════════════════════════════════════════════
// Sempre devolve um objeto `{ok, ...}` (nunca lança): erro de rede ou resposta que não é
// JSON viram `{ok:false, erro}`. `status` vai junto para quem precisar distinguir 404/422.
// Sessão expirada (401) leva ao login e volta para esta página.
async function api(method, path, body) {
  const opts = { method, headers: {'Content-Type':'application/json'} };
  if (body) opts.body = JSON.stringify(body);
  let r;
  try { r = await fetch(path, opts); }
  catch (e) { return {ok: false, status: 0, erro: 'Sem conexão com o servidor.'}; }
  if (r.status === 401) {
    location.href = `/entrar?proximo=${encodeURIComponent(location.pathname)}`;
    return {ok: false, status: 401, erro: 'Entre para continuar.'};
  }
  try { return {status: r.status, ...(await r.json())}; }
  catch (e) { return {ok: false, status: r.status, erro: 'Resposta inesperada do servidor.'}; }
}
const GET  = p => api('GET', p);
const POST = (p, b) => api('POST', p, b);
const PUT  = (p, b) => api('PUT', p, b);
const PATCH = (p, b) => api('PATCH', p, b);
const DEL  = p => api('DELETE', p);

// ═══════════════════════════════════════════════════════
// TOAST
// ═══════════════════════════════════════════════════════
function toast(msg, type='info', dur=3500) {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  el.addEventListener('click', () => el.remove());
  el.dataset.criado = Date.now();
  document.getElementById('toast-area').appendChild(el);
  setTimeout(() => el.remove(), type === 'error' ? Math.max(dur, 6000) : dur);   // erro fica mais tempo
}

// Toast com uma ação (ex.: "Desfazer"), visível por ~8 s. O botão é focável e fecha o toast.
function toastAcao(msg, rotulo, acao, dur = 8000) {
  const el = document.createElement('div');
  el.className = 'toast toast-info toast-acao';
  el.setAttribute('role', 'status');
  el.innerHTML = `<span>${esc(msg)}</span> <button class="btn btn-ghost btn-sm">${esc(rotulo)}</button>`;
  el.querySelector('button').onclick = e => { e.stopPropagation(); el.remove(); acao(); };
  document.getElementById('toast-area').appendChild(el);
  setTimeout(() => el.remove(), dur);
}

// ── Erro junto ao campo (não só em toast): aria-invalid + aria-describedby + texto logo abaixo ──
function erroNoCampo(id, msg) {
  const el = document.getElementById(id);
  if (!el) { toast(msg, 'error'); return; }
  limparErroCampo(id);
  el.setAttribute('aria-invalid', 'true');
  el.setAttribute('aria-describedby', `${id}-erro`);
  el.insertAdjacentHTML('afterend', `<div class="campo-erro" id="${id}-erro" role="alert">${esc(msg)}</div>`);
  el.focus();
}
function limparErroCampo(id) {
  const el = document.getElementById(id);
  el?.removeAttribute('aria-invalid');
  el?.removeAttribute('aria-describedby');
  document.getElementById(`${id}-erro`)?.remove();
}

// ── Campo de período: lista dos próximos períodos + "Outro…" para digitar (prevenção de erro) ──
// A lista parte do período seguinte ao histórico (ou do 1º do plano). Sem nenhum dos dois, parte do
// período corrente do relógio da pessoa: é só uma lista para ESCOLHER; nada é assumido sem ela escolher.
const PERIODO_VALIDO = /^\d{4}\s*[./-]\s*[12]$/;
function proximoPeriodo(p) { const [a, n] = p.split('/').map(Number); return n === 1 ? `${a}/2` : `${a + 1}/1`; }
// O próximo período em que dá para se matricular (o que está em andamento já passou da matrícula):
// jan–fev → AAAA/1 · mar–jul → AAAA/2 · ago–dez → (AAAA+1)/1.
function proximaMatricula(hoje = new Date()) {
  const m = hoje.getMonth(), a = hoje.getFullYear();
  return m < 2 ? `${a}/1` : m < 7 ? `${a}/2` : `${a + 1}/1`;
}
function periodosSugeridos(n = 8) {
  const doHist = S.historico.map(h => h.periodo_letivo).filter(Boolean).sort((a, b) => a.localeCompare(b, 'pt', {numeric: true}));
  const doPlano = Planos.atual()?.semestres.map(s => s.periodo_letivo).find(Boolean);
  let p = doHist.length ? proximoPeriodo(doHist[doHist.length - 1]) : (doPlano || proximaMatricula());
  const lista = [];
  for (let i = 0; i < n; i++) { lista.push(p); p = proximoPeriodo(p); }
  return lista;
}
function campoPeriodo(id, valor, {auto = true, desativado = false, aoMudar = ''} = {}) {
  const opcoes = periodosSugeridos();
  const outro = valor && !opcoes.includes(valor);
  return `<select class="form-select" id="${id}" ${desativado ? 'disabled' : ''}
      onchange="document.getElementById('${id}-outro').hidden = this.value !== 'outro'; limparErroCampo('${id}'); ${aoMudar}">
      ${auto ? `<option value="" ${!valor ? 'selected' : ''}>Automático</option>` : `<option value="" disabled ${!valor ? 'selected' : ''}>Escolha…</option>`}
      ${opcoes.map(p => `<option ${p === valor ? 'selected' : ''}>${p}</option>`).join('')}
      <option value="outro" ${outro ? 'selected' : ''}>Outro…</option>
    </select>
    <input class="form-input campo-outro" id="${id}-outro" ${outro ? '' : 'hidden'} placeholder="AAAA/N" maxlength="7" inputmode="numeric"
      aria-label="Digite o período (AAAA/N)" value="${outro ? esc(valor) : ''}" onkeydown="if(event.key==='Enter'){${aoMudar}}" onchange="${aoMudar}"/>`;
}
// Valor escolhido; null = inválido (o erro já aparece junto ao campo).
function valorPeriodo(id) {
  const sel = document.getElementById(id);
  if (!sel) return '';
  if (sel.value !== 'outro') return sel.value;
  const v = document.getElementById(`${id}-outro`).value.trim();
  if (!PERIODO_VALIDO.test(v)) { erroNoCampo(`${id}-outro`, 'Use AAAA/N, por exemplo 2027/1.'); return null; }
  limparErroCampo(`${id}-outro`);
  return v.replace(/\s*[.-]\s*/, '/').replace(/\s+/g, '');
}

// ── Linha de metrô: a cadeia crítica como estações (o curso é uma linha; a formatura, o terminal) ──
function linhaDeMetro(estacoes, rotulo) {
  if (!estacoes?.length) return '';
  return `<ol class="metro" aria-label="${esc(rotulo)}">${estacoes.map((e, k) => `<li class="${k === estacoes.length - 1 ? 'terminal' : ''}">
    <span class="metro-ponto" aria-hidden="true"></span><b title="${esc(e.nome || '')}">${esc(e.codigo)}</b><small>${esc(e.periodo || '')}</small></li>`).join('')}</ol>`;
}

// Grava as preferências do aluno (junta o que mudou ao que já está guardado). Devolve true se deu certo.
async function salvarPreferencias(parcial) {
  const r = await PUT(`/api/cursos/${CURSO_ID}/preferencias`, {...(S.preferencias || {}), ...parcial});
  if (!r.ok) { toast(r.erro || 'Não foi possível guardar as preferências.', 'error'); return false; }
  S.preferencias = r.preferencias;
  // grupo "cursar junto" impossível: avisado na hora, com o motivo (o resto segue valendo)
  (r.avisos_juntas || []).forEach(a => toast(a, 'warn', 9000));
  return true;
}
// Grupos "cursar junto" de uma disciplina (as outras do grupo).
const grupoDe = id => (S.preferencias?.juntas || []).find(g => g.disciplinas.includes(id)) || null;

// ═══════════════════════════════════════════════════════
// MODAL
// ═══════════════════════════════════════════════════════
function openModal(html) {
  document.getElementById('modal-box').innerHTML = html;
  document.getElementById('modal-overlay').style.display = 'flex';
  const primeiro = document.querySelector('#modal-box input:not([type=hidden]), #modal-box select, #modal-box textarea');
  if (primeiro) primeiro.focus();
}
function closeModal() {
  document.getElementById('modal-overlay').style.display = 'none';
}

// ═══════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════
async function navTo(page, el) {
  S.currentPage = page;
  // aviso simples de outra tela não acompanha a pessoa (os de "Desfazer" e de erro ficam)
  document.querySelectorAll('#toast-area .toast:not(.toast-acao):not(.toast-error)').forEach(t => {
    if (Date.now() - Number(t.dataset.criado || 0) > 1200) t.remove();
  });
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  if (el) el.classList.add('active');
  document.querySelectorAll('.nav-item').forEach(n => n.removeAttribute('aria-current'));
  if (el) el.setAttribute('aria-current', 'page');
  document.getElementById('content').innerHTML = '<div class="skel-grid"><div class="skel"></div><div class="skel"></div><div class="skel"></div><div class="skel"></div><div class="skel alto"></div></div>';
  document.getElementById('topbar-actions').innerHTML = '';
  await loadData();
  render();
}

// Cores só de exibição (não são gravadas): usadas quando a disciplina não tem `cor`.
const COR_PADRAO = {obrigatoria: '#4338CA', optativa: '#0F9D8A', eletiva: '#D98E04'};

// A API nova usa nomes do banco (`periodo_sugerido`, `requisitos`); as telas
// herdadas esperam `periodo`, `prerequisitos`, `horarios`. Este é o único
// ponto de tradução. Campos desconhecidos continuam `null` (nunca viram 0).
function adaptarDisciplina(d) {
  return {
    ...d,
    periodo: d.periodo_sugerido,
    cor: d.cor || COR_PADRAO[d.tipo] || '#4338CA',
    prerequisitos: d.requisitos || [],
    horarios: [],   // horários vêm das turmas (Etapa 4B)
  };
}

// Carrega tudo UMA vez, com os pedidos em paralelo (antes eram em fila: disciplinas → turmas → histórico…).
// Catálogo, turmas, planos e histórico só mudam por ações da própria tela, que já atualizam a cópia local
// (`Planos`, `carregarAluno`); por isso trocar de aba não refaz os pedidos. Só a análise do plano é refeita.
let carregandoTudo = null;
async function loadData() {
  if (!S.curso) {
    carregandoTudo = carregandoTudo || carregarTudo().finally(() => { carregandoTudo = null; });
    await carregandoTudo;
  }
  if (S.curso && ['planner', 'calendario', 'dashboard'].includes(S.currentPage)) await analisarPlano();
}

async function carregarTudo() {
  const planosJaCarregados = Planos.carregado();
  const [resp, oferta, planosOk] = await Promise.all([
    GET(`/api/cursos/${CURSO_ID}/disciplinas`),
    GET(`/api/cursos/${CURSO_ID}/turmas`),
    planosJaCarregados ? true : Planos.carregar(),
    carregarAluno(),
  ]);
  S.preferencias = (await GET(`/api/cursos/${CURSO_ID}/preferencias`).catch(() => null))?.preferencias || {};
  if (!resp.ok) {
    toast(resp.erro || 'Não foi possível carregar o curso.', 'error');
    return;                       // S.curso continua nulo: a próxima tentativa recarrega
  }
  if (oferta.ok) {
    S.turmas = oferta.turmas;
    S.periodos = oferta.periodos;
    S.grade = oferta.grade;
  }
  S.disciplinas = resp.disciplinas.map(adaptarDisciplina);
  S.podeEditarCatalogo = !!resp.pode_editar_catalogo;
  document.getElementById('curso-ativo-nome').textContent = resp.curso.nome;
  document.title = `${resp.curso.nome} · Rumo`;

  if (!planosJaCarregados && planosOk) await Planos.migrarDoNavegador();
  S.planos = Planos.planos();
  S.currentPlano = Planos.atualId();
  S.curso = resp.curso;           // por último: marca "carregado"
}

// O painel calcula a formatura "pelo seu plano" com o plano aberto (ou o mais recente, se nenhum).
const assinaturaPainel = () => JSON.stringify([Planos.carregado() ? Planos.atualId() : null, Planos.carregado() && Planos.atual() ? Planos.paraAnalise() : null]);
function urlPainel() {
  const id = Planos.carregado() ? Planos.atualId() : null;
  S.painelAssinatura = assinaturaPainel();
  return `/api/cursos/${CURSO_ID}/painel${id ? `?plano_id=${id}` : ''}`;
}

// Depois de editar/criar uma disciplina: relê o catálogo (códigos dos requisitos mudam em outras
// disciplinas) e o painel (situação e progresso dependem do catálogo).
async function recarregarCatalogo() {
  const resp = await GET(`/api/cursos/${CURSO_ID}/disciplinas`);
  if (!resp.ok) return toast(resp.erro || 'Não foi possível recarregar as disciplinas.', 'error');
  S.disciplinas = resp.disciplinas.map(adaptarDisciplina);
  await carregarAluno();
  render();
}

// Histórico e painel do aluno (status, progresso, previsão). Rechamar depois de mudar o histórico.
async function carregarAluno() {
  const [h, p] = await Promise.all([
    GET(`/api/cursos/${CURSO_ID}/historico`),
    GET(urlPainel()),
  ]);
  if (!h.ok || !p.ok) toast(h.erro || p.erro || 'Não foi possível carregar seu histórico.', 'error');
  S.historico = h.ok ? h.historico : [];
  S.painel = p.ok ? p : null;
  S.situacoes = new Map((S.painel?.disciplinas || []).map(d => [d.id, d]));
  atualizarCaminho();
  atualizarRota();
}

// Trecho de linha na barra lateral: quanto do curso já foi percorrido.
function atualizarCaminho() {
  const caixa = document.getElementById('caminho');
  const bruto = S.painel?.progresso?.percentual;
  const pct = bruto == null ? null : Math.round(bruto);
  if (!caixa) return;
  caixa.hidden = pct == null;
  if (pct == null) return;
  document.getElementById('caminho-fill').style.width = pct + '%';
  document.getElementById('caminho-marca').style.left = pct + '%';
  document.getElementById('caminho-pct').textContent = pct + '%';
}

// Pede ao servidor o julgamento do plano atual (carga, requisitos, conflitos).
// Em falha mantém a última análise: a tela segue utilizável, sem inventar problemas.
async function analisarPlano(rodada = 0) {
  if (!Planos.atual()) { S.analise = []; return; }
  const r = await POST(`/api/cursos/${CURSO_ID}/plano/analisar`, Planos.paraAnalise());
  if (r.ok) {
    S.analise = r.semestres;
    // as turmas que o Rumo escolheu (ou ainda vazias) acompanham a melhor combinação; refaz a análise uma vez
    if (rodada === 0 && aplicarTurmasAutomaticas()) await analisarPlano(1);
  } else toast(r.erro || 'Não foi possível analisar o plano.', 'error');
}

// Turma automática: com quadro real no período, a disciplina sem turma (ou com turma escolhida pelo Rumo)
// recebe a da melhor combinação do semestre — sem choque e respeitando a sua rotina. A turma que VOCÊ
// escolhe fica fixa; "Automática" no seletor devolve a escolha ao Rumo. A regra é do servidor
// (`marcas.turma_sugerida`); aqui só se aplica.
function aplicarTurmasAutomaticas() {
  const plano = Planos.atual();
  if (!plano) return false;
  const trocas = [];
  plano.semestres.forEach((s, i) => {
    const marcas = S.analise?.[i]?.marcas || {};
    s.itens.forEach(it => {
      if (it.encontros_livres?.length) return;
      const sugerida = marcas[it.disciplina_id]?.turma_sugerida;
      if (sugerida && (it.turma_id == null || it.turma_auto) && it.turma_id !== sugerida) trocas.push([s.id, it.disciplina_id, sugerida]);
    });
  });
  if (trocas.length) Planos.definirTurmasAuto(trocas);
  return trocas.length > 0;
}

// Turmas ofertadas de uma disciplina (opcionalmente só as de um período).
function turmasDaDisciplina(discId, periodo) {
  return S.turmas.filter(t => t.disciplina_id === discId && (periodo == null || t.periodo_letivo === periodo));
}


// ═══════════════════════════════════════════════════════
// A ROTA: os 4 passos, na ordem em que se usa o Rumo.
// Fonte única: o menu (✓ nos passos feitos), a barra "Próximo passo" e o cartão do Painel leem daqui.
// `pular` = passo que não se aplica agora (ex.: sem quadro de horários importado, o Calendário não tem o que mostrar).
// ═══════════════════════════════════════════════════════
const planoComItens = () => S.planos.some(p => p.semestres.some(s => s.itens.length));
const ROTA = [
  {tela: 'historico', titulo: 'Informe o que você já cursou (opcional)', botao: 'Abrir histórico',
   texto: 'Opcional: libera pré-requisitos já cumpridos e a previsão pelo seu ritmo. Dá para pular.',
   pular: () => historicoPulado(), podePular: true,
   feito: () => S.historico.length > 0},
  {tela: 'rotina', titulo: 'Conte sua rotina (opcional)', botao: 'Abrir minha rotina',
   texto: 'Quando você não pode ter aula, seu ritmo e as optativas. Vale para o plano, a sugestão e o simulador.',
   pular: () => rotinaPulada(), feito: () => rotinaPreenchida()},
  {tela: 'planner', titulo: 'Monte o plano (ou peça uma sugestão)', botao: 'Abrir planejamento',
   texto: 'Arraste disciplinas para os semestres ou use “Sugerir plano”. As turmas são escolhidas sozinhas; você pode trocar.',
   feito: planoComItens},
  {tela: 'simulador', titulo: 'Teste o plano no Simulador', botao: 'Abrir simulador',
   texto: 'Formatura prevista, riscos de cada semestre e o que acontece se você reprovar.',
   feito: () => typeof SIM !== 'undefined' && SIM.sim.estado === 'ok'},
];
const passosDaRota = () => ROTA.filter(p => !(p.pular && p.pular()));
// Rotina "feita" = há algo guardado além das respostas automáticas.
function rotinaPreenchida() {
  const p = S.preferencias || {};
  return !!(p.indisponiveis?.length || p.turno || p.dias_livres?.length || p.max_pesadas || p.pesadas?.length
    || Object.keys(p.teto_por_periodo || {}).length || p.periodos_pulados?.length || p.juntas?.length
    || p.optativas_faltando != null || p.optativas_feitas?.length);
}
const chaveRotinaPulada = () => `rumo.rotina_pulada.${CURSO_ID}`;
function rotinaPulada() { try { return localStorage.getItem(chaveRotinaPulada()) === '1'; } catch (e) { return false; } }
window.pularRotina = () => {
  try { localStorage.setItem(chaveRotinaPulada(), '1'); } catch (e) { /* só não lembra */ }
  atualizarRota();
  if (S.currentPage === 'dashboard') dashboard(); else render();
};
// "Pular o histórico" é conveniência deste navegador (o app funciona igual sem histórico).
const chavePulo = () => `rumo.historico_pulado.${CURSO_ID}`;
function historicoPulado() { try { return localStorage.getItem(chavePulo()) === '1'; } catch (e) { return false; } }
window.pularHistorico = () => {
  try { localStorage.setItem(chavePulo(), '1'); } catch (e) { /* sem storage: só não lembra */ }
  atualizarRota();
  if (S.currentPage === 'dashboard') dashboard(); else render();
};

// Marca ✓ no menu e mostra, no rodapé, o próximo passo (só fora da tela dele e fora do Painel, que já tem o cartão).
function atualizarRota() {
  const ativos = passosDaRota();
  ROTA.forEach(p => {
    const el = document.querySelector(`.nav-item[data-page="${p.tela}"]`);
    if (!el) return;
    el.classList.toggle('feito', !!p.feito());
    el.classList.toggle('pulado', !ativos.includes(p));
  });
  const barra = document.getElementById('proximo-passo');
  if (!barra) return;
  const proximo = ativos.find(p => !p.feito());
  if (!S.curso || !proximo || proximo.tela === S.currentPage || S.currentPage === 'dashboard') { barra.hidden = true; return; }
  barra.innerHTML = `<span class="pp-rot">Próximo passo · ${ROTA.indexOf(proximo) + 1} de ${ROTA.length}</span>
    <b>${esc(proximo.titulo)}</b><span class="pp-txt">${esc(proximo.texto)}</span>
    <button class="btn btn-primary btn-sm" onclick="irPara('${proximo.tela}')">${esc(proximo.botao)} →</button>`;
  barra.hidden = false;
}

function irPara(page) {
  navTo(page, document.querySelector(`.nav-item[data-page="${page}"]`));
}

// Uma frase por tela: o que ela mostra e o que fazer aqui. Aparece sob o título.
const DICAS_DE_PAGINA = {
  dashboard: 'Onde você está e o que falta.',
  historico: 'Passo 1 de 4 · opcional · o que você já cursou.',
  rotina: 'Passo 2 de 4 · opcional · vale para o plano, a sugestão e o simulador.',
  planner: 'Passo 3 de 4 · monte à mão ou peça uma sugestão.',
  calendario: 'A semana do plano, semestre a semestre.',
  simulador: 'Passo 4 de 4 · avalia o plano aberto no Planejamento.',
  fluxograma: 'O curso por período. Clique numa disciplina.',
  disciplinas: 'Créditos, oferta par/ímpar e pré-requisitos.',
};

function render() {
  const titles = {
    dashboard: 'Painel',
    planner: 'Planejamento',      // iguais ao menu (consistência)
    fluxograma: 'Fluxograma',
    calendario: 'Calendário',
    historico: 'Histórico',
    rotina: 'Minha rotina',
    disciplinas: 'Disciplinas',
    simulador: 'Simulador',
  };
  document.getElementById('page-title').textContent = titles[S.currentPage] || '';
  document.getElementById('page-hint').textContent = DICAS_DE_PAGINA[S.currentPage] || '';
  const pages = { dashboard, planner, fluxograma, calendario, historico, disciplinas, simulador, rotina };
  const fn = pages[S.currentPage];
  if (fn) fn();
  atualizarRota();
}

// ═══════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════
// Situação de uma disciplina para o aluno: 'concluida' | 'cursando' | 'elegivel' | 'bloqueada'
// (calculada no servidor a partir do histórico). `null` se o painel não carregou.
const situacaoDe = discId => S.situacoes.get(discId) || null;
const getAprovados = () => new Set([...S.situacoes.values()].filter(d => d.situacao === 'concluida').map(d => d.id));
const getCursando = () => new Set([...S.situacoes.values()].filter(d => d.situacao === 'cursando').map(d => d.id));

// "Pré-requisito pendente: AAA100 ou BBB100" (uma linha por pendência).
function textoPendenciaPainel(p) {
  const nomes = p.alternativas.map(a => a.codigo).join(' ou ');
  return `${p.tipo === 'pre' ? 'Pré-requisito' : 'Correquisito'} pendente: ${nomes}`;
}

function getPlannedIds() {
  const ids = new Set();
  const plano = S.planos.find(p=>p.id===S.currentPlano);
  if (plano) plano.semestres.forEach(s => s.itens.forEach(i => ids.add(i.disciplina_id)));
  return ids;
}

// Escapa texto vindo do CSV antes de entrar em innerHTML (evita XSS armazenado).
function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function diaLabel(d) {
  return {SEG:'Seg',TER:'Ter',QUA:'Qua',QUI:'Qui',SEX:'Sex',SAB:'Sáb',DOM:'Dom'}[d] || d;
}

function horariosStr(horarios) {
  return horarios.map(h=>`${diaLabel(h.dia)} ${h.inicio}–${h.fim}`).join(', ');
}

// "T1 · Seg 16:00–18:00, Qui 14:00–16:00" (sem horários cadastrados: só o código).
function turmaRotulo(t) {
  const h = horariosStr(t.encontros);
  return h ? `${t.codigo_turma} · ${h}` : `${t.codigo_turma} · sem horários`;
}

// Desconhecido (null) aparece como "–", nunca como 0 ou "null".
function valorOu(v, sufixo = '') { return v == null ? '–' : `${v}${sufixo}`; }

function credStr(n) { return n == null ? '– créditos' : (n===1?'1 crédito':`${n} créditos`); }

// Em quais períodos letivos a disciplina é ofertada. `null` = o curso não informou (não é "sempre").
const PERIODICIDADE = {
  sempre: {curto: 'Todo período', longo: 'Todo período letivo (1 e 2)', cls: 'badge-green'},
  impar:  {curto: 'Só ímpar',     longo: 'Só períodos ímpares (AAAA/1)', cls: 'badge-blue'},
  par:    {curto: 'Só par',       longo: 'Só períodos pares (AAAA/2)',   cls: 'badge-purple'},
};
function periodicidadeBadge(p) {
  const x = PERIODICIDADE[p];
  return x ? `<span class="badge ${x.cls}" title="${esc(x.longo)}">${x.curto}</span>`
           : '<span class="badge" title="O curso não informou em quais períodos a disciplina é ofertada">Oferta não informada</span>';
}

// Selo de oferta ÚNICO (lista, cartão, calendário, simulador, fluxograma). A oferta efetiva vem do
// servidor (`d.oferta`: valor + origem cadastrada/estimada/desconhecida). Com `periodo`, destaca quando
// a disciplina não abre naquele período: vermelho se a oferta é cadastrada, amarelo se é estimada.
function abreEm(oferta, periodo) {
  if (!oferta || !periodo || oferta.valor === 'sempre') return true;
  const n = Number(String(periodo).split('/')[1]);
  return Number.isFinite(n) ? ((n % 2 === 1) === (oferta.valor === 'impar')) : true;
}
function ofertaDe(d) {
  return d.oferta || {valor: d.periodicidade || 'sempre', origem: d.periodicidade ? 'cadastrada' : 'desconhecida'};
}
function seloOferta(d, periodo = null) {
  const o = ofertaDe(d), est = o.origem === 'estimada';
  if (periodo && o.origem !== 'desconhecida' && !abreEm(o, periodo)) {
    return est
      ? `<span class="badge badge-yellow selo-oferta" title="Estimada pelo período sugerido na matriz: pode não abrir em ${esc(periodo)}">⚠ Talvez não abra em ${esc(periodo)}</span>`
      : `<span class="badge badge-red selo-oferta" title="${esc(PERIODICIDADE[o.valor].longo)}">✕ Não abre em ${esc(periodo)}</span>`;
  }
  if (o.origem === 'desconhecida') return '<span class="badge badge-gray selo-oferta" title="O curso não informou em quais períodos a disciplina é ofertada">Oferta ?</span>';
  const x = PERIODICIDADE[o.valor];
  return `<span class="badge ${x.cls} selo-oferta${est ? ' estimada' : ''}" title="${esc(x.longo)}${est ? ' — estimada pelo período sugerido' : ''}">${x.curto}${est ? ' (estimada)' : ''}</span>`;
}

// Tags prontas do servidor (choque, disponibilidade, sem horário, optativa): só desenha.
const COR_TAG = {red: 'badge-red', yellow: 'badge-yellow', gray: 'badge-gray', accent: 'badge-accent'};
function tagsProntas(tags) {
  return (tags || []).map(t => `<span class="badge ${COR_TAG[t.cor] || 'badge-gray'} tag-${esc(t.tipo)}">${esc(t.texto)}</span>`).join(' ');
}

function periodStr(n) {
  if (n == null) return 'Sem período sugerido';
  const ord = ['','1º','2º','3º','4º','5º','6º','7º','8º','9º','10º'];
  return (ord[n] || n+'º') + ' período';
}

function hexToRgb(hex) {
  const r = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return r ? `${parseInt(r[1],16)},${parseInt(r[2],16)},${parseInt(r[3],16)}` : '31,79,216';
}

