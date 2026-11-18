// ═══════════════════════════════════════════════════════
// PAGE: CALENDÁRIO (Etapa 4B)
// Desenha os encontros das TURMAS ESCOLHIDAS no semestre. Dias e faixa de horas
// vêm de `S.grade` (derivada no servidor dos dados do curso: sábado, noturno…).
// Conflitos vêm da análise do servidor; aqui só são destacados.
// ═══════════════════════════════════════════════════════
function calendario() {
  const plano = Planos.atual();
  const semOpts = plano ? plano.semestres.map(s =>
    `<option value="${s.id}" ${s.id===S.calendarSemId?'selected':''}>${esc(s.rotulo)}${s.periodo_letivo ? ' · ' + esc(s.periodo_letivo) : ''}</option>`
  ).join('') : '';

  const c = document.getElementById('content');
  c.innerHTML = `
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
    <span style="font-size:13px;color:var(--text2)">Visualizar semestre:</span>
    <select class="form-select" style="width:240px" onchange="calendarSemChange(+this.value)">
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
function eventosDoSemestre(sem, conflitantes) {
  const eventos = [];
  sem.itens.forEach(item => {
    const d = S.disciplinas.find(x => x.id === item.disciplina_id);
    const livres = encontrosLivresDe(item);
    // Horários próprios (definidos pelo aluno) valem no lugar da turma do quadro.
    const turma = livres.length ? {codigo_turma: 'próprio', encontros: livres, propria: true}
      : item.turma_id ? S.turmas.find(t => t.id === item.turma_id) : null;
    if (!d || !turma) return;
    turma.encontros.forEach(e => eventos.push({
      ...e, disciplina: d, turma, conflito: conflitantes.has(d.id),
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

  // Só conflito CONFIRMADO (turmas já escolhidas) é pintado de vermelho.
  const analise = analiseDoSemestre(semId);
  const conflitantes = new Set();
  (analise?.conflitos || []).filter(c => c.tipo === 'conflito').forEach(c => { conflitantes.add(c.a.id); conflitantes.add(c.b.id); });

  const eventos = eventosDoSemestre(sem, conflitantes);
  const grade = gradeDoCalendario(eventos);
  const horas = [];
  for (let h = grade.hora_inicio; h < grade.hora_fim; h++) horas.push(h);

  const diaFull = {SEG:'Segunda',TER:'Terça',QUA:'Quarta',QUI:'Quinta',SEX:'Sexta',SAB:'Sábado',DOM:'Domingo'};
  const alturaHora = 56;                       // px por hora
  const porMinuto = alturaHora / 60;
  const minutos = t => { const [hh, mm] = t.split(':').map(Number); return hh * 60 + mm; };
  const totalH = horas.length * alturaHora;
  const colunas = `56px repeat(${grade.dias.length},minmax(110px,1fr))`;

  let html = `<div style="overflow-x:auto"><div style="min-width:${56 + grade.dias.length * 110}px">
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
        border-radius:5px;padding:3px 5px;cursor:pointer;
        ${ev.conflito?'outline:2px solid var(--red);outline-offset:-2px':''}
        overflow:hidden" onclick="${ev.turma.propria ? `editarHorarios(${sem.id},${d.id})` : `showDiscDetail(${d.id})`}" title="${esc(d.nome)} — turma ${esc(ev.turma.codigo_turma)} (${ev.inicio}–${ev.fim})">
        <div style="font-size:10px;font-weight:700;color:var(--text)">${esc(d.codigo)} · ${esc(ev.turma.codigo_turma)}</div>
        <div style="font-size:9px;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(d.nome)}</div>
        ${ev.local ? `<div style="font-size:9px;color:var(--text2)">${esc(ev.local)}</div>` : ''}
        ${ev.conflito ? '<div style="font-size:9px;color:var(--red)">⚠️ Conflito</div>' : ''}
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
    .filter(({i, d}) => d && !i.turma_id && !encontrosLivresDe(i).length)
    .map(({d}) => {
      const tem = turmasDaDisciplina(d.id, sem.periodo_letivo).length;
      const motivo = !tem ? 'sem horário definido'
        : !sem.periodo_letivo ? 'sem horário (escolha o período letivo ou defina os seus)'
        : 'sem horário (escolha a turma ou defina os seus)';
      return `<li><strong>${esc(d.codigo)}</strong> ${esc(d.nome)} — <span style="color:var(--text3)">${esc(motivo)}</span>
        · <a href="#" onclick="editarHorarios(${sem.id},${d.id});return false">definir horários</a></li>`;
    });
  if (!fora.length) return '';
  return `<div class="card card-sm" style="margin-top:12px">
    <div style="font-size:12px;font-weight:700;color:var(--text2);margin-bottom:6px">Fora da grade (sem horário)</div>
    <ul style="font-size:12px;color:var(--text2);padding-left:18px;line-height:1.7">${fora.join('')}</ul>
    <a href="#" style="font-size:12px" onclick="irPara('planner');return false">Escolher turmas no Planejamento →</a>
  </div>`;
}
