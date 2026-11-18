// ═══════════════════════════════════════════════════════
// HORÁRIOS PRÓPRIOS (calendário livre)
// O aluno define os horários de uma disciplina na mão, sem depender de turma importada
// nem de período letivo. Valem no lugar da turma e entram na detecção de conflitos
// (o servidor é quem julga; aqui só se edita e se mostra).
// ═══════════════════════════════════════════════════════
const DIAS_SEMANA = ['SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SAB', 'DOM'];

const itemDoPlano = (semId, discId) =>
  Planos.atual()?.semestres.find(s => s.id === semId)?.itens.find(i => i.disciplina_id === discId) || null;

const encontrosLivresDe = item => (item && item.encontros_livres) || [];

const resumoHorarios = encontros =>
  encontros.map(e => `${diaLabel(e.dia)} ${e.inicio}–${e.fim}`).join(', ');

const hhmm = min => `${String(Math.floor(min / 60)).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`;

function linhaHorario(e = {dia: 'SEG', inicio: '08:00', fim: '10:00'}) {
  return `<div class="hp-linha" style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
    <select class="form-select hp-dia" style="width:110px">
      ${DIAS_SEMANA.map(d => `<option value="${d}" ${d === e.dia ? 'selected' : ''}>${esc(diaLabel(d))}</option>`).join('')}
    </select>
    <input type="time" class="form-input hp-ini" value="${esc(e.inicio)}" style="width:110px"/>
    <span style="color:var(--text3)">até</span>
    <input type="time" class="form-input hp-fim" value="${esc(e.fim)}" style="width:110px"/>
    <button class="btn btn-ghost btn-sm" title="Remover horário" onclick="this.closest('.hp-linha').remove()">✕</button>
  </div>`;
}

function adicionarLinhaHorario() {
  document.getElementById('hp-linhas').insertAdjacentHTML('beforeend', linhaHorario());
}

// Editor de UMA disciplina do semestre.
function editarHorarios(semId, discId) {
  const item = itemDoPlano(semId, discId);
  const d = S.disciplinas.find(x => x.id === discId);
  if (!item || !d) return;
  const atuais = encontrosLivresDe(item);
  const aviso = item.turma_id
    ? `<div class="alert alert-blue" style="margin-bottom:12px"><span>ℹ️</span><div>Esta disciplina usa uma turma do quadro importado. Ao salvar horários próprios, a turma deixa de valer.</div></div>` : '';
  openModal(`<h2>Horários · ${esc(d.codigo)}</h2>
    <p style="font-size:12px;color:var(--text2);margin-bottom:12px">${esc(d.nome)}. Defina quando você tem aula; vale mesmo sem quadro de horários do curso.</p>
    ${aviso}
    <div id="hp-linhas">${(atuais.length ? atuais : [undefined]).map(e => linhaHorario(e)).join('')}</div>
    <button class="btn btn-ghost btn-sm" onclick="adicionarLinhaHorario()">+ Outro dia</button>
    <div class="modal-footer">
      ${atuais.length ? `<button class="btn btn-danger" style="margin-right:auto" onclick="limparHorarios(${semId},${discId})">Remover horários</button>` : ''}
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="salvarHorarios(${semId},${discId})">Salvar</button>
    </div>`);
}

function lerLinhasHorario() {
  return [...document.querySelectorAll('#hp-linhas .hp-linha')].map(l => ({
    dia: l.querySelector('.hp-dia').value,
    inicio: l.querySelector('.hp-ini').value,
    fim: l.querySelector('.hp-fim').value,
  }));
}

function validarLinhasHorario(linhas) {
  for (const l of linhas) {
    if (!l.inicio || !l.fim) return 'Preencha o início e o fim de cada horário.';
    if (l.inicio >= l.fim) return 'Cada horário deve terminar depois de começar.';
  }
  for (let i = 0; i < linhas.length; i++) for (let j = i + 1; j < linhas.length; j++)
    if (linhas[i].dia === linhas[j].dia && linhas[i].inicio < linhas[j].fim && linhas[i].fim > linhas[j].inicio)
      return 'Dois horários da mesma disciplina se sobrepõem.';
  return null;
}

async function reaplicarPlano() {
  S.planos = Planos.planos();
  S.currentPlano = Planos.atualId();
  await analisarPlano();
  if (S.currentPage === 'calendario') calendario(); else planner();
}

async function salvarHorarios(semId, discId) {
  const linhas = lerLinhasHorario();
  const erro = validarLinhasHorario(linhas);
  if (erro) { toast(erro, 'error'); return; }
  Planos.definirEncontros(semId, discId, linhas);
  closeModal();
  await reaplicarPlano();
}

async function limparHorarios(semId, discId) {
  Planos.definirEncontros(semId, discId, []);
  closeModal();
  await reaplicarPlano();
}

// Clique numa célula vazia do calendário: escolhe a disciplina e já vem com dia e hora.
function novoHorarioNoCalendario(semId, dia, minutoInicio) {
  const sem = Planos.atual()?.semestres.find(s => s.id === semId);
  if (!sem) return;
  const candidatas = sem.itens.filter(i => !i.turma_id).map(i => S.disciplinas.find(d => d.id === i.disciplina_id)).filter(Boolean);
  if (!candidatas.length) {
    toast('Sem disciplina para encaixar aqui: adicione uma ao semestre em Planejamento (disciplinas com turma escolhida têm horário próprio da turma).', 'warn');
    return;
  }
  openModal(`<h2>Novo horário</h2>
    <div class="form-group"><label class="form-label">Disciplina</label>
      <select id="nh-disc" class="form-select">${candidatas.map(d => `<option value="${d.id}">${esc(d.codigo)} — ${esc(d.nome)}</option>`).join('')}</select></div>
    <div id="hp-linhas">${linhaHorario({dia, inicio: hhmm(minutoInicio), fim: hhmm(Math.min(minutoInicio + 120, 23 * 60 + 59))})}</div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="salvarNovoHorario(${semId})">Salvar</button>
    </div>`);
}

async function salvarNovoHorario(semId) {
  const discId = +document.getElementById('nh-disc').value;
  const novas = lerLinhasHorario();
  const todas = [...encontrosLivresDe(itemDoPlano(semId, discId)), ...novas];
  const erro = validarLinhasHorario(todas);
  if (erro) { toast(erro, 'error'); return; }
  Planos.definirEncontros(semId, discId, todas);
  closeModal();
  await reaplicarPlano();
}
