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
  pref: null,        // preferências do aluno (lembradas neste navegador, por curso)
  prefAberto: false,
  erroCampo: null,   // {campo, msg}: erro de validação mostrado junto ao campo
  aba: 'geral',      // aba aberta: geral | riscos | semestres | reprovar | probabilidade | sugestao
};
// A sugestão saiu daqui: ela CRIA um plano e mora no Planejamento ("Sugerir plano"). O Simulador só AVALIA.
const ABAS = [['geral', 'Visão geral'], ['riscos', 'Riscos'], ['semestres', 'Semestres'],
              ['reprovar', 'E se reprovar'], ['probabilidade', 'Probabilidade']];

// ── preferências do aluno (Fase 2) ──────────────────────────────────────
const PREF_VAZIA = () => ({indisponiveis: [], turno: '', dias_livres: [], max_pesadas: '', pesadas: [],
  tetos: [], pulados: '', ingresso: '', fator: '', opt_faltando: '', opt_feitas: [], fixas: []});
const DIAS_PREF = ['SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SAB'];
// Formulário ⇄ forma guardada no servidor (S.preferencias, carregada uma vez com o curso).
function prefDoServidor(g) {
  g = g || {};
  return {...PREF_VAZIA(), indisponiveis: (g.indisponiveis || []).map(b => ({motivo: '', ...b})), turno: g.turno || '',
    dias_livres: g.dias_livres || [], max_pesadas: g.max_pesadas ?? '', pesadas: g.pesadas || [],
    tetos: Object.entries(g.teto_por_periodo || {}).map(([periodo, creditos]) => ({periodo, creditos})),
    pulados: (g.periodos_pulados || []).join(', '), ingresso: g.periodo_ingresso || '',
    fator: g.fator_prazo_maximo != null ? String(g.fator_prazo_maximo).replace('.', ',') : '',
    opt_faltando: g.optativas_faltando ?? '', opt_feitas: g.optativas_feitas || [],
    fixas: (g.fixas || []).map(f => ({...f}))};
}
function prefCarregar() {
  if (!SIM.pref) SIM.pref = prefDoServidor(S.preferencias);
  return SIM.pref;
}
function prefSalvar() { /* o rascunho fica na tela; grava no servidor ao "Aplicar" */ }
// Monta o objeto `preferencias` do pedido (só o que foi preenchido; a validação é do servidor).
function prefCorpo() {
  const p = prefCarregar(), c = {};
  const blocos = p.indisponiveis.filter(b => b.dia && b.inicio && b.fim);
  if (blocos.length) c.indisponiveis = blocos.map(b => ({dia: b.dia, inicio: b.inicio, fim: b.fim, ...(b.motivo ? {motivo: b.motivo} : {})}));
  if (p.turno) c.turno = p.turno;
  if (p.dias_livres.length) c.dias_livres = p.dias_livres;
  if (p.max_pesadas !== '') c.max_pesadas = Number(p.max_pesadas);
  if (p.pesadas.length) c.pesadas = p.pesadas;
  const tetos = p.tetos.filter(t => t.periodo && t.creditos !== '');
  if (tetos.length) c.teto_por_periodo = Object.fromEntries(tetos.map(t => [t.periodo.trim(), Number(t.creditos)]));
  const pulados = p.pulados.split(/[,;\s]+/).map(x => x.trim()).filter(Boolean);
  if (pulados.length) c.periodos_pulados = pulados;
  if (p.ingresso.trim()) c.periodo_ingresso = p.ingresso.trim();
  if (p.fator !== '') c.fator_prazo_maximo = Number(String(p.fator).replace(',', '.'));
  if (p.opt_faltando !== '' && p.opt_faltando != null) c.optativas_faltando = Number(p.opt_faltando);
  if (p.opt_feitas?.length) c.optativas_feitas = p.opt_feitas;
  const fixas = (p.fixas || []).filter(f => f.disciplina_id && f.periodo);
  if (fixas.length) c.fixas = fixas.map(f => ({disciplina_id: Number(f.disciplina_id), periodo: f.periodo}));
  // grupos "cursar junto" vivem nas preferências guardadas: viajam junto para não se perderem
  if (S.preferencias?.juntas?.length) c.juntas = S.preferencias.juntas;
  if (S.preferencias?.juntas_respondida) c.juntas_respondida = true;
  return c;
}
const prefAtivasSemJuntas = () => Object.keys(prefCorpo()).filter(k => !k.startsWith('juntas')).length;
const prefAtivas = () => prefAtivasSemJuntas();

const GRAV = {
  alta:  {ico: '⛔', rotulo: 'Alta',  cls: 'g-alta'},
  media: {ico: '⚠', rotulo: 'Média', cls: 'g-media'},
  baixa: {ico: 'ℹ', rotulo: 'Baixa', cls: 'g-baixa'},
};
const VEREDITO_ICO = {ok: '✓', medio: '⚠', alto: '⛔', info: 'ℹ'};

// "Dá para cursar o que falta com a sua rotina?" — uma resposta só (texto pronto do servidor).
function cartaoRotina(r) {
  if (!r) return '';
  return `<div class="sim-veredito v-${esc(r.nivel === 'info' ? 'medio' : r.nivel)} rotina-veredito" role="status">
    <span class="sim-veredito-ico" aria-hidden="true">${VEREDITO_ICO[r.nivel] || 'ℹ'}</span>
    <div><b>${esc(r.titulo)}</b><div>${esc(r.texto)}</div>
      ${r.acao ? `<div class="risco-acao">→ ${esc(r.acao)}</div>` : ''}
      ${r.nao_cabem?.length > 6 ? `<details class="sim-mais"><summary>Ver as ${r.nao_cabem.length}</summary>${r.nao_cabem.map(chip).join(' ')}</details>` : ''}
    </div></div>`;
}

const horaAgora = () => new Date().toLocaleTimeString('pt-BR', {hour: '2-digit', minute: '2-digit'});
const chip = d => `<span class="tag" title="${esc(d.nome)}">${esc(d.codigo)}</span>`;
const nSem = n => `${n} semestre${n === 1 ? '' : 's'}`;
const planoTemItens = () => !!Planos.atual()?.semestres.some(s => s.itens.length);
// O servidor só decide o período sozinho se o plano ou o histórico trouxer algum. Senão a pessoa precisa dizer.
const temPeriodoNoHistorico = () => S.historico.some(h => h.periodo_letivo);
const planoTemPeriodo = () => !!Planos.atual()?.semestres.some(s => s.periodo_letivo);
const precisaDoPeriodo = () => !SIM.inicio && !planoTemPeriodo() && !temPeriodoNoHistorico();
const PERIODO_OK = /^\d{4}\s*[./-]\s*[12]$/;
const assinaturaDoPedido = () => JSON.stringify([Planos.atualId(), Planos.paraAnalise(), SIM.inicio, prefCorpo()]);

// ── blocos de feedback reutilizáveis ────────────────────────────────────
const faixa = (tipo, html) => `<div class="sim-faixa sim-${tipo}" role="status"><span>${html}</span></div>`;
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
      <div class="sim-explica">
        <b>O que é simulado:</b> o plano aberto no Planejamento, do jeito que está, com a sua rotina.
        <span>Quer outro plano? <a href="#" onclick="irPara('planner');setTimeout(abrirSugestao,300);return false">Sugerir um plano melhor</a>.</span>
      </div>
    </div>
    ${S.historico.length ? '' : `<div class="sim-nota" style="margin:0 0 12px">Sem histórico: tudo conta como a cursar e a chance de aprovação usa o padrão (85%). <a href="#" onclick="irPara('historico');return false">Informar o histórico</a> deixa a simulação mais fiel.</div>`}
    <div id="sim-rotina">${resumoRotina()}</div>
    <div id="sim-status"></div>
    <div id="sim-resumo"></div>
    <div id="sim-abas"></div>
    <div id="sim-resultado" role="tabpanel"></div>`;
  if (SIM.aba === 'sugestao') SIM.aba = 'geral';
  desenharAbas();
  desenharSimulacao();
  // Roda sozinha ao abrir (ou ao mudar o plano), mas só se o pedido mudou: voltar à aba não repete a conta.
  if (planoTemItens() && !precisaDoPeriodo() && SIM.sim.estado !== 'carregando' && SIM.sim.assinatura !== assinaturaDoPedido()) simRodar();
}

window.simTrocarPlano = id => { Planos.selecionar(Number(id)); S.currentPlano = Planos.atualId(); SIM.sim.assinatura = null; simulador(); };
// Valida no navegador (feedback imediato) antes de gastar uma ida ao servidor.
window.simUsarInicio = () => {
  const v = valorPeriodo('sim-inicio-pedido');
  if (v === null) return;
  if (!v) { erroNoCampo('sim-inicio-pedido', 'Escolha o período em que o plano começa.'); return; }
  SIM.inicio = v; SIM.sim.assinatura = null; simulador();
};
window.simMudarInicio = () => {
  const sel = document.getElementById('sim-inicio');
  if (sel?.value === 'outro' && !document.getElementById('sim-inicio-outro').value.trim()) { document.getElementById('sim-inicio-outro').focus(); return; }
  const v = valorPeriodo('sim-inicio');
  if (v === null) return;                                 // inválido: o erro já está junto ao campo
  SIM.inicio = v; SIM.sim.assinatura = null; simulador();
};

// ── abas (navegáveis pelo teclado: ← → Home End) ─────────────────────────
window.simAba = aba => { SIM.aba = aba; desenharAbas(); desenharSimulacao(); desenharSugestao();
  document.getElementById(`aba-${aba}`)?.focus(); };
function desenharAbas() {
  const alvo = document.getElementById('sim-abas');
  if (!alvo) return;
  const d = SIM.sim.estado === 'ok' ? SIM.sim.dados : null;
  const conta = {riscos: d?.riscos.filter(x => x.gravidade !== 'baixa').length};
  alvo.innerHTML = `<div class="abas-sim" role="tablist" aria-label="Seções do simulador"
      onkeydown="simAbaTeclado(event)">${ABAS.map(([k, rot]) => `<button role="tab" id="aba-${k}" aria-selected="${SIM.aba === k}"
      aria-controls="${k === 'sugestao' ? 'sug-bloco' : 'sim-resultado'}" tabindex="${SIM.aba === k ? 0 : -1}"
      class="aba ${SIM.aba === k ? 'ativa' : ''}" onclick="simAba('${k}')">${rot}${conta[k] ? ` <span class="badge badge-red">${conta[k]}</span>` : ''}</button>`).join('')}</div>`;
}
window.simAbaTeclado = e => {
  const i = ABAS.findIndex(([k]) => k === SIM.aba);
  const alvo = {ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: ABAS.length - 1}[e.key];
  if (alvo === undefined) return;
  e.preventDefault();
  simAba(ABAS[(alvo + ABAS.length) % ABAS.length][0]);
};

// ═══════════════════════════════════════════════════════
// SIMULAÇÃO
// ═══════════════════════════════════════════════════════
window.simRodar = async function (manual = false) {
  if (!planoTemItens()) { desenharSimulacao(); return; }
  const meu = ++SIM.seq;
  const assinatura = assinaturaDoPedido();
  SIM.sim = {...SIM.sim, estado: 'carregando', erro: null};
  desenharSimulacao();
  const corpo = {...Planos.paraAnalise(), preferencias: prefCorpo()};
  if (SIM.inicio) corpo.periodo_inicial = SIM.inicio;
  const r = await POST(`/api/cursos/${CURSO_ID}/simulacao`, corpo);
  if (meu !== SIM.seq) return;                                  // chegou depois de o pedido ter mudado
  if (marcarErroDeCampo(r)) {
    SIM.sim = {...SIM.sim, estado: 'erro', erro: 'Corrija o campo destacado nas preferências.'};
  } else if (!r.ok) {
    SIM.sim = {...SIM.sim, estado: 'erro', erro: r.erro || 'Erro desconhecido ao simular.'};
  } else {
    SIM.sim = {estado: 'ok', dados: r, erro: null, quando: horaAgora(), assinatura};
    if (manual) toast('Simulação atualizada.', 'success', 2000);
    if (SIM.sug.estado === 'ok') desenharSugestao();             // a comparação usa a simulação do plano atual
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

  if (SIM.aba === 'sugestao') { res.innerHTML = ''; res.hidden = true; } else res.hidden = false;
  const sug = document.getElementById('sug-bloco');
  if (sug) sug.hidden = SIM.aba !== 'sugestao';
  if (SIM.aba === 'sugestao') { st.innerHTML = ''; return; }
  if (!planoTemItens()) {                                        // 4. vazio, com a ação que resolve
    st.innerHTML = '';
    res.innerHTML = `<div class="empty">${Planos.planos().length ? 'Este plano ainda não tem disciplinas.' : 'Você ainda não tem um plano.'}<br>
      Monte um plano à mão ou peça uma sugestão no Planejamento; o Simulador avalia o plano que estiver aberto.<br>
      <button class="btn btn-primary" onclick="irPara('planner')">Montar plano</button>
      <button class="btn btn-ghost" onclick="irPara('planner');setTimeout(abrirSugestao,300)">✨ Sugerir plano</button></div>`;
    return;
  }
  if (precisaDoPeriodo()) {                                      // falta um dado: pede aqui, sem ir ao servidor
    st.innerHTML = '';
    res.innerHTML = `<div class="sim-faixa sim-info" role="status"><div><b>Falta uma informação:</b> em que período este plano começa?<br>
      <small>Seu plano e seu histórico não têm período letivo. Escolha na lista ou digite.</small></div>
      <span class="sim-inline"><label class="sr-only" for="sim-inicio-pedido">Período em que o plano começa</label>
        ${campoPeriodo('sim-inicio-pedido', '', {auto: false})}<button class="btn btn-primary btn-sm" onclick="simUsarInicio()">Simular</button></span></div>`;
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
  const resumo = document.getElementById('sim-resumo');
  if (resumo) resumo.innerHTML = blocoVisaoGeral(d);
  desenharAbas();
  const paineis = {
    geral: () => blocoGeral(d), riscos: () => blocoRiscos(d), semestres: () => blocoLinhaDoTempo(d),
    reprovar: () => blocoReprovar(d), probabilidade: () => blocoProbabilidade(d.monte_carlo), sugestao: () => '',
  };
  res.innerHTML = (paineis[SIM.aba] || paineis.geral)();
  res.setAttribute('aria-labelledby', `aba-${SIM.aba}`);
}

// Aba "Visão geral": o que falta, optativas, prazo, a cadeia crítica (linha de metrô) e as premissas.
function blocoGeral(d) {
  const r = d.resumo;
  const faltam = r.faltam_obrigatorias.length
    ? `<div class="sim-nota">Faltam obrigatórias no plano: ${r.faltam_obrigatorias.map(chip).join(' ')}</div>` : '';
  return `<section class="sim-bloco">${faltam}${notaOptativas(r.optativas)}${notaPrazo(d.prazo)}</section>
    ${blocoCritico(d)}${blocoPremissas(d)}`;
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
  return `<section class="sim-bloco">
    ${d.rotina?.nivel === 'alto' ? cartaoRotina(d.rotina) : ''}
    ${d.rotina?.nivel === 'alto' && v.tipo === 'rotina' ? '' /* o cartão da rotina já diz isso */ : `
    <div class="sim-veredito v-${esc(v.nivel)}"><span class="sim-veredito-ico" aria-hidden="true">${VEREDITO_ICO[v.nivel]}</span>
      <div><b>${esc(v.titulo)}</b><div>${esc(v.texto)}</div></div></div>`}
    <div class="grid-4">
      <div class="stat-card"><div class="stat-label">Formatura</div><div class="stat-value">${esc(formatura.valor)}</div><div class="stat-sub">${esc(formatura.sub)}</div></div>
      <div class="stat-card"><div class="stat-label">Créditos no plano</div><div class="stat-value">${r.creditos_planejados}</div>
        <div class="stat-sub">${r.creditos_restantes == null ? 'Restantes: –' : `Restam ${r.creditos_restantes} depois dele`}</div></div>
      <div class="stat-card"><div class="stat-label">Riscos</div><div class="stat-value">${g.alta + g.media + g.baixa}</div>
        <div class="stat-sub">${g.alta} alta · ${g.media} média · ${g.baixa} baixa</div></div>
      <div class="stat-card"><div class="stat-label">Pior caso se reprovar</div><div class="stat-value">${r.atraso_maximo_reprovacao ? '+' + nSem(r.atraso_maximo_reprovacao) : 'Sem atraso'}</div>
        <div class="stat-sub">numa única disciplina</div></div>
    </div></section>`;
}

// Optativas: exigidas × cumpridas × planejadas, e as duas datas (texto pronto do servidor).
function notaOptativas(o) {
  if (!o) return '';
  const datas = o.faltam && o.com_optativas
    ? `<div class="grid-4" style="margin-top:10px"><div class="stat-card"><div class="stat-label">Formatura só com as obrigatórias</div><div class="stat-value">${esc(o.so_obrigatorias || '–')}</div></div>
       <div class="stat-card"><div class="stat-label">Formatura com as optativas</div><div class="stat-value">${esc(o.com_optativas)}</div><div class="stat-sub">faltam ${o.faltam} créditos</div></div></div>` : '';
  return `<div class="sim-nota ${o.faltam ? 'sim-nota-aviso' : o.faltam === 0 ? 'ok' : ''}"><b>Optativas:</b> ${esc(o.mensagem)}</div>${datas}`;
}

// "N choques" no topo do semestre leva ao primeiro item com choque.
function linkChoques(s, prefixo) {
  if (!s.choques_texto) return '';
  const alvo = s.itens.find(i => i.choques?.length);
  return `<a class="badge badge-red" href="#${prefixo}-item-${s.posicao}-${alvo?.disciplina.id}" onclick="document.getElementById('${prefixo}-item-${s.posicao}-${alvo?.disciplina.id}')?.scrollIntoView({block:'center'});return false">⛔ ${esc(s.choques_texto)}</a>`;
}

function notaPrazo(pz) {
  if (!pz) return '';
  const cls = pz.no_prazo_maximo === false ? 'erro' : pz.no_prazo_regular === true ? 'ok' : pz.no_prazo_regular === false ? 'sim-nota-aviso' : '';
  const origem = pz.origem_ingresso === 'inicio_do_plano' ? ' <small>(ingresso = início do plano)</small>' : '';
  return `<div class="sim-nota ${cls}"><b>Prazo:</b> ${esc(pz.mensagem)}${origem}</div>`;
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

// Riscos repetidos (3+ do mesmo tipo) ficam num grupo com título do servidor: a lista não vira um muro.
function listaRiscos(fortes, grupos) {
  const agrupados = new Set((grupos || []).map(g => g.tipo));
  const soltos = fortes.filter(x => !agrupados.has(x.tipo));
  return `${soltos.length ? `<ul class="riscos">${soltos.map(itemRisco).join('')}</ul>` : ''}
    ${(grupos || []).map(g => {
      const itens = fortes.filter(x => x.tipo === g.tipo);
      const alto = itens.some(x => x.gravidade === 'alta');
      return `<details class="risco-grupo ${alto ? 'g-alta' : 'g-media'}"><summary><span aria-hidden="true">${alto ? '⛔' : '⚠'}</span> <b>${esc(g.titulo)}</b>
        <span class="sim-dica">${itens[0]?.acao ? '→ ' + esc(itens[0].acao) : ''}</span></summary>
        <ul class="riscos">${itens.map(itemRisco).join('')}</ul></details>`;
    }).join('')}`;
}

function blocoRiscos(d) {
  const fortes = d.riscos.filter(x => x.gravidade !== 'baixa');
  const fracos = d.riscos.filter(x => x.gravidade === 'baixa');
  const corpo = d.riscos.length === 0
    ? `<div class="sim-nota ok">✓ Nenhum risco encontrado com os dados que o curso informou.</div>`
    : `${fortes.length ? listaRiscos(fortes, d.riscos_grupos) : '<div class="sim-nota ok">✓ Nenhum risco alto ou médio.</div>'}
       ${fracos.length ? `<details class="sim-mais"><summary>${fracos.length} aviso${fracos.length > 1 ? 's' : ''} menor${fracos.length > 1 ? 'es' : ''} (informativos)</summary>
         <ul class="riscos">${fracos.map(itemRisco).join('')}</ul></details>` : ''}`;
  return `<section class="sim-bloco"><h3>O que pode dar errado</h3>${corpo}
    ${d.riscos.length ? `<div class="sim-acoes"><button class="btn btn-ghost btn-sm" onclick="irPara('planner')">Ajustar no Planejamento</button></div>` : ''}</section>`;
}

// ── 3. linha do tempo ───────────────────────────────────────────────────
function selosDoItem(i, periodo) {
  // "sem horário" agora vem pronto do servidor (tag cinza): não repetir aqui
  const s = [seloOferta({oferta: {valor: i.periodicidade, origem: i.origem_periodicidade}}, periodo), tagsProntas(i.tags)];
  if (i.horario_origem === 'projetado') s.push(`<span class="badge badge-gray" title="Copiado de ${esc(i.periodo_da_turma || 'outro período')}">Horário projetado</span>`);
  else if (i.horario_origem === 'proprio') s.push('<span class="badge badge-accent">Horário próprio</span>');
  return s.join(' ');
}

function cartaoSemestre(s, riscos) {
  const meus = riscos.filter(x => x.posicao === s.posicao);
  const altos = meus.filter(x => x.gravidade === 'alta').length;
  const noLimite = s.creditos_no_limite ?? s.creditos, fora = s.creditos_fora_do_limite || 0;
  const pct = s.limite_creditos ? Math.min(100, Math.round(noLimite / s.limite_creditos * 100)) : null;
  return `<div class="sim-sem ${altos ? 'tem-alto' : ''}">
    <div class="sim-sem-topo"><b>${s.posicao}º · ${esc(s.periodo)}</b><span class="badge badge-gray">${s.paridade === 'impar' ? 'ímpar' : 'par'}</span>
      ${s.trancado ? '<span class="badge badge-gray">Trancado</span>' : ''}${linkChoques(s, 'sim')}${s.pesadas?.length ? `<span class="badge badge-yellow" title="${esc(s.pesadas.map(x => x.codigo).join(', '))}">${s.pesadas.length} pesada${s.pesadas.length > 1 ? 's' : ''}</span>` : ''}
      ${altos ? `<span class="badge badge-red">⛔ ${altos} problema${altos > 1 ? 's' : ''}</span>` : meus.length ? `<span class="badge badge-yellow">${meus.length} aviso${meus.length > 1 ? 's' : ''}</span>` : '<span class="badge badge-green">✓ ok</span>'}
    </div>
    <div class="sim-carga" title="${s.creditos}${s.limite_creditos ? ' de ' + s.limite_creditos : ''} créditos">
      ${pct == null ? '' : `<div class="progress-bar"><div class="progress-fill ${s.sobrecarga ? 'estouro' : ''}" style="width:${pct}%"></div></div>`}
      <span>${noLimite}${s.limite_creditos ? ' / ' + s.limite_creditos : ''} créditos${fora ? ` · +${fora} fora do limite` : ''}${s.sem_creditos.length ? ` (sem créditos informados: ${esc(s.sem_creditos.join(', '))})` : ''}</span>
    </div>
    ${s.semana ? `<div class="sim-semana">${esc(s.semana.resumo)}</div>` : ''}
    ${s.espaco_optativa_texto ? `<div class="sim-semana">${esc(s.espaco_optativa_texto)}</div>` : ''}
    <ul class="sim-itens">${s.itens.map(i => `<li id="sim-item-${s.posicao}-${i.disciplina.id}">
      <span class="sim-disc"><b>${esc(i.disciplina.codigo)}</b> ${esc(i.disciplina.nome)}</span>
      <span class="sim-selos">${selosDoItem(i, s.periodo)}${i.encontros.length ? ` <small>${esc((i.turma_codigo ? i.turma_codigo + ' · ' : '') + horariosStr(i.encontros))}</small>` : ''}</span></li>`).join('')}</ul>
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

// ── 4b. vou formar quando? (Monte Carlo) ────────────────────────────────
function blocoProbabilidade(mc) {
  if (!mc) return '';
  const maior = Math.max(...mc.distribuicao.map(x => x.pct), mc.nao_formou_pct, 1);
  const barras = mc.distribuicao.map(x => `<div class="mc-col" title="${esc(x.periodo)}: ${x.pct}% (acumulado ${x.acumulado_pct}%)">
      <div class="mc-trilho"><div class="mc-barra ${x.periodo === mc.periodo_do_plano ? 'no-plano' : ''}" style="height:${Math.round(x.pct / maior * 100)}%"></div></div>
      <span>${esc(x.periodo)}</span></div>`).join('');
  return `<section class="sim-bloco"><h3>Vou formar quando?</h3>
    ${mc.mensagem_plano ? `<p class="sim-destaque">${esc(mc.mensagem_plano)}</p>` : ''}
    <p class="sim-texto">${esc(mc.mensagem)}</p>
    <div class="mc-barras" aria-hidden="true">${barras}</div>
    <table class="sr-only"><caption>Chance de formar em cada período (${mc.n} simulações)</caption>
      <tr><th>Período</th><th>Chance</th><th>Acumulada</th></tr>
      ${mc.distribuicao.map(x => `<tr><td>${esc(x.periodo)}</td><td>${x.pct}%</td><td>${x.acumulado_pct}%</td></tr>`).join('')}</table>
    ${mc.nao_formou_pct ? `<div class="sim-nota">Em ${mc.nao_formou_pct}% das simulações o curso não fecha nos 12 semestres seguintes ao plano.</div>` : ''}
    ${mc.sensibilidade.length ? `<p class="sim-texto" style="margin-top:12px"><b>O que mais pode atrasar:</b></p>
      <ul class="sim-premissas">${mc.sensibilidade.map(x => `<li>${esc(x.mensagem)}</li>`).join('')}</ul>` : ''}
    <p class="sim-dica">${esc(mc.taxa.texto)} ${mc.n} simulações, sempre com o mesmo sorteio.</p>
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
  const cadeia = (c.cadeia || []).map(x => ({codigo: x.disciplina.codigo, nome: x.disciplina.nome, periodo: x.periodo}));
  return `<section class="sim-bloco"><h3>Caminho crítico</h3>
    ${c.cadeia_mensagem ? `<p class="sim-destaque">${esc(c.cadeia_mensagem)}</p>` : ''}
    ${linhaDeMetro(cadeia, 'Cadeia crítica: ' + cadeia.map(x => `${x.codigo} em ${x.periodo}`).join(', '))}
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
  ['sug-teto', 'sug-inicio'].forEach(limparErroCampo);
  if (document.getElementById('sug-inicio')) {
    const v = valorPeriodo('sug-inicio');
    if (v === null) return;                                       // erro já junto ao campo
    SIM.inicio = v;
  }
  SIM.teto = document.getElementById('sug-teto')?.value.trim() ?? SIM.teto;
  SIM.extras = Number(document.getElementById('sug-extras')?.value ?? SIM.extras);
  SIM.optFaltando = '';                       // optativas vêm da rotina (mesmos números do Simulador)
  if (SIM.teto !== '' && !(Number.isInteger(Number(SIM.teto)) && Number(SIM.teto) >= 1 && Number(SIM.teto) <= 60)) { erroNoCampo('sug-teto', 'Use um número inteiro de 1 a 60.'); return; }
  if (precisaDoPeriodo()) { erroNoCampo('sug-inicio', 'Escolha o período: seu histórico ainda não tem períodos.'); return; }
  const corpo = {semestres_extras: SIM.extras, preferencias: prefCorpo()};
  if (planoTemItens()) corpo.plano_atual = Planos.paraAnalise();   // ponto de partida: não sai pior que ele
  if (SIM.inicio) corpo.periodo_inicial = SIM.inicio;
  if (SIM.teto) corpo.max_creditos = Number(SIM.teto);
  if (SIM.optFaltando !== '') corpo.optativas_faltando = Number(SIM.optFaltando);
  SIM.sug = {...SIM.sug, estado: 'carregando', erro: null, salvo: null, inicio: Date.now()};
  desenharSugestao();
  const relogio = setInterval(atualizarEtapas, 300);             // avança o indicador de etapas enquanto espera
  const r = await POST(`/api/cursos/${CURSO_ID}/simulacao/sugerir`, corpo);
  clearInterval(relogio);
  const deCampo = marcarErroDeCampo(r);
  SIM.sug = r.ok ? {estado: 'ok', dados: r, erro: null, salvo: null}
                 : {...SIM.sug, estado: 'erro', erro: deCampo ? 'Corrija o campo destacado nas preferências.' : (r.erro || 'Erro desconhecido ao gerar a sugestão.')};
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
  toast(`Plano “${plano.nome}” criado e aberto. O anterior continua na lista de planos.`, 'success', 5000);
  desenharSugestao();
  if (S.currentPage === 'planner') { SIM.sugAberta = false; await atualizarPlano(); }
};

function desenharSugestao() {
  const alvo = document.getElementById('sug-bloco');
  if (!alvo) return;
  const g = SIM.sug, ocupado = g.estado === 'carregando';
  const tetoCurso = S.curso?.max_creditos_semestre;
  alvo.innerHTML = `<section class="sim-bloco sim-sugestao" aria-labelledby="sug-titulo">
    <div class="sug-cabeca"><h3 id="sug-titulo">✨ Sugerir um plano</h3>
      <button class="btn btn-ghost btn-sm" onclick="fecharSugestao()" aria-label="Fechar a sugestão">✕ Fechar</button></div>
    <p class="sim-texto">Monta um plano NOVO com o que falta cursar: pré-requisitos, oferta par/ímpar, limite de créditos,
      choques e a sua rotina (horários e optativas de <a href="#" onclick="irPara('rotina');return false">Minha rotina</a>).
      Seu plano atual não muda; ao final você compara e decide.</p>
    <div class="sug-form">
      <div class="form-group"><label class="form-label" for="sug-inicio">Começa em</label>
        ${campoPeriodo('sug-inicio', SIM.inicio, {auto: !precisaDoPeriodo(), desativado: ocupado})}</div>
      <div class="form-group"><label class="form-label" for="sug-teto">Máx. créditos por semestre</label>
        <input class="form-input" id="sug-teto" type="number" min="1" max="60" placeholder="${tetoCurso ? 'curso: ' + tetoCurso : 'sem limite'}" value="${esc(SIM.teto)}" ${ocupado ? 'disabled' : ''}/></div>
      <div class="form-group"><label class="form-label" for="sug-extras">Ritmo</label>
        <select class="form-select" id="sug-extras" ${ocupado ? 'disabled' : ''}>
          ${[[0, 'O mais rápido possível'], [1, 'Mais leve (+1 semestre)'], [2, 'Bem leve (+2 semestres)']].map(([v, t]) => `<option value="${v}" ${SIM.extras === v ? 'selected' : ''}>${t}</option>`).join('')}
        </select></div>
      <button class="btn btn-primary" onclick="simSugerir()" ${ocupado ? 'disabled' : ''}>${ocupado ? 'Calculando…' : g.dados ? 'Gerar de novo' : 'Gerar sugestão'}</button>
    </div>
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
  if (g.estado === 'carregando') return blocoEtapas();
  if (g.estado === 'erro') return erroComRetentativa(g.erro, 'simSugerir');
  if (g.estado !== 'ok') return `<div class="sim-nota">${precisaDoPeriodo()
    ? 'Escolha em que período o plano começa e clique em “Gerar sugestão”. Os outros campos são opcionais.'
    : 'Clique em “Gerar sugestão”. Em branco, usamos o limite do curso e o período seguinte ao seu histórico.'}</div>`;
  const d = g.dados;
  if (!d.viavel) return `<div class="sim-faixa sim-erro" role="alert"><div><b>Não existe plano possível.</b> ${esc(d.mensagem)}<div class="risco-acao">→ ${esc(d.acao)}</div></div></div>`;
  const m = d.metricas;
  if (!d.semestres.length) return faixa('ok', '✓ Não há nada a cursar: o curso já está completo.');
  const cadeia = (d.cadeia_critica || []).map(x => ({codigo: x.disciplina.codigo, nome: x.disciplina.nome, periodo: x.periodo}));
  return `${faixa('ok', `✓ Sugestão pronta · começa em <b>${esc(d.periodo_inicial)}</b> e você forma em <b>${esc(d.formatura?.com_optativas || m.periodo_fim)}</b>`)}
    ${cartaoRotina(d.rotina?.nivel === 'alto' ? d.rotina : null)}
    ${d.partiu_do_plano ? `<p class="sim-dica">A busca partiu do seu plano “${esc(Planos.atual()?.nome || '')}”: sem pedidos novos, a sugestão não forma depois dele.</p>` : ''}
    ${(d.fixas_mensagens || []).map(f => `<div class="sim-nota ${f.ok ? 'ok' : 'sim-nota-aviso'}">${f.ok ? '✓' : '⚠'} ${esc(f.texto)}</div>`).join('')}
    ${d.selo ? `<div class="selo-otimo selo-${esc(d.selo.tipo)}"><b>${d.selo.tipo === 'otimo' ? '✓' : '≈'} ${esc(d.selo.titulo)}</b><span>${esc(d.selo.texto)}</span></div>` : ''}
    ${d.selo ? '' : `<p class="sim-texto">${esc(d.explicacao)}</p>`}
    ${blocoComparacao(SIM.sim.estado === 'ok' ? SIM.sim.dados.indicadores : null, d.indicadores)}
    ${d.cadeia_mensagem ? `<p class="sim-texto"><b>${esc(d.cadeia_mensagem)}</b></p>` : ''}
    ${linhaDeMetro(cadeia, 'Cadeia crítica da sugestão: ' + cadeia.map(x => `${x.codigo} em ${x.periodo}`).join(', '))}
    ${(d.etapas || []).some(e => e.ms != null) ? `<p class="sim-dica">Feito em: ${d.etapas.map(e => `${esc(e.rotulo.toLowerCase())} ${e.ms} ms`).join(' · ')}.</p>` : ''}
    <div class="grid-4">
      <div class="stat-card"><div class="stat-label">Semestres</div><div class="stat-value">${m.n_semestres}</div><div class="stat-sub">mínimo teórico: ${d.limite_inferior}</div></div>
      <div class="stat-card"><div class="stat-label">Carga média</div><div class="stat-value">${m.carga_media}</div><div class="stat-sub">máx. ${m.carga_maxima} · variação ±${m.carga_desvio}</div></div>
      <div class="stat-card"><div class="stat-label">Choques de horário</div><div class="stat-value">${m.colisoes}</div><div class="stat-sub">${m.colisoes ? 'sem saída com os horários conhecidos' : 'nenhum previsto'}</div></div>
      <div class="stat-card"><div class="stat-label">Se reprovar (média)</div><div class="stat-value">+${m.atraso_medio_reprovacao}</div><div class="stat-sub">semestres · pior caso +${m.atraso_maximo_reprovacao}</div></div>
    </div>
    ${notaPrazo(d.prazo)}
    ${d.pedidos_mensagem ? `<div class="sim-nota sim-nota-aviso">${esc(d.pedidos_mensagem)}</div>` : ''}
    ${d.monte_carlo?.mensagem_plano ? `<div class="sim-nota"><b>Chance:</b> ${esc(d.monte_carlo.mensagem_plano)} ${esc(d.monte_carlo.mensagem)}</div>` : ''}
    ${blocoOptativas(d)}
    ${d.incluidas_por_requisito.length ? `<div class="sim-nota">Entraram por serem exigidas por outras: ${d.incluidas_por_requisito.map(chip).join(' ')}</div>` : ''}
    <div class="sim-timeline">${d.semestres.map(s => `<div class="sim-sem ${s.colisoes.length ? 'tem-alto' : ''}">
      <div class="sim-sem-topo"><b>${s.posicao}º · ${esc(s.periodo)}</b>${s.trancado ? '<span class="badge badge-gray">Trancado</span>' : `<span class="badge badge-gray">${s.creditos + s.creditos_optativos} créditos</span>`}
        ${linkChoques(s, 'sug')}</div>
      ${s.semana && s.itens.length ? `<div class="sim-semana">${esc(s.semana.resumo)}</div>` : ''}
      <ul class="sim-itens">${s.itens.map(i => { const x = S.disciplinas.find(z => z.id === i.disciplina.id);
        return `<li id="sug-item-${s.posicao}-${i.disciplina.id}"><span class="sim-disc"><b>${esc(i.disciplina.codigo)}</b> ${esc(i.disciplina.nome)}</span>
          <span class="sim-selos">${x ? seloOferta(x, s.periodo) : ''} ${tagsProntas(i.tags)}${i.horario_origem === 'projetado' ? ' <span class="badge badge-gray">Horário projetado</span>' : ''}</span></li>`; }).join('')}
        ${s.creditos_optativos ? `<li class="sim-reserva">Espaço para optativa: ${s.creditos_optativos} créditos (você escolhe qual)</li>` : ''}</ul>
      ${s.colisoes.map(c => `<div class="risco-meta">Choque na ${esc(diaLabel(c.dia))}: ${esc(c.a.codigo)} × ${esc(c.b.codigo)}</div>`).join('')}
    </div>`).join('')}</div>
    ${g.erroSalvar ? `<div class="sim-faixa sim-erro" role="alert"><div><b>Não deu certo.</b> ${esc(g.erroSalvar)}</div></div>` : ''}
    <div class="sim-acoes">
      ${g.salvo
        ? `<span class="sim-ok">✓ Salvo como “${esc(g.salvo)}” e aberto.</span> <button class="btn btn-ghost btn-sm" onclick="irPara('simulador')">Testar no Simulador</button>`
        : `<button class="btn btn-primary btn-sm" id="sug-salvar" onclick="simSalvarSugestao()">Usar este plano</button>
           <span class="sim-dica">Cria um plano novo e o abre; o atual continua na lista.</span>`}
    </div>`;
}


// ═══════════════════════════════════════════════════════
// PREFERÊNCIAS (Fase 2): valem para a simulação e para a sugestão
// ═══════════════════════════════════════════════════════
const idDoCampo = campo => 'pref-' + String(campo).replace(/\./g, '-');
// Erro de validação de um campo (422 com `detalhes.campo`): abre o painel e mostra junto ao campo.
function marcarErroDeCampo(r) {
  const campo = r && !r.ok && r.detalhes?.campo;
  if (!campo || campo === 'periodo_inicial') return false;
  SIM.erroCampo = {campo, msg: r.erro};
  SIM.prefAberto = true;
  desenharPreferencias();
  return true;
}
function mostrarErroDeCampo() {
  const e = SIM.erroCampo;
  if (!e) return;
  // o campo exato (ex.: indisponiveis-0-fim) ou o grupo dele (ex.: indisponiveis)
  const el = document.getElementById(idDoCampo(e.campo)) || document.getElementById(idDoCampo(e.campo.split('.')[0]));
  if (!el) { toast(e.msg, 'error'); return; }
  const idErro = el.id + '-erro';
  el.setAttribute('aria-invalid', 'true');
  el.setAttribute('aria-describedby', idErro);
  el.insertAdjacentHTML('afterend', `<div class="campo-erro" id="${idErro}" role="alert">${esc(e.msg)}</div>`);
  el.focus?.();
}
window.prefMudar = (chave, valor) => { prefCarregar()[chave] = valor; prefSalvar(); SIM.erroCampo = null; };
window.prefDia = (dia, marcado) => {
  const p = prefCarregar();
  p.dias_livres = marcado ? [...new Set([...p.dias_livres, dia])] : p.dias_livres.filter(d => d !== dia);
  prefSalvar();
};
window.prefPesada = (id, marcado) => {
  const p = prefCarregar();
  p.pesadas = marcado ? [...new Set([...p.pesadas, id])] : p.pesadas.filter(x => x !== id);
  prefSalvar();
};
window.prefOptFeita = (id, marcado) => {
  const p = prefCarregar();
  p.opt_feitas = marcado ? [...new Set([...p.opt_feitas, id])] : p.opt_feitas.filter(x => x !== id);
};
window.prefLinha = (lista, k, chave, valor) => { prefCarregar()[lista][k][chave] = valor; prefSalvar(); SIM.erroCampo = null; };
window.prefAdicionar = lista => {
  const p = prefCarregar();
  p[lista].push(lista === 'indisponiveis' ? {dia: 'SEG', inicio: '08:00', fim: '12:00', motivo: ''}
    : lista === 'fixas' ? {disciplina_id: null, periodo: ''} : {periodo: '', creditos: ''});
  prefSalvar(); desenharPreferencias();
};
window.prefRemover = (lista, k) => { prefCarregar()[lista].splice(k, 1); prefSalvar(); SIM.erroCampo = null; desenharPreferencias(); };
window.prefAplicar = async () => {
  SIM.erroCampo = null; SIM.sim.assinatura = null;
  const r = await PUT(`/api/cursos/${CURSO_ID}/preferencias`, prefCorpo());
  if (marcarErroDeCampo(r)) return;
  if (!r.ok) { toast(r.erro || 'Não foi possível guardar as preferências.', 'error'); return; }
  S.preferencias = r.preferencias;
  SIM.pref = prefDoServidor(S.preferencias);
  (r.avisos_juntas || []).forEach(a => toast(a, 'warn', 9000));
  toast('Rotina guardada. Vale no Planejamento, no Calendário, na Sugestão e no Simulador.', 'success', 3500);
  atualizarRota();
  desenharVereditoRotina();
  desenharPreferencias();
  if (planoTemItens()) simRodar(true);
  if (SIM.sug.dados) simSugerir();
};
window.prefLimpar = () => { SIM.pref = PREF_VAZIA(); prefAplicar(); };

function desenharPreferencias() {
  const alvo = document.getElementById('sim-pref');
  if (!alvo) return;
  const p = prefCarregar(), n = prefAtivas();
  const pendentes = S.disciplinas.filter(d => !['concluida', 'cursando'].includes(situacaoDe(d.id)?.situacao));
  const linhaBloco = (b, k) => `<div class="pref-linha">
      <select class="form-select" id="pref-indisponiveis-${k}-dia" aria-label="Dia" onchange="prefLinha('indisponiveis',${k},'dia',this.value)">
        ${DIAS_PREF.map(d => `<option ${b.dia === d ? 'selected' : ''}>${d}</option>`).join('')}</select>
      <input class="form-input" type="time" id="pref-indisponiveis-${k}-inicio" aria-label="Início" value="${esc(b.inicio)}" onchange="prefLinha('indisponiveis',${k},'inicio',this.value)"/>
      <input class="form-input" type="time" id="pref-indisponiveis-${k}-fim" aria-label="Fim" value="${esc(b.fim)}" onchange="prefLinha('indisponiveis',${k},'fim',this.value)"/>
      <input class="form-input" id="pref-indisponiveis-${k}-motivo" placeholder="motivo (trabalho…)" maxlength="40" aria-label="Motivo" value="${esc(b.motivo || '')}" onchange="prefLinha('indisponiveis',${k},'motivo',this.value)"/>
      <button class="btn btn-ghost btn-sm" onclick="prefRemover('indisponiveis',${k})" aria-label="Remover horário">✕</button></div>`;
  const linhaTeto = (t, k) => `<div class="pref-linha pref-linha-2">
      <input class="form-input" placeholder="2028/1" maxlength="7" aria-label="Período" value="${esc(t.periodo)}" onchange="prefLinha('tetos',${k},'periodo',this.value)"/>
      <input class="form-input" type="number" min="1" max="60" placeholder="créditos" aria-label="Créditos máximos" value="${esc(t.creditos)}" onchange="prefLinha('tetos',${k},'creditos',this.value)"/>
      <button class="btn btn-ghost btn-sm" onclick="prefRemover('tetos',${k})" aria-label="Remover teto">✕</button></div>`;
  alvo.innerHTML = `<details class="sim-bloco sim-pref" ${SIM.prefAberto ? 'open' : ''} ontoggle="SIM.prefAberto = this.open">
    <summary><b>Minha rotina</b> <span class="sim-dica">${n ? `${n} ativa${n > 1 ? 's' : ''}` : 'trabalho, turno, trancamento…'}</span></summary>
    <div class="pref-grid">
      <div class="pref-grupo pref-grade" id="pref-indisponiveis" tabindex="-1"><div class="form-label">Quando você NÃO pode ter aula (clique ou arraste)</div>
        ${gradeSemanal()}
        <details class="pref-exatos"><summary>Ajustar horários exatos</summary>
          ${p.indisponiveis.map(linhaBloco).join('') || '<div class="sim-dica">Nenhum.</div>'}
          <button class="btn btn-ghost btn-sm" onclick="prefAdicionar('indisponiveis')">+ Horário</button></details></div>
      <div class="pref-grupo">
        <label class="form-label" for="pref-turno">Turno preferido</label>
        <select class="form-select" id="pref-turno" onchange="prefMudar('turno', this.value)">
          ${[['', 'Tanto faz'], ['manha', 'Manhã'], ['tarde', 'Tarde'], ['noite', 'Noite']].map(([v, t]) => `<option value="${v}" ${p.turno === v ? 'selected' : ''}>${t}</option>`).join('')}</select>
        <fieldset class="pref-dias" id="pref-dias_livres" tabindex="-1"><legend class="form-label">Dias que quero livres</legend>
          ${DIAS_PREF.map(d => `<label><input type="checkbox" ${p.dias_livres.includes(d) ? 'checked' : ''} onchange="prefDia('${d}', this.checked)"/> ${d}</label>`).join('')}</fieldset>
      </div>
      <div class="pref-grupo">
        <label class="form-label" for="pref-max_pesadas">Máx. disciplinas pesadas por semestre</label>
        <input class="form-input" type="number" min="1" max="10" id="pref-max_pesadas" placeholder="sem limite" value="${esc(p.max_pesadas)}" onchange="prefMudar('max_pesadas', this.value)"/>
        <details class="sug-feitas" id="pref-pesadas" tabindex="-1"><summary>Quais acho pesadas${p.pesadas.length ? ` (${p.pesadas.length})` : ''}</summary>
          <div class="sim-dica">As que você já reprovou contam sozinhas.</div>
          <div class="sug-feitas-lista">${pendentes.map(d => { const rep = situacaoDe(d.id)?.reprovada_antes;
            return `<label class="sug-feita"><input type="checkbox" ${rep || p.pesadas.includes(d.id) ? 'checked' : ''} ${rep ? 'disabled' : ''} onchange="prefPesada(${d.id}, this.checked)"/> <b>${esc(d.codigo)}</b> ${esc(d.nome)}${rep ? ' · já reprovada' : ''}</label>`; }).join('')}</div></details>
      </div>
      <div class="pref-grupo" id="pref-juntas" tabindex="-1"><div class="form-label">Cursar junto</div>
        ${(S.preferencias?.juntas || []).map((g, k) => `<div class="pref-linha pref-linha-2">
          <span>${g.disciplinas.map(x => esc(S.disciplinas.find(y => y.id === x)?.codigo || x)).join(' + ')}</span>
          <select class="form-select" aria-label="Regra do grupo" onchange="juntasRegra(${k}, this.value)">
            <option value="obrigatoria" ${g.regra === 'obrigatoria' ? 'selected' : ''}>sempre juntas</option>
            <option value="preferencia" ${g.regra === 'preferencia' ? 'selected' : ''}>juntas se der</option></select>
          <button class="btn btn-ghost btn-sm" onclick="juntasRemover(${k})" aria-label="Desfazer grupo">✕</button></div>`).join('') || '<div class="sim-dica">Nenhum grupo.</div>'}
        <button class="btn btn-ghost btn-sm" onclick="juntasEscolher()">+ Cursar duas juntas</button></div>
      <div class="pref-grupo" id="pref-fixas" tabindex="-1"><div class="form-label">Cursar em um período específico</div>
        <div class="sim-dica">A sugestão põe a disciplina exatamente nesse período (se ela abrir e os requisitos deixarem).</div>
        ${p.fixas.map((f, k) => `<div class="pref-linha pref-linha-2">
          <select class="form-select" aria-label="Disciplina" onchange="prefLinha('fixas',${k},'disciplina_id',Number(this.value))">
            <option value="">Disciplina…</option>
            ${S.disciplinas.filter(x => !['concluida', 'cursando'].includes(situacaoDe(x.id)?.situacao)).map(x =>
              `<option value="${x.id}" ${x.id === f.disciplina_id ? 'selected' : ''}>${esc(x.codigo)} · ${esc(x.nome)}</option>`).join('')}</select>
          <select class="form-select" aria-label="Período" onchange="prefLinha('fixas',${k},'periodo',this.value)">
            <option value="">Período…</option>
            ${periodosSugeridos(12).map(per => `<option ${per === f.periodo ? 'selected' : ''}>${per}</option>`).join('')}</select>
          <button class="btn btn-ghost btn-sm" onclick="prefRemover('fixas',${k})" aria-label="Remover">✕</button></div>`).join('')}
        <button class="btn btn-ghost btn-sm" onclick="prefAdicionar('fixas')">+ Disciplina em período</button></div>
      <div class="pref-grupo" id="pref-optativas" tabindex="-1"><div class="form-label">Optativas</div>
        <label class="form-label" for="pref-optativas_faltando">Ainda preciso de (créditos)</label>
        <input class="form-input" type="number" min="0" max="120" id="pref-optativas_faltando" value="${esc(p.opt_faltando)}"
          placeholder="${S.curso?.creditos_optativos_exigidos != null ? 'automático pelo curso' : 'o curso não informa'}"
          onchange="prefMudar('opt_faltando', this.value)"/>
        <details class="sug-feitas" id="pref-optativas_feitas"><summary>Já fiz fora do histórico${p.opt_feitas.length ? ` (${p.opt_feitas.length})` : ''}</summary>
          <div class="sug-feitas-lista">${S.disciplinas.filter(x => x.tipo !== 'obrigatoria' && !['concluida', 'cursando'].includes(situacaoDe(x.id)?.situacao)).map(x =>
            `<label class="sug-feita"><input type="checkbox" ${p.opt_feitas.includes(x.id) ? 'checked' : ''} onchange="prefOptFeita(${x.id}, this.checked)"/> <b>${esc(x.codigo)}</b> ${esc(x.nome)}${x.creditos ? ` · ${x.creditos} cr` : ''}</label>`).join('') || '<div class="sim-dica">Nenhuma optativa a marcar.</div>'}</div></details>
      </div>
      <div class="pref-grupo" id="pref-teto_por_periodo" tabindex="-1"><div class="form-label">Teto de créditos num período (TCC, estágio…)</div>
        ${p.tetos.map(linhaTeto).join('')}
        <button class="btn btn-ghost btn-sm" onclick="prefAdicionar('tetos')">+ Período</button></div>
      <div class="pref-grupo">
        <label class="form-label" for="pref-periodos_pulados">Vou trancar</label>
        <input class="form-input" id="pref-periodos_pulados" placeholder="ex.: 2028/2" value="${esc(p.pulados)}" onchange="prefMudar('pulados', this.value)"/>
        <label class="form-label" for="pref-periodo_ingresso">Entrei no curso em</label>
        <input class="form-input" id="pref-periodo_ingresso" maxlength="7" placeholder="auto (pelo histórico)" value="${esc(p.ingresso)}" onchange="prefMudar('ingresso', this.value)"/>
        <label class="form-label" for="pref-fator_prazo_maximo">Prazo máximo (× duração)</label>
        <input class="form-input" id="pref-fator_prazo_maximo" inputmode="decimal" placeholder="1,5" value="${esc(p.fator)}" onchange="prefMudar('fator', this.value)"/>
      </div>
    </div>
    <div class="sim-acoes"><button class="btn btn-primary btn-sm" onclick="prefAplicar()">Salvar rotina</button>
      ${n ? '<button class="btn btn-ghost btn-sm" onclick="prefLimpar()">Limpar tudo</button>' : ''}
      <span class="sim-dica">Ficam guardadas na sua conta para este curso.</span></div>
  </details>`;
  mostrarErroDeCampo();
}


// ═══════════════════════════════════════════════════════
// "CURSAR JUNTO" (TCC + Seminário…): pergunta UMA vez, depois só em Preferências
// ═══════════════════════════════════════════════════════
SIM.juntas = null;     // {candidatas, perguntar, pergunta} vindo do servidor
async function desenharPerguntaJuntas() {
  const alvo = document.getElementById('sim-juntas');
  if (!alvo) return;
  if (SIM.juntas === null) {
    SIM.juntas = {candidatas: [], perguntar: false};          // evita pedir duas vezes
    const r = await GET(`/api/cursos/${CURSO_ID}/juntas/candidatas`);
    if (r.ok) SIM.juntas = r;
  }
  const j = SIM.juntas;
  if (!j.perguntar || S.preferencias?.juntas_respondida) { alvo.innerHTML = ''; return; }
  alvo.innerHTML = `<section class="sim-bloco sim-pergunta" aria-labelledby="pj-t"><h3 id="pj-t">${esc(j.pergunta)}</h3>
    <ul class="sim-premissas">${j.candidatas.map(c => `<li>${esc(c.texto)}</li>`).join('')}</ul>
    <div class="sim-acoes">
      <button class="btn btn-primary btn-sm" onclick="juntasAceitar()">Sim, essas juntas</button>
      <button class="btn btn-ghost btn-sm" onclick="juntasEscolher()">Escolher outras</button>
      <button class="btn btn-ghost btn-sm" onclick="juntasNao()">Não, obrigado</button>
    </div></section>`;
}
window.juntasAceitar = async () => {
  const juntas = [...(S.preferencias?.juntas || []),
    ...SIM.juntas.candidatas.map(c => ({disciplinas: c.disciplinas.map(x => x.id), regra: 'obrigatoria'}))];
  if (await salvarPreferencias({juntas, juntas_respondida: true})) { toast('Grupos guardados. Dá para mudar em Preferências.', 'success'); simuladorDepoisDeJuntas(); }
};
window.juntasNao = async () => { if (await salvarPreferencias({juntas_respondida: true})) simuladorDepoisDeJuntas(); };
window.juntasEscolher = () => {
  const lista = S.disciplinas.filter(d => situacaoDe(d.id)?.situacao !== 'concluida');
  const opcoes = lista.map(d => `<option value="${d.id}">${esc(d.codigo)} · ${esc(d.nome)}</option>`).join('');
  openModal(`<h2>Cursar duas disciplinas juntas</h2>
    <label class="form-label" for="pj-a">Esta</label><select class="form-select" id="pj-a">${opcoes}</select>
    <label class="form-label" for="pj-b" style="margin-top:8px">junto com</label><select class="form-select" id="pj-b">${opcoes}</select>
    <div class="campo-erro" id="pj-erro" role="alert"></div>
    <div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="juntasCriar()">Cursar juntas</button></div>`);
};
window.juntasCriar = async () => {
  const a = Number(document.getElementById('pj-a').value), b = Number(document.getElementById('pj-b').value);
  if (a === b) { document.getElementById('pj-erro').textContent = 'Escolha duas disciplinas diferentes.'; return; }
  const juntas = [...(S.preferencias?.juntas || []), {disciplinas: [a, b], regra: 'obrigatoria'}];
  if (await salvarPreferencias({juntas, juntas_respondida: true})) { closeModal(); simuladorDepoisDeJuntas(); }
};
window.juntasRegra = async (k, regra) => {
  const juntas = (S.preferencias?.juntas || []).map((g, i) => i === k ? {...g, regra} : g);
  if (await salvarPreferencias({juntas})) simuladorDepoisDeJuntas();
};
window.juntasRemover = async k => {
  const antes = S.preferencias?.juntas || [];
  if (await salvarPreferencias({juntas: antes.filter((_, i) => i !== k)})) {
    simuladorDepoisDeJuntas();
    toastAcao('Grupo desfeito.', 'Desfazer', async () => { if (await salvarPreferencias({juntas: antes})) simuladorDepoisDeJuntas(); });
  }
};
function simuladorDepoisDeJuntas() {
  SIM.sim.assinatura = null;
  desenharPreferencias(); desenharPerguntaJuntas();
  if (planoTemItens()) simRodar(true);
  if (SIM.sug.dados) simSugerir();
}


// ── Sugestão: progresso por etapas (H1) ─────────────────────────────────
// A resposta vem de uma vez; enquanto espera, o indicador avança por uma ESTIMATIVA de tempo de cada
// etapa (e diz isso). Quando chega, a tela mostra o tempo real de cada uma (`etapas` do servidor).
const ETAPAS_SUG = [['Grafo de requisitos e limite mínimo', 400], ['Primeiro plano (guloso)', 300],
  ['Melhorando (recozimento simulado)', 2500], ['Escolhendo turmas', 600], ['Chance de formar (500 simulações)', 2500]];
function etapaAtual() {
  let t = Date.now() - (SIM.sug.inicio || Date.now());
  for (let i = 0; i < ETAPAS_SUG.length; i++) { if (t < ETAPAS_SUG[i][1]) return i; t -= ETAPAS_SUG[i][1]; }
  return ETAPAS_SUG.length - 1;
}
function blocoEtapas() {
  const atual = etapaAtual();
  return `<div class="sim-faixa sim-carregando" role="status" aria-live="polite"><span><span class="sim-spin" aria-hidden="true"></span> Calculando o melhor plano…</span></div>
    <ol class="etapas-sug" id="etapas-sug">${ETAPAS_SUG.map(([rot], i) =>
      `<li class="${i < atual ? 'feita' : i === atual ? 'atual' : ''}">${i < atual ? '✓' : i === atual ? '●' : '○'} ${esc(rot)}</li>`).join('')}</ol>
    <p class="sim-dica">O avanço é uma estimativa; ao terminar mostramos quanto cada etapa levou.</p>`;
}
function atualizarEtapas() {
  const el = document.getElementById('etapas-sug');
  if (!el || SIM.sug.estado !== 'carregando') return;
  const atual = etapaAtual();
  [...el.children].forEach((li, i) => {
    li.className = i < atual ? 'feita' : i === atual ? 'atual' : '';
    li.textContent = `${i < atual ? '✓' : i === atual ? '●' : '○'} ${ETAPAS_SUG[i][0]}`;
  });
}

// ── Plano atual × Sugestão, lado a lado, antes de salvar (indicadores prontos do servidor) ──
function comparar(a, b, melhor) {
  if (a == null || b == null || a === b) return 0;
  const n = v => typeof v === 'string' ? v.split('/').reduce((x, y) => x * 10 + Number(y), 0) : v;
  const d = n(b) - n(a);
  return (melhor === 'menor' ? -d : d) > 0 ? 1 : -1;            // 1 = sugestão melhor
}
function blocoComparacao(atual, sug) {
  if (!sug?.length) return '';
  if (!atual) return '';                 // sem plano simulado, uma coluna de "–" só confunde
  const porChave = Object.fromEntries((atual || []).map(x => [x.chave, x]));
  const linhas = sug.map(x => {
    const a = porChave[x.chave], c = comparar(a?.valor, x.valor, x.melhor);
    return `<tr><th scope="row">${esc(x.rotulo)}</th><td class="${c < 0 ? 'melhor' : ''}">${a ? esc(a.texto) : '–'}${c < 0 ? ' <span aria-label="melhor">✓</span>' : ''}</td>
      <td class="${c > 0 ? 'melhor' : ''}">${esc(x.texto)}${c > 0 ? ' <span aria-label="melhor">✓</span>' : ''}</td></tr>`;
  }).join('');
  return `<div class="comparacao"><table><caption>Plano atual × Sugestão</caption>
    <thead><tr><th scope="col"></th><th scope="col">Plano atual</th><th scope="col">Sugestão</th></tr></thead><tbody>${linhas}</tbody></table>
    ${atual ? '' : '<p class="sim-dica">Simule um plano para comparar com ele.</p>'}</div>`;
}

// ── Grade semanal clicável para marcar quando NÃO dá (com presets) ──────
const HORAS_GRADE = Array.from({length: 16}, (_, i) => 7 + i);       // 07h … 22h (faixas de 1 h)
const DIAS_GRADE = ['SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SAB'];
const DIA_NOME = {SEG: 'Segunda', TER: 'Terça', QUA: 'Quarta', QUI: 'Quinta', SEX: 'Sexta', SAB: 'Sábado'};
const PRESETS_GRADE = {
  'Trabalho manhã': {dias: ['SEG', 'TER', 'QUA', 'QUI', 'SEX'], de: 8, ate: 12, motivo: 'trabalho'},
  'Estágio tarde': {dias: ['SEG', 'TER', 'QUA', 'QUI', 'SEX'], de: 13, ate: 18, motivo: 'estágio'},
  'Noturno (só à noite)': {dias: ['SEG', 'TER', 'QUA', 'QUI', 'SEX'], de: 7, ate: 18, motivo: 'trabalho de dia'},
};
const minutosGrade = texto => { const [h, m] = texto.split(':').map(Number); return h * 60 + m; };
const horaGrade = m => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const celulaOcupada = (p, dia, h) => p.indisponiveis.some(b => b.dia === dia && minutosGrade(b.inicio) < (h + 1) * 60 && minutosGrade(b.fim) > h * 60);
// Junta/corta faixas do mesmo dia (mantém o motivo da primeira faixa que já existia).
function normalizarBlocos(blocos) {
  const saida = [];
  for (const dia of [...new Set(blocos.map(b => b.dia))]) {
    const doDia = blocos.filter(b => b.dia === dia).map(b => ({...b, i: minutosGrade(b.inicio), f: minutosGrade(b.fim)})).sort((a, b) => a.i - b.i);
    for (const b of doDia) {
      const ult = saida[saida.length - 1];
      if (ult && ult.dia === dia && b.i <= ult.f) { ult.f = Math.max(ult.f, b.f); ult.motivo = ult.motivo || b.motivo; }
      else saida.push({...b});
    }
  }
  return saida.filter(b => b.f > b.i).map(b => ({dia: b.dia, inicio: horaGrade(b.i), fim: horaGrade(b.f), motivo: b.motivo || ''}));
}
function alternarCelula(dia, h, ligar) {
  const p = prefCarregar(), ini = h * 60, fim = (h + 1) * 60;
  if (ligar) p.indisponiveis = normalizarBlocos([...p.indisponiveis, {dia, inicio: horaGrade(ini), fim: horaGrade(fim), motivo: ''}]);
  else p.indisponiveis = normalizarBlocos(p.indisponiveis.flatMap(b => {
    if (b.dia !== dia) return [b];
    const i = minutosGrade(b.inicio), f = minutosGrade(b.fim);
    if (f <= ini || i >= fim) return [b];
    return [i < ini ? {...b, fim: horaGrade(ini)} : null, f > fim ? {...b, inicio: horaGrade(fim)} : null].filter(Boolean);
  }));
}
let _pintando = null;                              // arrastar o mouse pinta (ou apaga) várias células
window.gradeInicio = (e, dia, h) => {
  e.preventDefault();
  _pintando = !celulaOcupada(prefCarregar(), dia, h);
  alternarCelula(dia, h, _pintando); desenharGrade();
};
window.gradeEntra = (dia, h) => { if (_pintando === null) return; alternarCelula(dia, h, _pintando); desenharGrade(); };
window.gradeTecla = (e, dia, h) => {
  if (e.key !== 'Enter' && e.key !== ' ') return;
  e.preventDefault(); alternarCelula(dia, h, !celulaOcupada(prefCarregar(), dia, h)); desenharGrade();
  document.querySelector(`[data-celula="${dia}-${h}"]`)?.focus();
};
document.addEventListener('pointerup', () => { _pintando = null; });
window.gradePreset = nome => {
  const x = PRESETS_GRADE[nome], p = prefCarregar();
  p.indisponiveis = normalizarBlocos([...p.indisponiveis,
    ...x.dias.map(dia => ({dia, inicio: horaGrade(x.de * 60), fim: horaGrade(x.ate * 60), motivo: x.motivo}))]);
  desenharPreferencias();
};
window.gradeLimpar = () => { prefCarregar().indisponiveis = []; desenharPreferencias(); };
function gradeSemanal() {
  const p = prefCarregar();
  return `<div class="grade-presets">${Object.keys(PRESETS_GRADE).map(n => `<button class="btn btn-ghost btn-sm" onclick="gradePreset('${n}')">${esc(n)}</button>`).join('')}
      <button class="btn btn-ghost btn-sm" onclick="gradeLimpar()">Limpar</button></div>
    <div class="grade-semanal" id="grade-semanal" role="grid" aria-label="Clique nas horas em que você não pode ter aula">
      <div class="grade-cab" role="row"><span></span>${DIAS_GRADE.map(d => `<span role="columnheader">${d}</span>`).join('')}</div>
      ${HORAS_GRADE.map(h => `<div class="grade-linha" role="row"><span class="grade-hora" role="rowheader">${String(h).padStart(2, '0')}h</span>
        ${DIAS_GRADE.map(d => { const on = celulaOcupada(p, d, h);
          return `<button class="grade-celula ${on ? 'on' : ''}" role="gridcell" data-celula="${d}-${h}" aria-pressed="${on}"
            aria-label="${DIA_NOME[d]}, ${h}h às ${h + 1}h: ${on ? 'indisponível' : 'livre'}"
            onpointerdown="gradeInicio(event,'${d}',${h})" onpointerenter="gradeEntra('${d}',${h})" onkeydown="gradeTecla(event,'${d}',${h})"></button>`; }).join('')}</div>`).join('')}
    </div>
    <div class="sim-dica">${p.indisponiveis.length ? p.indisponiveis.map(b => `${b.dia} ${b.inicio}–${b.fim}${b.motivo ? ' (' + esc(b.motivo) + ')' : ''}`).join(' · ') : 'Nada marcado: todos os horários servem.'}</div>`;
}
function desenharGrade() {
  const g = document.getElementById('grade-semanal');
  if (!g) return;
  const p = prefCarregar();
  g.querySelectorAll('.grade-celula').forEach(c => {
    const [dia, h] = c.dataset.celula.split('-');
    const on = celulaOcupada(p, dia, Number(h));
    c.classList.toggle('on', on);
    c.setAttribute('aria-pressed', String(on));
    c.setAttribute('aria-label', `${DIA_NOME[dia]}, ${h}h às ${Number(h) + 1}h: ${on ? 'indisponível' : 'livre'}`);
  });
  g.nextElementSibling.textContent = p.indisponiveis.length
    ? p.indisponiveis.map(b => `${b.dia} ${b.inicio}–${b.fim}${b.motivo ? ' (' + b.motivo + ')' : ''}`).join(' · ') : 'Nada marcado: todos os horários servem.';
}


// Uma linha com a rotina que o Simulador está usando (editar fica em "Minha rotina").
function resumoRotina() {
  const p = S.preferencias || {};
  const partes = [];
  if (p.indisponiveis?.length) partes.push(`${p.indisponiveis.length} horário${p.indisponiveis.length > 1 ? 's' : ''} em que não pode`);
  if (p.turno) partes.push(`prefere ${({manha: 'manhã', tarde: 'tarde', noite: 'noite'})[p.turno]}`);
  if (p.max_pesadas) partes.push(`até ${p.max_pesadas} pesada${p.max_pesadas > 1 ? 's' : ''} por semestre`);
  if (p.periodos_pulados?.length) partes.push(`trancamento em ${p.periodos_pulados.join(', ')}`);
  if (p.optativas_faltando != null) partes.push(`ainda precisa de ${p.optativas_faltando} cr de optativas`);
  if (p.juntas?.length) partes.push(`${p.juntas.length} par${p.juntas.length > 1 ? 'es' : ''} para cursar junto`);
  return `<div class="sim-nota sim-rotina"><b>Sua rotina:</b> ${partes.length ? esc(partes.join(' · ')) : 'nada informado (todos os horários servem)'}
    · <a href="#" onclick="irPara('rotina');return false">${partes.length ? 'editar' : 'contar minha rotina'}</a></div>`;
}


// Minha rotina: logo abaixo do texto, a resposta para "com esta rotina, dá para cursar o que falta?".
async function desenharVereditoRotina() {
  const alvo = document.getElementById('rotina-veredito');
  if (!alvo) return;
  const r = await GET(`/api/cursos/${CURSO_ID}/rotina`);
  if (!document.getElementById('rotina-veredito')) return;     // saiu da tela enquanto esperava
  alvo.innerHTML = r.ok && r.rotina ? cartaoRotina(r.rotina) : '';
}
