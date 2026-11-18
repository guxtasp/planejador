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
  currentPage: 'fluxograma',
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
const DEL  = p => api('DELETE', p);

// ═══════════════════════════════════════════════════════
// TOAST
// ═══════════════════════════════════════════════════════
function toast(msg, type='info', dur=3500) {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.getElementById('toast-area').appendChild(el);
  setTimeout(() => el.remove(), dur);
}

// ═══════════════════════════════════════════════════════
// MODAL
// ═══════════════════════════════════════════════════════
function openModal(html) {
  document.getElementById('modal-box').innerHTML = html;
  document.getElementById('modal-overlay').style.display = 'flex';
}
function closeModal() {
  document.getElementById('modal-overlay').style.display = 'none';
}

// ═══════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════
async function navTo(page, el) {
  S.currentPage = page;
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  if (el) el.classList.add('active');
  document.getElementById('topbar-actions').innerHTML = '';
  await loadData();
  render();
}

// Cores só de exibição (não são gravadas): usadas quando a disciplina não tem `cor`.
const COR_PADRAO = {obrigatoria: '#6366f1', optativa: '#14b8a6', eletiva: '#f59e0b'};

// A API nova usa nomes do banco (`periodo_sugerido`, `requisitos`); as telas
// herdadas esperam `periodo`, `prerequisitos`, `horarios`. Este é o único
// ponto de tradução. Campos desconhecidos continuam `null` (nunca viram 0).
function adaptarDisciplina(d) {
  return {
    ...d,
    periodo: d.periodo_sugerido,
    cor: d.cor || COR_PADRAO[d.tipo] || '#6366f1',
    prerequisitos: d.requisitos || [],
    horarios: [],   // horários vêm das turmas (Etapa 4B)
  };
}

async function loadData() {
  const resp = await GET(`/api/cursos/${CURSO_ID}/disciplinas`);
  if (!resp.ok) {
    toast(resp.erro || 'Não foi possível carregar o curso.', 'error');
    return;
  }
  S.curso = resp.curso;
  document.getElementById('curso-ativo-nome').textContent = S.curso.nome;
  document.title = `${S.curso.nome} · Planejador Acadêmico`;
  S.disciplinas = resp.disciplinas.map(adaptarDisciplina);

  const oferta = await GET(`/api/cursos/${CURSO_ID}/turmas`);
  if (oferta.ok) {
    S.turmas = oferta.turmas;
    S.periodos = oferta.periodos;
    S.grade = oferta.grade;
  }

  // Planos: o servidor é carregado UMA vez; depois a cópia local é a fonte (ver plano_store.js).
  if (!Planos.carregado()) {
    if (await Planos.carregar()) await Planos.migrarDoNavegador();
  }
  S.planos = Planos.planos();
  S.currentPlano = Planos.atualId();

  await carregarAluno();
  if (['planner', 'calendario'].includes(S.currentPage)) await analisarPlano();
}

// Histórico e painel do aluno (status, progresso, previsão). Rechamar depois de mudar o histórico.
async function carregarAluno() {
  const [h, p] = await Promise.all([
    GET(`/api/cursos/${CURSO_ID}/historico`),
    GET(`/api/cursos/${CURSO_ID}/painel`),
  ]);
  if (!h.ok || !p.ok) toast(h.erro || p.erro || 'Não foi possível carregar seu histórico.', 'error');
  S.historico = h.ok ? h.historico : [];
  S.painel = p.ok ? p : null;
  S.situacoes = new Map((S.painel?.disciplinas || []).map(d => [d.id, d]));
}

// Pede ao servidor o julgamento do plano atual (carga, requisitos, conflitos).
// Em falha mantém a última análise: a tela segue utilizável, sem inventar problemas.
async function analisarPlano() {
  if (!Planos.atual()) { S.analise = []; return; }
  const r = await POST(`/api/cursos/${CURSO_ID}/plano/analisar`, Planos.paraAnalise());
  if (r.ok) S.analise = r.semestres;
  else toast(r.erro || 'Não foi possível analisar o plano.', 'error');
}

// Turmas ofertadas de uma disciplina (opcionalmente só as de um período).
function turmasDaDisciplina(discId, periodo) {
  return S.turmas.filter(t => t.disciplina_id === discId && (periodo == null || t.periodo_letivo === periodo));
}

function irPara(page) {
  navTo(page, document.querySelector(`.nav-item[data-page="${page}"]`));
}

function render() {
  const titles = {
    dashboard: 'Dashboard',
    planner: 'Planejamento de Matrícula',
    fluxograma: 'Fluxograma Curricular',
    calendario: 'Calendário Semanal',
    historico: 'Histórico Acadêmico',
    disciplinas: 'Base de Disciplinas',
  };
  document.getElementById('page-title').textContent = titles[S.currentPage] || '';
  const pages = { dashboard, planner, fluxograma, calendario, historico, disciplinas };
  const fn = pages[S.currentPage];
  if (fn) fn();
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

function periodStr(n) {
  if (n == null) return 'Sem período sugerido';
  const ord = ['','1º','2º','3º','4º','5º','6º','7º','8º','9º','10º'];
  return (ord[n] || n+'º') + ' período';
}

function hexToRgb(hex) {
  const r = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return r ? `${parseInt(r[1],16)},${parseInt(r[2],16)},${parseInt(r[3],16)}` : '99,102,241';
}

