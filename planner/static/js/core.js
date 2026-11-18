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
const DEL  = p => api('DELETE', p);

// ═══════════════════════════════════════════════════════
// TOAST
// ═══════════════════════════════════════════════════════
function toast(msg, type='info', dur=3500) {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  el.addEventListener('click', () => el.remove());
  document.getElementById('toast-area').appendChild(el);
  setTimeout(() => el.remove(), type === 'error' ? Math.max(dur, 6000) : dur);   // erro fica mais tempo
}

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
  if (S.curso && ['planner', 'calendario'].includes(S.currentPage)) await analisarPlano();
}

async function carregarTudo() {
  const planosJaCarregados = Planos.carregado();
  const [resp, oferta, planosOk] = await Promise.all([
    GET(`/api/cursos/${CURSO_ID}/disciplinas`),
    GET(`/api/cursos/${CURSO_ID}/turmas`),
    planosJaCarregados ? true : Planos.carregar(),
    carregarAluno(),
  ]);
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
  document.getElementById('curso-ativo-nome').textContent = resp.curso.nome;
  document.title = `${resp.curso.nome} · Rumo`;

  if (!planosJaCarregados && planosOk) await Planos.migrarDoNavegador();
  S.planos = Planos.planos();
  S.currentPlano = Planos.atualId();
  S.curso = resp.curso;           // por último: marca "carregado"
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


// ═══════════════════════════════════════════════════════
// A ROTA: os 4 passos, na ordem em que se usa o Rumo.
// Fonte única: o menu (✓ nos passos feitos), a barra "Próximo passo" e o cartão do Painel leem daqui.
// `pular` = passo que não se aplica agora (ex.: sem quadro de horários importado, o Calendário não tem o que mostrar).
// ═══════════════════════════════════════════════════════
const planoComItens = () => S.planos.some(p => p.semestres.some(s => s.itens.length));
const ROTA = [
  {tela: 'historico', titulo: 'Informe o que você já cursou', botao: 'Abrir histórico',
   texto: 'Sem o histórico, nenhuma disciplina aparece como concluída e o progresso fica em zero.',
   feito: () => S.historico.length > 0},
  {tela: 'planner', titulo: 'Monte o plano dos próximos semestres', botao: 'Montar plano',
   texto: 'Arraste as disciplinas que pretende cursar. O Rumo avisa de pré-requisito faltando e choque de horário.',
   feito: planoComItens},
  {tela: 'calendario', titulo: 'Escolha turmas e horários', botao: 'Ver minha semana',
   texto: 'Veja o plano na semana e escolha a turma de cada disciplina sem bater horário.',
   pular: () => !S.turmas.length,
   feito: () => S.planos.some(p => p.semestres.some(s => s.itens.some(i => i.turma_id || i.encontros_livres?.length)))},
  {tela: 'simulador', titulo: 'Teste o futuro no Simulador', botao: 'Abrir simulador',
   texto: 'Veja a formatura prevista, os riscos de cada semestre e o que acontece se você reprovar.',
   feito: () => typeof SIM !== 'undefined' && SIM.sim.estado === 'ok'},
];
const passosDaRota = () => ROTA.filter(p => !(p.pular && p.pular()));

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
  dashboard: 'Onde você está na rota: quanto já fez, o que pode cursar agora e o que está travado por pré-requisito.',
  historico: 'Passo 1 de 4 · O que você já cursou. É daqui que o Rumo sabe o que está concluído e libera as próximas disciplinas.',
  planner: 'Passo 2 de 4 · Arraste disciplinas da lista para os semestres. Cada semestre mostra créditos, choques de horário e pré-requisitos faltando.',
  calendario: 'Passo 3 de 4 · A sua semana em horários, com as turmas do plano. Escolha o semestre e a turma de cada disciplina.',
  simulador: 'Passo 4 de 4 · E se eu seguir este plano? Mostra os riscos semestre a semestre e a formatura prevista, e sugere um plano melhor.',
  fluxograma: 'Mapa do curso por período. A cor de cada caixa diz se você já fez, está fazendo, pode fazer ou ainda está bloqueado. Clique para ver detalhes.',
  disciplinas: 'Todas as disciplinas do curso: créditos, em que períodos são ofertadas (par, ímpar ou sempre) e pré-requisitos. Informar par/ímpar deixa o Simulador exato.',
};

function render() {
  const titles = {
    dashboard: 'Painel',
    planner: 'Planejamento de Matrícula',
    fluxograma: 'Fluxograma Curricular',
    calendario: 'Calendário Semanal',
    historico: 'Histórico Acadêmico',
    disciplinas: 'Base de Disciplinas',
    simulador: 'Simulador',
  };
  document.getElementById('page-title').textContent = titles[S.currentPage] || '';
  document.getElementById('page-hint').textContent = DICAS_DE_PAGINA[S.currentPage] || '';
  const pages = { dashboard, planner, fluxograma, calendario, historico, disciplinas, simulador };
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

function periodStr(n) {
  if (n == null) return 'Sem período sugerido';
  const ord = ['','1º','2º','3º','4º','5º','6º','7º','8º','9º','10º'];
  return (ord[n] || n+'º') + ' período';
}

function hexToRgb(hex) {
  const r = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return r ? `${parseInt(r[1],16)},${parseInt(r[2],16)},${parseInt(r[3],16)}` : '31,79,216';
}

