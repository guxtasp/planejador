// ═══════════════════════════════════════════════════════
// PAGE: CALENDÁRIO (Etapa 4B)
// Desenha os encontros das TURMAS ESCOLHIDAS no semestre. Dias e faixa de horas
// vêm de `S.grade` (derivada no servidor dos dados do curso: sábado, noturno…).
// Conflitos vêm da análise do servidor; aqui só são destacados.
// ═══════════════════════════════════════════════════════
function calendario() {
  const plano = Planos.atual();
  // abre já no 1º semestre com disciplinas (antes abria vazio, pedindo para escolher)
  if (plano && !semestreDoCalendario(S.calendarSemId)) {
    S.calendarSemId = (plano.semestres.find(s => s.itens.length) || plano.semestres[0])?.id ?? null;
  }
  const semOpts = plano ? plano.semestres.map(s =>
    `<option value="${s.id}" ${s.id===S.calendarSemId?'selected':''}>${esc(s.rotulo)}${s.periodo_letivo ? ' · ' + esc(s.periodo_letivo) : ''}</option>`
  ).join('') : '';

  const c = document.getElementById('content');
  c.innerHTML = `
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
    <label for="cal-semestre" style="font-size:13px;color:var(--text2)">Semestre</label>
    <select class="form-select" id="cal-semestre" style="width:240px" onchange="calendarSemChange(+this.value)">
      <option value="0">-- Selecione --</option>
      ${semOpts}
    </select>
    ${S.calendarSemId ? `<button class="btn btn-ghost btn-sm" onclick="validarSemestre(${S.calendarSemId})">✓ Validar</button>` : ''}
  </div>
  <div class="card" style="padding:0;overflow:hidden">
    ${renderCalendar(S.calendarSemId)}
  </div>
  ${renderPendentesCalendario(S.calendarSemId)}
  `;
}

function calendarSemChange(id) {
  S.calendarSemId = id || null;
  calendario();
}

const TEXTO_VAZIO_CALENDARIO = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`;

function semestreDoCalendario(semId) {
  return semId ? Planos.atual()?.semestres.find(s => s.id === semId) || null : null;
}

// Eventos = encontros da turma escolhida de cada disciplina do semestre.
// Semestre futuro sem quadro: entra a turma PROJETADA pelo servidor (último quadro de mesma paridade),
// desenhada tracejada e marcada "estimado" — melhor que uma semana vazia.
function eventosDoSemestre(sem, conflitantes, marcas = {}) {
  const eventos = [];
  sem.itens.forEach(item => {
    const d = S.disciplinas.find(x => x.id === item.disciplina_id);
    const livres = encontrosLivresDe(item);
    const projetada = marcas[item.disciplina_id]?.turma_projetada;
    // Horários próprios (definidos pelo aluno) valem no lugar da turma do quadro.
    const turma = livres.length ? {codigo_turma: 'próprio', encontros: livres, propria: true}
      : item.turma_id ? S.turmas.find(t => t.id === item.turma_id)
      : projetada ? (t => t && {...t, estimada: true})(S.turmas.find(t => t.id === projetada)) : null;
    if (!d || !turma) return;
    turma.encontros.forEach(e => eventos.push({
      ...e, disciplina: d, turma, conflito: conflitantes.has(d.id),
      bloqueio: (S.preferencias?.indisponiveis || []).some(b => b.dia === e.dia && e.inicio < b.fim && e.fim > b.inicio),
    }));
  });
  return eventos;
}

// Eventos que se sobrepõem no mesmo dia dividem a largura da coluna (só visual:
// quem colide de fato é decidido pelo servidor). Devolve `{col, cols}` por evento.
function distribuirColunas(eventos, minutos) {
  const ordenados = [...eventos].sort((a, b) => minutos(a.inicio) - minutos(b.inicio) || minutos(a.fim) - minutos(b.fim));
  const pos = new Map();
  let grupo = [], fimGrupo = -1;
  const fechar = () => { const n = Math.max(0, ...grupo.map(e => pos.get(e).col + 1)); grupo.forEach(e => (pos.get(e).cols = n)); };
  ordenados.forEach(ev => {
    if (grupo.length && minutos(ev.inicio) >= fimGrupo) { fechar(); grupo = []; fimGrupo = -1; }
    const usadas = new Set(grupo.filter(e => minutos(e.fim) > minutos(ev.inicio)).map(e => pos.get(e).col));
    let col = 0; while (usadas.has(col)) col++;
    pos.set(ev, {col, cols: 1});
    grupo.push(ev); fimGrupo = Math.max(fimGrupo, minutos(ev.fim));
  });
  if (grupo.length) fechar();
  return pos;
}

// Grade do curso (se houver) ampliada para nunca esconder um horário próprio. Sem quadro
// importado, vale o padrão SEG–SEX 07–22 (só visual) e o aluno clica numa célula para criar.
function gradeDoCalendario(eventos) {
  const base = S.grade || {dias: ['SEG','TER','QUA','QUI','SEX'], hora_inicio: 7, hora_fim: 22};
  const mins = t => { const [h, m] = t.split(':').map(Number); return h * 60 + m; };
  const dias = new Set(base.dias);
  let ini = base.hora_inicio, fim = base.hora_fim;
  eventos.forEach(e => {
    dias.add(e.dia);
    ini = Math.min(ini, Math.floor(mins(e.inicio) / 60));
    fim = Math.max(fim, Math.ceil(mins(e.fim) / 60));
  });
  return {dias: DIAS_SEMANA.filter(d => dias.has(d)), hora_inicio: ini, hora_fim: fim};
}

function renderCalendar(semId) {
  const sem = semestreDoCalendario(semId);
  if (!sem) {
    return `<div class="empty" style="padding:60px">${TEXTO_VAZIO_CALENDARIO}<div style="font-weight:600;color:var(--text);margin-bottom:4px">Escolha um semestre</div>O calendário mostra a semana de um semestre do seu plano. Se ainda não há semestres, crie-os em Planejamento.</div>`;
  }

  // Mesma regra do Planejamento e do Simulador: as marcas vêm prontas do servidor.
  const analise = analiseDoSemestre(semId);
  const marcas = analise?.marcas || {};
  const conflitantes = new Set(Object.entries(marcas).filter(([, m]) => m.choques?.length).map(([id]) => Number(id)));

  const eventos = eventosDoSemestre(sem, conflitantes, marcas);
  const estimadas = eventos.some(e => e.turma.estimada);
  const grade = gradeDoCalendario(eventos);
  if (window.matchMedia('(max-width:640px)').matches) return calendarioEmLista(sem, eventos, grade, marcas, estimadas);
  const horas = [];
  for (let h = grade.hora_inicio; h < grade.hora_fim; h++) horas.push(h);

  const diaFull = {SEG:'Segunda',TER:'Terça',QUA:'Quarta',QUI:'Quinta',SEX:'Sexta',SAB:'Sábado',DOM:'Domingo'};
  const alturaHora = 56;                       // px por hora
  const porMinuto = alturaHora / 60;
  const minutos = t => { const [hh, mm] = t.split(':').map(Number); return hh * 60 + mm; };
  const totalH = horas.length * alturaHora;
  const colunas = `56px repeat(${grade.dias.length},minmax(110px,1fr))`;

  const choquesTexto = analise?.choques_texto
    ? `<div class="sim-nota erro" style="margin:0 0 10px">⛔ ${esc(analise.choques_texto)} neste semestre: veja os blocos com contorno vermelho.</div>` : '';
  const notaEstimada = estimadas ? `<div class="sim-nota" style="margin:0 0 10px">As turmas de ${esc(sem.periodo_letivo || 'este período')} ainda não saíram:
    os blocos tracejados repetem o último quadro de mesma paridade (estimativa, pode mudar).</div>` : '';
  let html = `${choquesTexto}${notaEstimada}<div style="overflow-x:auto"><div style="min-width:${56 + grade.dias.length * 110}px">
  <div style="display:grid;grid-template-columns:${colunas};border-bottom:1px solid var(--border)">
    <div class="cal-header cal-cell"></div>
    ${grade.dias.map(d=>`<div class="cal-header cal-cell" style="padding:12px 8px">${diaFull[d] || d}</div>`).join('')}
  </div>
  <div style="display:grid;grid-template-columns:${colunas};position:relative;height:${totalH}px">`;

  html += `<div style="position:relative">`;
  horas.forEach((h, i) => {
    html += `<div style="position:absolute;top:${i*alturaHora}px;right:6px;font-size:10px;color:var(--text3);line-height:1">${String(h).padStart(2,'0')}:00</div>`;
  });
  html += `</div>`;

  grade.dias.forEach(dia => {
    html += `<div style="position:relative;border-left:1px solid var(--border);cursor:cell" title="Clique para adicionar um horário"
      onclick="if(event.target===this||event.target.dataset.linha){const r=this.getBoundingClientRect();novoHorarioNoCalendario(${sem.id},'${dia}',Math.floor((event.clientY-r.top)/${alturaHora}*2)*30+${grade.hora_inicio * 60})}">`;
    horas.forEach((h, i) => {
      html += `<div style="position:absolute;top:${i*alturaHora}px;left:0;right:0;border-top:1px solid var(--border);opacity:.3;pointer-events:none"></div>`;
    });
    // blocos em que a pessoa não pode (preferências guardadas): faixa hachurada, atrás das aulas
    (S.preferencias?.indisponiveis || []).filter(b => b.dia === dia).forEach(b => {
      const ini = Math.max(minutos(b.inicio), grade.hora_inicio * 60), fim = Math.min(minutos(b.fim), grade.hora_fim * 60);
      if (fim <= ini) return;
      html += `<div class="cal-indisponivel" style="top:${(ini - grade.hora_inicio * 60) * porMinuto}px;height:${(fim - ini) * porMinuto}px"
        title="Indisponível${b.motivo ? ': ' + esc(b.motivo) : ''}"><span>${esc(b.motivo || 'indisponível')}</span></div>`;
    });
    const doDia = eventos.filter(ev => ev.dia === dia);
    const colunasDoDia = distribuirColunas(doDia, minutos);
    doDia.forEach(ev => {
      const d = ev.disciplina;
      const {col, cols} = colunasDoDia.get(ev);
      const larg = 100 / cols;
      const top = (minutos(ev.inicio) - grade.hora_inicio * 60) * porMinuto;
      const h = (minutos(ev.fim) - minutos(ev.inicio)) * porMinuto;
      html += `<div style="position:absolute;top:${top+2}px;left:calc(${col*larg}% + 2px);width:calc(${larg}% - 4px);height:${h-4}px;box-sizing:border-box;
        background:rgba(${hexToRgb(d.cor)},.18);border:1px solid ${esc(d.cor)};border-left:4px solid ${esc(d.cor)};
        border-radius:5px;padding:3px 5px;cursor:pointer;${ev.turma.estimada ? 'border-style:dashed;opacity:.85;' : ''}
        ${ev.conflito?'outline:2px solid var(--red);outline-offset:-2px':''}
        overflow:hidden" onclick="${ev.turma.propria ? `editarHorarios(${sem.id},${d.id})` : `showDiscDetail(${d.id})`}" title="${esc(d.nome)} — turma ${esc(ev.turma.codigo_turma)} (${ev.inicio}–${ev.fim})${ev.turma.estimada ? ' · horário estimado pelo quadro de ' + esc(ev.turma.periodo_letivo || '') : ''}">
        <div style="font-size:10px;font-weight:700;color:var(--text)">${esc(d.codigo)} · ${ev.turma.estimada ? 'estimado' : esc(parteDoEncontro(ev))}</div>
        ${abreEm(ofertaDe(d), sem.periodo_letivo) ? '' : `<div class="cal-selo">${seloOferta(d, sem.periodo_letivo)}</div>`}
        <div style="font-size:9px;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(d.nome)}</div>
        ${ev.local ? `<div style="font-size:9px;color:var(--text2)">${esc(ev.local)}</div>` : ''}
        ${ev.conflito ? `<div style="font-size:9px;color:var(--red-ink);font-weight:700">⚠️ ${esc((marcas[d.id]?.choques || [])[0]?.texto || 'Choque')}</div>` : ''}
        ${ev.bloqueio ? '<div style="font-size:9px;color:var(--red-ink);font-weight:700">⛔ Bate com sua disponibilidade</div>' : ''}
        ${(marcas[d.id]?.tags || []).filter(t => t.tipo === 'junto').map(t => `<div style="font-size:9px;color:var(--accent);font-weight:600">${esc(t.texto)}</div>`).join('')}
      </div>`;
    });
    html += `</div>`;
  });

  html += `</div></div></div>`;
  return html;
}

// Quem está no semestre mas NÃO aparece na grade, e por quê.
function renderPendentesCalendario(semId) {
  const sem = semestreDoCalendario(semId);
  if (!sem) return '';
  if (!sem.itens.length) return `<p style="margin-top:12px;font-size:12px;color:var(--text3)"><button class="btn btn-primary btn-sm" onclick="irPara('planner')">+ Adicionar disciplinas</button></p>`;

  const fora = sem.itens.map(i => ({i, d: S.disciplinas.find(x => x.id === i.disciplina_id)}))
    .filter(({i, d}) => d && !i.turma_id && !encontrosLivresDe(i).length && !analiseDoSemestre(semId)?.marcas?.[d.id]?.turma_projetada)
    .map(({d}) => {
      const tem = turmasDaDisciplina(d.id, sem.periodo_letivo).length;
      const motivo = !tem ? 'sem horário definido'
        : !sem.periodo_letivo ? 'sem horário (escolha o período letivo ou defina os seus)'
        : 'sem horário (escolha a turma ou defina os seus)';
      return `<li><strong>${esc(d.codigo)}</strong> ${esc(d.nome)} ${seloOferta(d, sem.periodo_letivo)} — <span style="color:var(--text3)">${esc(motivo)}</span>
        · <a href="#" onclick="editarHorarios(${sem.id},${d.id});return false">definir horários</a></li>`;
    });
  if (!fora.length) return '';
  return `<div class="card card-sm" style="margin-top:12px">
    <div style="font-size:12px;font-weight:700;color:var(--text2);margin-bottom:6px">Fora da grade (sem horário)</div>
    <ul style="font-size:12px;color:var(--text2);padding-left:18px;line-height:1.7">${fora.join('')}</ul>
    <a href="#" style="font-size:12px" onclick="irPara('planner');return false">Escolher turmas no Planejamento →</a>
  </div>`;
}


// Celular: a semana vira uma lista por dia (sem rolagem lateral; quinta e sexta não somem da tela).
function calendarioEmLista(sem, eventos, grade, marcas, estimadas) {
  const nomes = {SEG: 'Segunda', TER: 'Terça', QUA: 'Quarta', QUI: 'Quinta', SEX: 'Sexta', SAB: 'Sábado', DOM: 'Domingo'};
  const analise = analiseDoSemestre(sem.id);
  const topo = `${analise?.choques_texto ? `<div class="sim-nota erro">⛔ ${esc(analise.choques_texto)} neste semestre.</div>` : ''}
    ${estimadas ? `<div class="sim-nota">Turmas de ${esc(sem.periodo_letivo || 'este período')} ainda não saíram: os itens tracejados são estimativa.</div>` : ''}`;
  const dias = grade.dias.map(dia => {
    const doDia = eventos.filter(e => e.dia === dia).sort((a, b) => a.inicio.localeCompare(b.inicio));
    const bloqueios = (S.preferencias?.indisponiveis || []).filter(b => b.dia === dia);
    return `<section><h3>${nomes[dia] || dia}${bloqueios.length ? ` <span class="badge badge-gray">${bloqueios.map(b => `${esc(b.motivo || 'indisponível')} ${b.inicio}–${b.fim}`).join(' · ')}</span>` : ''}</h3>
      ${doDia.length ? `<ul>${doDia.map(ev => `<li class="${ev.turma.estimada ? 'estimada' : ''} ${ev.conflito ? 'conflito' : ''}" style="border-left-color:${esc(ev.disciplina.cor)}"
          onclick="${ev.turma.propria ? `editarHorarios(${sem.id},${ev.disciplina.id})` : `showDiscDetail(${ev.disciplina.id})`}">
          <span class="hora">${ev.inicio}–${ev.fim}</span>
          <span><b>${esc(ev.disciplina.codigo)}</b> ${esc(ev.disciplina.nome)}${ev.turma.estimada ? ' <i>(estimado)</i>' : ''}
            ${ev.local ? `<br><small>${esc(ev.local)}</small>` : ''}
            ${ev.conflito ? `<br><span class="alerta">⚠ ${esc((marcas[ev.disciplina.id]?.choques || [])[0]?.texto || 'Choque')}</span>` : ''}
            ${ev.bloqueio ? '<br><span class="alerta">⛔ Bate com sua disponibilidade</span>' : ''}</span></li>`).join('')}</ul>`
        : '<div class="livre">Sem aula</div>'}</section>`;
  }).join('');
  return `${topo}<div class="cal-lista">${dias}</div>`;
}

// Turma "teórica + prática": cada bloco diz de qual parte é (T1 teórica, P2 prática).
function parteDoEncontro(ev) {
  const parte = ev.componente && (ev.turma.partes || []).find(p => p.componente === ev.componente);
  return parte ? `${parte.codigo_turma} ${ev.componente === 'pratica' ? 'prática' : 'teórica'}` : ev.turma.codigo_turma;
}
