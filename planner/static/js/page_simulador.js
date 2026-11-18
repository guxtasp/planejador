// ═══════════════════════════════════════════════════════
// PAGE: SIMULADOR (Peças 3 e 4)
// "E se eu seguir este plano?" (simulação) e "qual o melhor plano?" (sugestão).
// A tela só mostra o que o servidor devolve; os textos dos riscos já vêm prontos (`mensagem`, `acao`).
//
// REGRA DE FEEDBACK (vale para tudo aqui): toda ação tem 4 estados visíveis e escritos —
//   1. trabalhando  → texto "Simulando…" + botão desativado com o mesmo verbo;
//   2. deu certo    → faixa "Atualizado às HH:MM" (ou toast de sucesso que diz o que aconteceu e onde ver);
//   3. deu errado   → mensagem do servidor, por extenso, + botão "Tentar de novo";
//   4. vazio        → diz o que falta e oferece o botão que resolve.
// Nunca fica só a tela parada, só uma cor ou só um código técnico.
// ═══════════════════════════════════════════════════════
const SIM = {
  sim: {estado: 'vazio', dados: null, erro: null, quando: null, assinatura: null},
  sug: {estado: 'vazio', dados: null, erro: null, salvo: null},
  inicio: '',        // período inicial digitado ("" = deixa o servidor decidir)
  teto: '',          // limite de créditos pedido na sugestão
  extras: 0,         // folga voluntária (semestres a mais)
  optFaltando: '',   // créditos de optativas que a pessoa diz precisar ("" = o app calcula)
  optFeitas: new Set(), // optativas que a pessoa marcou como já feitas (só vale para a sugestão)
  feitasAberto: false,
  verTodos: false,   // lista completa de "e se eu reprovar"
  seq: 0,            // descarta respostas atrasadas (troca de plano no meio do pedido)
};

const GRAV = {
  alta:  {ico: '⛔', rotulo: 'Alta',  cls: 'g-alta'},
  media: {ico: '⚠', rotulo: 'Média', cls: 'g-media'},
  baixa: {ico: 'ℹ', rotulo: 'Baixa', cls: 'g-baixa'},
};
const VEREDITO_ICO = {ok: '✓', medio: '⚠', alto: '⛔'};

const horaAgora = () => new Date().toLocaleTimeString('pt-BR', {hour: '2-digit', minute: '2-digit'});
const chip = d => `<span class="tag" title="${esc(d.nome)}">${esc(d.codigo)}</span>`;
const nSem = n => `${n} semestre${n === 1 ? '' : 's'}`;
const planoTemItens = () => !!Planos.atual()?.semestres.some(s => s.itens.length);
// O servidor só decide o período sozinho se o plano ou o histórico trouxer algum. Senão a pessoa precisa dizer.
const temPeriodoNoHistorico = () => S.historico.some(h => h.periodo_letivo);
const planoTemPeriodo = () => !!Planos.atual()?.semestres.some(s => s.periodo_letivo);
const precisaDoPeriodo = () => !SIM.inicio && !planoTemPeriodo() && !temPeriodoNoHistorico();
const PERIODO_OK = /^\d{4}\s*[./-]\s*[12]$/;
const assinaturaDoPedido = () => JSON.stringify([Planos.atualId(), Planos.paraAnalise(), SIM.inicio]);

// ── blocos de feedback reutilizáveis ────────────────────────────────────
const faixa = (tipo, html) => `<div class="sim-faixa sim-${tipo}" role="status">${html}</div>`;
const carregando = txt => faixa('carregando', `<span class="sim-spin" aria-hidden="true"></span> ${esc(txt)}`);
const erroComRetentativa = (msg, fn) => `<div class="sim-faixa sim-erro" role="alert">
  <div><b>Não deu certo.</b> ${esc(msg)}</div><button class="btn btn-ghost btn-sm" onclick="${fn}()">Tentar de novo</button></div>`;

// ── entrada da tela ─────────────────────────────────────────────────────
function simulador() {
  const planos = Planos.planos();
  document.getElementById('topbar-actions').innerHTML =
    planoTemItens() ? `<button class="btn btn-primary btn-sm" id="sim-btn-topo" onclick="simRodar(true)">↻ Simular de novo</button>` : '';

  document.getElementById('content').innerHTML = `
    <div class="card sim-controles">
      <div class="form-group">
        <label class="form-label" for="sim-plano">Plano a simular</label>
        <select class="form-select" id="sim-plano" onchange="simTrocarPlano(this.value)" ${planos.length ? '' : 'disabled'}>
          ${planos.length ? planos.map(p => `<option value="${p.id}" ${p.id === Planos.atualId() ? 'selected' : ''}>${esc(p.nome)}</option>`).join('')
                          : '<option>Nenhum plano</option>'}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label" for="sim-inicio">Começa em</label>
        <input class="form-input" id="sim-inicio" placeholder="auto (ex.: 2027/1)" value="${esc(SIM.inicio)}"
               onchange="simMudarInicio(this.value)" inputmode="numeric" maxlength="7"/>
      </div>
    </div>
    <div id="sim-status"></div>
    <div id="sim-resultado"></div>
    <div id="sug-bloco"></div>`;
  desenharSimulacao();
  desenharSugestao();
  // Roda sozinha ao abrir (ou ao mudar o plano), mas só se o pedido mudou: voltar à aba não repete a conta.
  if (planoTemItens() && !precisaDoPeriodo() && SIM.sim.estado !== 'carregando' && SIM.sim.assinatura !== assinaturaDoPedido()) simRodar();
}

window.simTrocarPlano = id => { Planos.selecionar(Number(id)); S.currentPlano = Planos.atualId(); SIM.sim.assinatura = null; simulador(); };
// Valida no navegador (feedback imediato) antes de gastar uma ida ao servidor.
window.simUsarInicio = () => {
  const campo = document.getElementById('sim-inicio-pedido');
  const v = campo?.value.trim() ?? '';
  if (!PERIODO_OK.test(v)) { toast('Use o formato AAAA/N, por exemplo 2027/1.', 'error'); campo?.focus(); return; }
  SIM.inicio = v; SIM.sim.assinatura = null; simulador();
};
window.simMudarInicio = v => { SIM.inicio = v.trim(); SIM.sim.assinatura = null; simulador(); };

// ═══════════════════════════════════════════════════════
// SIMULAÇÃO
// ═══════════════════════════════════════════════════════
window.simRodar = async function (manual = false) {
  if (!planoTemItens()) { desenharSimulacao(); return; }
  const meu = ++SIM.seq;
  const assinatura = assinaturaDoPedido();
  SIM.sim = {...SIM.sim, estado: 'carregando', erro: null};
  desenharSimulacao();
  const corpo = {...Planos.paraAnalise()};
  if (SIM.inicio) corpo.periodo_inicial = SIM.inicio;
  const r = await POST(`/api/cursos/${CURSO_ID}/simulacao`, corpo);
  if (meu !== SIM.seq) return;                                  // chegou depois de o pedido ter mudado
  if (!r.ok) {
    SIM.sim = {...SIM.sim, estado: 'erro', erro: r.erro || 'Erro desconhecido ao simular.'};
  } else {
    SIM.sim = {estado: 'ok', dados: r, erro: null, quando: horaAgora(), assinatura};
    if (manual) toast('Simulação atualizada.', 'success', 2000);
  }
  desenharSimulacao();
  atualizarRota();
};

function desenharSimulacao() {
  const st = document.getElementById('sim-status'), res = document.getElementById('sim-resultado');
  if (!st || !res) return;
  const s = SIM.sim;
  const botao = document.getElementById('sim-btn-topo');
  if (botao) { botao.disabled = s.estado === 'carregando'; botao.textContent = s.estado === 'carregando' ? 'Simulando…' : '↻ Simular de novo'; }

  if (!planoTemItens()) {                                        // 4. vazio, com a ação que resolve
    st.innerHTML = '';
    res.innerHTML = `<div class="empty">${Planos.planos().length ? 'Este plano ainda não tem disciplinas.' : 'Você ainda não tem um plano.'}<br>
      Monte um plano para ver o que acontece semestre a semestre, ou peça uma sugestão logo abaixo.<br>
      <button class="btn btn-primary" onclick="irPara('planner')">Montar plano</button></div>`;
    return;
  }
  if (precisaDoPeriodo()) {                                      // falta um dado: pede aqui, sem ir ao servidor
    st.innerHTML = '';
    res.innerHTML = `<div class="sim-faixa sim-info" role="status"><div><b>Falta uma informação:</b> em que período este plano começa?<br>
      <small>Seu plano e seu histórico não têm período letivo, e o Rumo não adivinha pela data de hoje.</small></div>
      <span class="sim-inline"><input class="form-input" id="sim-inicio-pedido" placeholder="ex.: 2027/1" maxlength="7" aria-label="Período em que o plano começa"
        onkeydown="if(event.key==='Enter')simUsarInicio()"/><button class="btn btn-primary btn-sm" onclick="simUsarInicio()">Simular</button></span></div>`;
    return;
  }
  if (s.estado === 'carregando') {                               // 1. trabalhando
    st.innerHTML = carregando('Simulando os semestres do seu plano…');
    res.innerHTML = '<div class="skel-grid"><div class="skel"></div><div class="skel"></div><div class="skel alto"></div></div>';
    return;
  }
  if (s.estado === 'erro') {                                     // 3. deu errado
    st.innerHTML = erroComRetentativa(s.erro, 'simRodar');
    res.innerHTML = '';
    return;
  }
  if (s.estado !== 'ok') { st.innerHTML = ''; res.innerHTML = ''; return; }
  const d = s.dados;                                             // 2. deu certo
  st.innerHTML = faixa('ok', `✓ Simulação atualizada às ${esc(s.quando)} · começa em <b>${esc(d.periodo_inicial)}</b> · ${nSem(d.resumo.n_semestres)} com disciplinas`);
  res.innerHTML = [blocoVisaoGeral(d), blocoRiscos(d), blocoLinhaDoTempo(d), blocoReprovar(d), blocoCritico(d), blocoPremissas(d)].join('');
}

// ── 1. visão geral ──────────────────────────────────────────────────────
function blocoVisaoGeral(d) {
  const r = d.resumo, v = d.veredito;
  const formatura = r.formatura_prevista
    ? {valor: r.formatura_prevista, sub: 'O plano fecha o curso'}
    : r.formatura_estimada
      ? {valor: r.formatura_estimada, sub: 'Estimativa: o plano não fecha o curso'}
      : {valor: '–', sub: r.completo === null ? 'O curso não informa os créditos exigidos' : 'Sem previsão'};
  const g = r.riscos_por_gravidade;
  const faltam = r.faltam_obrigatorias.length
    ? `<div class="sim-nota">Faltam obrigatórias no plano: ${r.faltam_obrigatorias.map(chip).join(' ')}</div>` : '';
  return `<section class="sim-bloco">
    <div class="sim-veredito v-${esc(v.nivel)}"><span class="sim-veredito-ico" aria-hidden="true">${VEREDITO_ICO[v.nivel]}</span>
      <div><b>${esc(v.titulo)}</b><div>${esc(v.texto)}</div></div></div>
    <div class="grid-4">
      <div class="stat-card"><div class="stat-label">Formatura</div><div class="stat-value">${esc(formatura.valor)}</div><div class="stat-sub">${esc(formatura.sub)}</div></div>
      <div class="stat-card"><div class="stat-label">Créditos no plano</div><div class="stat-value">${r.creditos_planejados}</div>
        <div class="stat-sub">${r.creditos_restantes == null ? 'Restantes: –' : `Restam ${r.creditos_restantes} depois dele`}</div></div>
      <div class="stat-card"><div class="stat-label">Riscos</div><div class="stat-value">${g.alta + g.media + g.baixa}</div>
        <div class="stat-sub">${g.alta} alta · ${g.media} média · ${g.baixa} baixa</div></div>
      <div class="stat-card"><div class="stat-label">Pior caso se reprovar</div><div class="stat-value">${r.atraso_maximo_reprovacao ? '+' + nSem(r.atraso_maximo_reprovacao) : 'Sem atraso'}</div>
        <div class="stat-sub">numa única disciplina</div></div>
    </div>${faltam}</section>`;
}

// ── 2. riscos ───────────────────────────────────────────────────────────
function itemRisco(x) {
  const g = GRAV[x.gravidade];
  const onde = x.posicao ? `Semestre ${x.posicao} · ${esc(x.periodo)}` : 'Plano inteiro';
  return `<li class="risco ${g.cls}">
    <span class="risco-ico" aria-hidden="true">${g.ico}</span>
    <div class="risco-corpo">
      <div><b>${esc(x.mensagem)}</b></div>
      ${x.acao ? `<div class="risco-acao">→ ${esc(x.acao)}</div>` : ''}
      <div class="risco-meta"><span class="badge badge-gray">${g.rotulo}</span> ${onde}</div>
    </div></li>`;
}

function blocoRiscos(d) {
  const fortes = d.riscos.filter(x => x.gravidade !== 'baixa');
  const fracos = d.riscos.filter(x => x.gravidade === 'baixa');
  const corpo = d.riscos.length === 0
    ? `<div class="sim-nota ok">✓ Nenhum risco encontrado com os dados que o curso informou.</div>`
    : `${fortes.length ? `<ul class="riscos">${fortes.map(itemRisco).join('')}</ul>` : '<div class="sim-nota ok">✓ Nenhum risco alto ou médio.</div>'}
       ${fracos.length ? `<details class="sim-mais"><summary>${fracos.length} aviso${fracos.length > 1 ? 's' : ''} menor${fracos.length > 1 ? 'es' : ''} (informativos)</summary>
         <ul class="riscos">${fracos.map(itemRisco).join('')}</ul></details>` : ''}`;
  return `<section class="sim-bloco"><h3>O que pode dar errado</h3>${corpo}
    ${d.riscos.length ? `<div class="sim-acoes"><button class="btn btn-ghost btn-sm" onclick="irPara('planner')">Ajustar no Planejamento</button></div>` : ''}</section>`;
}

// ── 3. linha do tempo ───────────────────────────────────────────────────
function selosDoItem(i) {
  const s = [];
  if (!i.ofertada) s.push('<span class="badge badge-red" title="A oferta cadastrada diz que não abre neste período">✕ Não abre neste período</span>');
  else if (i.origem_periodicidade === 'estimada') s.push('<span class="badge badge-yellow" title="Estimada pelo período sugerido na matriz">Oferta estimada</span>');
  else if (i.origem_periodicidade === 'desconhecida') s.push('<span class="badge badge-gray" title="O curso não informou a oferta">Oferta ?</span>');
  if (i.horario_origem === 'projetado') s.push(`<span class="badge badge-gray" title="Copiado de ${esc(i.periodo_da_turma || 'outro período')}">Horário projetado</span>`);
  else if (i.horario_origem === 'desconhecido') s.push('<span class="badge badge-gray">Sem horário</span>');
  else if (i.horario_origem === 'proprio') s.push('<span class="badge badge-accent">Horário próprio</span>');
  return s.join(' ');
}

function cartaoSemestre(s, riscos) {
  const meus = riscos.filter(x => x.posicao === s.posicao);
  const altos = meus.filter(x => x.gravidade === 'alta').length;
  const pct = s.limite_creditos ? Math.min(100, Math.round(s.creditos / s.limite_creditos * 100)) : null;
  return `<div class="sim-sem ${altos ? 'tem-alto' : ''}">
    <div class="sim-sem-topo"><b>${s.posicao}º · ${esc(s.periodo)}</b><span class="badge badge-gray">${s.paridade === 'impar' ? 'ímpar' : 'par'}</span>
      ${altos ? `<span class="badge badge-red">⛔ ${altos} problema${altos > 1 ? 's' : ''}</span>` : meus.length ? `<span class="badge badge-yellow">${meus.length} aviso${meus.length > 1 ? 's' : ''}</span>` : '<span class="badge badge-green">✓ ok</span>'}
    </div>
    <div class="sim-carga" title="${s.creditos}${s.limite_creditos ? ' de ' + s.limite_creditos : ''} créditos">
      ${pct == null ? '' : `<div class="progress-bar"><div class="progress-fill ${s.sobrecarga ? 'estouro' : ''}" style="width:${pct}%"></div></div>`}
      <span>${s.creditos}${s.limite_creditos ? ' / ' + s.limite_creditos : ''} créditos${s.sem_creditos.length ? ` (sem créditos informados: ${esc(s.sem_creditos.join(', '))})` : ''}</span>
    </div>
    <ul class="sim-itens">${s.itens.map(i => `<li>
      <span class="sim-disc"><b>${esc(i.disciplina.codigo)}</b> ${esc(i.disciplina.nome)}</span>
      <span class="sim-selos">${selosDoItem(i)}${i.encontros.length ? ` <small>${esc((i.turma_codigo ? i.turma_codigo + ' · ' : '') + horariosStr(i.encontros))}</small>` : ''}</span></li>`).join('')}</ul>
  </div>`;
}

function blocoLinhaDoTempo(d) {
  return `<section class="sim-bloco"><h3>Linha do tempo</h3>
    <div class="sim-timeline">${d.semestres.map(s => cartaoSemestre(s, d.riscos)).join('')}</div></section>`;
}

// ── 4. e se eu reprovar ─────────────────────────────────────────────────
window.simVerTodos = () => { SIM.verTodos = !SIM.verTodos; desenharSimulacao(); };

function blocoReprovar(d) {
  const todos = d.cenarios;
  if (!todos.length) {
    return `<section class="sim-bloco"><h3>E se eu reprovar?</h3><div class="empty" style="padding:12px">Sem cenários: não há disciplinas no plano que possam ser cursadas na simulação.</div></section>`;
  }
  const mostrados = SIM.verTodos ? todos : todos.slice(0, 6);
  const semEfeito = todos.every(c => c.atraso === 0);
  return `<section class="sim-bloco"><h3>E se eu reprovar?</h3>
    ${semEfeito ? '<div class="sim-nota ok">✓ Reprovar em qualquer uma delas não atrasa a formatura: o plano tem folga.</div>' : ''}
    <ul class="cenarios">${mostrados.map(c => `<li>
      <span class="badge ${c.atraso >= 2 ? 'badge-red' : c.atraso === 1 ? 'badge-yellow' : 'badge-green'}">${c.atraso ? '+' + nSem(c.atraso) : 'Sem atraso'}</span>
      <div>${esc(c.mensagem)}${c.afetadas.length ? `<div class="risco-meta">Também escorregam: ${c.afetadas.map(chip).join(' ')}</div>` : ''}</div></li>`).join('')}</ul>
    ${todos.length > 6 ? `<button class="btn btn-ghost btn-sm" onclick="simVerTodos()">${SIM.verTodos ? 'Mostrar só os piores' : `Ver todos (${todos.length})`}</button>` : ''}
  </section>`;
}

// ── 5. caminho crítico ──────────────────────────────────────────────────
function blocoCritico(d) {
  const c = d.critico;
  if (c.menor_semestres === 0) return '';
  const alertas = [
    c.ciclos.length ? `<div class="sim-nota erro">Pré-requisitos circulares: ${c.ciclos[0].map(chip).join(' → ')}. Revise o CSV do curso.</div>` : '',
    c.inalcancaveis.length ? `<div class="sim-nota erro">Não cabem em nenhum período (oferta e requisitos se contradizem): ${c.inalcancaveis.map(chip).join(' ')}</div>` : '',
  ].join('');
  const prazo = c.menor_semestres == null ? 'Sem prazo possível dentro do horizonte.'
    : `O menor prazo possível para o que falta é <b>${nSem(c.menor_semestres)}</b>${c.menor_sem_calendario != null && c.custo_da_oferta > 0
      ? `; a oferta par/ímpar custa ${nSem(c.custo_da_oferta)} (seriam ${c.menor_sem_calendario} se tudo abrisse todo semestre)` : ''}.`;
  return `<section class="sim-bloco"><h3>Caminho crítico</h3>
    <p class="sim-texto">${prazo} Estas disciplinas não podem atrasar sem atrasar a formatura:</p>
    ${alertas}
    <ol class="etapas">${c.etapas.map(e => `<li><b>${esc(e.periodo)}</b> ${e.disciplinas.map(chip).join(' ')}</li>`).join('')}</ol>
    ${c.gargalos.length ? `<p class="sim-texto">Quem mais destrava outras: ${c.gargalos.map(g => `${chip(g.disciplina)} <small>(${g.dependentes})</small>`).join(' · ')}</p>` : ''}
  </section>`;
}

// ── 6. premissas ────────────────────────────────────────────────────────
function blocoPremissas(d) {
  return `<details class="sim-bloco sim-mais"><summary>Como esta simulação foi calculada</summary>
    <ul class="sim-premissas">${d.premissas.map(p => `<li>${esc(p.texto)}</li>`).join('')}</ul></details>`;
}

// ═══════════════════════════════════════════════════════
// SUGESTÃO (otimização)
// ═══════════════════════════════════════════════════════
// Quanto o app calcularia sozinho: exigido pelo curso − optativas cumpridas (histórico + as marcadas aqui).
function optCalculadas() {
  const pr = S.painel?.progresso;
  if (!pr || pr.optativos_exigidos == null) return null;       // o curso não informa o total
  const marcadas = [...SIM.optFeitas].reduce((n, id) => n + (S.disciplinas.find(d => d.id === id)?.creditos || 0), 0);
  return Math.max(0, pr.optativos_exigidos - pr.optativos_validos - marcadas);
}
// Optativas/eletivas que ainda não constam como concluídas ou em curso no histórico.
function optativasMarcaveis() {
  const feita = id => ['CONCLUIDA', 'CURSANDO'].includes(String(S.situacoes.get(id)?.situacao || '').toUpperCase());
  return S.disciplinas.filter(d => d.tipo !== 'obrigatoria' && !feita(d.id));
}
window.simAlternarFeita = (id, marcada) => {
  marcada ? SIM.optFeitas.add(id) : SIM.optFeitas.delete(id);
  const campo = document.getElementById('sug-opt');
  if (campo && !campo.value.trim()) { const c = optCalculadas(); campo.placeholder = c == null ? 'o curso não informa' : `auto: ${c}`; }
  const n = document.getElementById('sug-feitas-n');
  if (n) n.textContent = SIM.optFeitas.size ? ` (${SIM.optFeitas.size} marcadas)` : '';
};

window.simSugerir = async function () {
  SIM.inicio = document.getElementById('sug-inicio')?.value.trim() ?? SIM.inicio;
  SIM.teto = document.getElementById('sug-teto')?.value.trim() ?? SIM.teto;
  SIM.extras = Number(document.getElementById('sug-extras')?.value ?? SIM.extras);
  SIM.optFaltando = document.getElementById('sug-opt')?.value.trim() ?? SIM.optFaltando;
  if (SIM.optFaltando !== '' && !(Number.isInteger(Number(SIM.optFaltando)) && Number(SIM.optFaltando) >= 0)) { toast('Em “Optativas que ainda preciso”, use um número inteiro de créditos (0 ou mais).', 'error'); document.getElementById('sug-opt')?.focus(); return; }
  if (SIM.inicio && !PERIODO_OK.test(SIM.inicio)) { toast('Período inválido. Use AAAA/N, por exemplo 2027/1.', 'error'); document.getElementById('sug-inicio')?.focus(); return; }
  if (precisaDoPeriodo()) { toast('Preencha “Começa em” (ex.: 2027/1): seu histórico ainda não tem períodos.', 'error'); document.getElementById('sug-inicio')?.focus(); return; }
  const corpo = {semestres_extras: SIM.extras};
  if (SIM.inicio) corpo.periodo_inicial = SIM.inicio;
  if (SIM.teto) corpo.max_creditos = Number(SIM.teto);
  if (SIM.optFaltando !== '') corpo.optativas_faltando = Number(SIM.optFaltando);
  if (SIM.optFeitas.size) corpo.optativas_feitas = [...SIM.optFeitas];
  SIM.sug = {...SIM.sug, estado: 'carregando', erro: null, salvo: null};
  desenharSugestao();
  const r = await POST(`/api/cursos/${CURSO_ID}/simulacao/sugerir`, corpo);
  SIM.sug = r.ok ? {estado: 'ok', dados: r, erro: null, salvo: null}
                 : {...SIM.sug, estado: 'erro', erro: r.erro || 'Erro desconhecido ao gerar a sugestão.'};
  desenharSugestao();
};

window.simSalvarSugestao = async function () {
  const d = SIM.sug.dados;
  if (!d?.viavel) return;
  const btn = document.getElementById('sug-salvar');
  if (btn) { btn.disabled = true; btn.textContent = 'Salvando…'; }
  const plano = await Planos.criarComConteudo(d.plano);        // já avisa o erro por toast
  if (!plano) { if (btn) { btn.disabled = false; btn.textContent = 'Salvar como plano'; } SIM.sug.erroSalvar = 'Não foi possível salvar o plano. Seu plano atual não foi alterado.'; desenharSugestao(); return; }
  S.planos = Planos.planos(); S.currentPlano = Planos.atualId();
  SIM.sim.assinatura = null;
  SIM.sug.erroSalvar = null;
  SIM.sug.salvo = plano.nome;
  toast(`Plano “${plano.nome}” criado e selecionado. Está em Planejamento.`, 'success', 5000);
  desenharSugestao();
};

function desenharSugestao() {
  const alvo = document.getElementById('sug-bloco');
  if (!alvo) return;
  const g = SIM.sug, ocupado = g.estado === 'carregando';
  const tetoCurso = S.curso?.max_creditos_semestre;
  alvo.innerHTML = `<section class="sim-bloco sim-sugestao">
    <h3>Sugerir um plano</h3>
    <p class="sim-texto">Distribui o que falta cursar respeitando pré-requisitos, oferta par/ímpar, limite de créditos e choques de horário.</p>
    <div class="sug-form">
      <div class="form-group"><label class="form-label" for="sug-inicio">Começa em</label>
        <input class="form-input" id="sug-inicio" placeholder="${precisaDoPeriodo() ? 'obrigatório: 2027/1' : 'auto (ex.: 2027/1)'}" value="${esc(SIM.inicio)}" maxlength="7" ${ocupado ? 'disabled' : ''}/></div>
      <div class="form-group"><label class="form-label" for="sug-teto">Máx. créditos por semestre</label>
        <input class="form-input" id="sug-teto" type="number" min="1" max="60" placeholder="${tetoCurso ? 'curso: ' + tetoCurso : 'sem limite'}" value="${esc(SIM.teto)}" ${ocupado ? 'disabled' : ''}/></div>
      <div class="form-group"><label class="form-label" for="sug-extras">Ritmo</label>
        <select class="form-select" id="sug-extras" ${ocupado ? 'disabled' : ''}>
          ${[[0, 'O mais rápido possível'], [1, 'Mais leve (+1 semestre)'], [2, 'Bem leve (+2 semestres)']].map(([v, t]) => `<option value="${v}" ${SIM.extras === v ? 'selected' : ''}>${t}</option>`).join('')}
        </select></div>
      <div class="form-group"><label class="form-label" for="sug-opt">Optativas que ainda preciso (créditos)</label>
        <input class="form-input" id="sug-opt" type="number" min="0" max="120" value="${esc(SIM.optFaltando)}"
               placeholder="${optCalculadas() == null ? 'o curso não informa' : 'auto: ' + optCalculadas()}" ${ocupado ? 'disabled' : ''}/></div>
      <button class="btn btn-primary" onclick="simSugerir()" ${ocupado ? 'disabled' : ''}>${ocupado ? 'Calculando…' : g.dados ? 'Gerar de novo' : 'Gerar sugestão'}</button>
    </div>
    ${optativasMarcaveis().length ? `<details class="sug-feitas" ${SIM.feitasAberto ? 'open' : ''} ontoggle="SIM.feitasAberto = this.open">
      <summary>Já fiz alguma optativa que não está no histórico?<span id="sug-feitas-n">${SIM.optFeitas.size ? ` (${SIM.optFeitas.size} marcadas)` : ''}</span></summary>
      <div class="sug-feitas-lista">${optativasMarcaveis().map(d => `<label class="sug-feita"><input type="checkbox" ${SIM.optFeitas.has(d.id) ? 'checked' : ''} ${ocupado ? 'disabled' : ''}
        onchange="simAlternarFeita(${d.id}, this.checked)"/> <b>${esc(d.codigo)}</b> ${esc(d.nome)}${d.creditos ? ` · ${d.creditos} cr` : ''}</label>`).join('')}</div>
    </details>` : ''}
    <div id="sug-saida">${corpoSugestao(g)}</div>
  </section>`;
}

// Datas de formatura lado a lado (só obrigatórias × com optativas) e o que aconteceu com as optativas.
function blocoOptativas(d) {
  const o = d.optativas, f = d.formatura;
  if (!o || !f) return '';
  const origem = o.origem === 'informado'
    ? `Usamos os <b>${o.pedidas}</b> créditos de optativas que você informou.`
    : (o.exigidas_pelo_curso == null ? '' : `Optativas: o curso exige ${o.exigidas_pelo_curso} créditos e você já tem ${o.ja_cumpridas}; faltam <b>${o.calculadas}</b>.`);
  const cartoes = f.optativas_adiam
    ? `<div class="grid-4"><div class="stat-card"><div class="stat-label">Formatura só com as obrigatórias</div><div class="stat-value">${esc(f.so_obrigatorias)}</div><div class="stat-sub">sem fechar as optativas</div></div>
       <div class="stat-card"><div class="stat-label">Formatura com as optativas</div><div class="stat-value">${esc(f.com_optativas || '—')}</div><div class="stat-sub">faltam encaixar ${o.sem_encaixe} créditos</div></div></div>`
    : '';
  const aviso = o.mensagem ? `<div class="sim-nota ${f.optativas_adiam ? 'sim-nota-aviso' : ''}">${esc(o.mensagem)}</div>` : '';
  return `${origem ? `<div class="sim-nota">${origem}</div>` : ''}${cartoes}${aviso}`;
}

function corpoSugestao(g) {
  if (g.estado === 'carregando') return carregando('Calculando o melhor plano… leva alguns segundos.');
  if (g.estado === 'erro') return erroComRetentativa(g.erro, 'simSugerir');
  if (g.estado !== 'ok') return '<div class="sim-nota">Preencha se quiser e clique em “Gerar sugestão”. Em branco, usamos o limite do curso e o período seguinte ao seu histórico.</div>';
  const d = g.dados;
  if (!d.viavel) return `<div class="sim-faixa sim-erro" role="alert"><div><b>Não existe plano possível.</b> ${esc(d.mensagem)}<div class="risco-acao">→ ${esc(d.acao)}</div></div></div>`;
  const m = d.metricas;
  if (!d.semestres.length) return faixa('ok', '✓ Não há nada a cursar: o curso já está completo.');
  return `${faixa('ok', `✓ Sugestão pronta · começa em <b>${esc(d.periodo_inicial)}</b> e as obrigatórias terminam em <b>${esc(m.periodo_fim)}</b>`)}
    <p class="sim-texto"><b>${esc(d.explicacao)}</b></p>
    <div class="grid-4">
      <div class="stat-card"><div class="stat-label">Semestres</div><div class="stat-value">${m.n_semestres}</div><div class="stat-sub">mínimo teórico: ${d.limite_inferior}</div></div>
      <div class="stat-card"><div class="stat-label">Carga média</div><div class="stat-value">${m.carga_media}</div><div class="stat-sub">máx. ${m.carga_maxima} · variação ±${m.carga_desvio}</div></div>
      <div class="stat-card"><div class="stat-label">Choques de horário</div><div class="stat-value">${m.colisoes}</div><div class="stat-sub">${m.colisoes ? 'sem saída com os horários conhecidos' : 'nenhum previsto'}</div></div>
      <div class="stat-card"><div class="stat-label">Se reprovar (média)</div><div class="stat-value">+${m.atraso_medio_reprovacao}</div><div class="stat-sub">semestres · pior caso +${m.atraso_maximo_reprovacao}</div></div>
    </div>
    ${blocoOptativas(d)}
    ${d.incluidas_por_requisito.length ? `<div class="sim-nota">Entraram por serem exigidas por outras: ${d.incluidas_por_requisito.map(chip).join(' ')}</div>` : ''}
    <div class="sim-timeline">${d.semestres.map(s => `<div class="sim-sem ${s.colisoes.length ? 'tem-alto' : ''}">
      <div class="sim-sem-topo"><b>${s.posicao}º · ${esc(s.periodo)}</b><span class="badge badge-gray">${s.creditos + s.creditos_optativos} créditos</span>
        ${s.colisoes.length ? `<span class="badge badge-red">⛔ choque</span>` : ''}</div>
      <ul class="sim-itens">${s.itens.map(i => { const x = S.disciplinas.find(z => z.id === i.disciplina.id);
        return `<li><span class="sim-disc"><b>${esc(i.disciplina.codigo)}</b> ${esc(i.disciplina.nome)}</span>
          <span class="sim-selos">${x ? periodicidadeBadge(x.periodicidade) : ''}${i.horario_origem === 'projetado' ? ' <span class="badge badge-gray">Horário projetado</span>' : ''}</span></li>`; }).join('')}
        ${s.creditos_optativos ? `<li class="sim-reserva">Reservar ${s.creditos_optativos} créditos de optativas</li>` : ''}</ul>
      ${s.colisoes.map(c => `<div class="risco-meta">Choque na ${esc(diaLabel(c.dia))}: ${esc(c.a.codigo)} × ${esc(c.b.codigo)}</div>`).join('')}
    </div>`).join('')}</div>
    ${g.erroSalvar ? `<div class="sim-faixa sim-erro" role="alert"><div><b>Não deu certo.</b> ${esc(g.erroSalvar)}</div></div>` : ''}
    <div class="sim-acoes">
      ${g.salvo
        ? `<span class="sim-ok">✓ Salvo como “${esc(g.salvo)}”.</span> <button class="btn btn-primary btn-sm" onclick="irPara('planner')">Abrir no Planejamento</button>`
        : `<button class="btn btn-primary btn-sm" id="sug-salvar" onclick="simSalvarSugestao()">Salvar como plano</button>
           <span class="sim-dica">Cria um plano novo; o seu atual não é alterado.</span>`}
    </div>`;
}
