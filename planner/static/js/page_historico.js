// ═══════════════════════════════════════════════════════
// PAGE: HISTÓRICO
// Lista de TENTATIVAS do aluno (reprovar e cursar de novo = duas linhas). As regras
// (o que conta como concluído, progresso, previsão) são do servidor: depois de cada
// mudança aqui, `carregarAluno()` traz o painel atualizado.
// ═══════════════════════════════════════════════════════
const STATUS_HIST = {
  aprovado:  {cls: 'badge-green',  rotulo: 'Aprovado'},
  reprovado: {cls: 'badge-red',    rotulo: 'Reprovado'},
  cursando:  {cls: 'badge-yellow', rotulo: 'Cursando'},
};

function historico() {
  const tb = document.getElementById('topbar-actions');
  tb.innerHTML = `<button class="btn btn-primary btn-sm" onclick="historicoModal()">+ Adicionar</button>`;

  const celula = 'padding:10px 14px';
  const c = document.getElementById('content');
  c.innerHTML = `
  <div class="card" style="margin-bottom:16px">
    <div style="display:flex;gap:16px;flex-wrap:wrap">
      ${Object.keys(STATUS_HIST).map(s => {
        const itens = S.historico.filter(h => h.status === s);
        const creditos = itens.reduce((soma, h) => soma + (h.creditos || 0), 0);
        const semCreditos = itens.filter(h => h.creditos == null).length;
        return `<div>
          <div class="stat-label">${STATUS_HIST[s].rotulo}</div>
          <div style="font-size:20px;font-weight:700">${itens.length} ${itens.length === 1 ? 'tentativa' : 'tentativas'}</div>
          <div class="stat-sub">${creditos} créditos${semCreditos ? ` (+${semCreditos} sem créditos informados)` : ''}</div>
        </div>`;
      }).join('<div style="width:1px;background:var(--border)"></div>')}
    </div>
  </div>
  <div class="card" style="padding:0;overflow:hidden">
    <table style="width:100%;border-collapse:collapse">
      <thead>
        <tr style="background:var(--bg3)">
          ${['Código','Disciplina','Período','Créditos','Status','Nota','Período Letivo',''].map(h =>
            `<th style="${celula};text-align:left;font-size:11px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--border)">${h}</th>`
          ).join('')}
        </tr>
      </thead>
      <tbody>
        ${S.historico.length === 0
          ? `<tr><td colspan="8" class="empty" style="padding:40px;text-align:center">
               <button class="btn btn-primary" onclick="historicoModal()">+ Adicionar a primeira disciplina</button></td></tr>`
          : S.historico.map(h => `
          <tr style="border-bottom:1px solid var(--border)" onmouseenter="this.style.background='var(--bg3)'" onmouseleave="this.style.background=''">
            <td style="${celula};font-size:12px;font-weight:700;color:var(--text3)">${esc(h.codigo)}</td>
            <td style="${celula};font-size:13px;font-weight:500">${esc(h.nome)}</td>
            <td style="${celula};font-size:12px;color:var(--text2)">${periodStr(h.periodo_sugerido)}</td>
            <td style="${celula};font-size:12px;color:var(--text2)">${valorOu(h.creditos)}</td>
            <td style="${celula}"><span class="badge ${STATUS_HIST[h.status].cls}">${STATUS_HIST[h.status].rotulo}</span></td>
            <td style="${celula};font-size:13px">${valorOu(h.nota)}</td>
            <td style="${celula};font-size:12px;color:var(--text2)">${esc(valorOu(h.periodo_letivo))}</td>
            <td style="${celula};white-space:nowrap">
              <button class="btn btn-ghost btn-sm" style="font-size:10px" onclick="historicoModal({id:${h.id}})">Editar</button>
              <button class="btn btn-danger btn-sm" style="font-size:10px" onclick="removerTentativa(${h.id})">Remover</button>
            </td>
          </tr>`).join('')}
      </tbody>
    </table>
  </div>`;
}

// Depois de mudar o histórico: painel novo e a tela atual redesenhada.
async function aposMudarHistorico() {
  await carregarAluno();
  render();
}

async function removerTentativa(id) {
  if (!confirm('Remover este registro?')) return;
  const r = await DEL(`/api/cursos/${CURSO_ID}/historico/${id}`);
  if (!r.ok) { toast(r.erro || 'Não foi possível remover.', 'error'); return; }
  toast('Removido do histórico', 'info');
  await aposMudarHistorico();
}

// Janela de adicionar/editar. `{id}` edita a tentativa; `{disciplinaId}` já escolhe a disciplina.
function historicoModal({id = null, disciplinaId = null} = {}) {
  const atual = id ? S.historico.find(h => h.id === id) : null;
  const discId = atual ? atual.disciplina_id : disciplinaId;
  const opcoes = S.disciplinas.map(d =>
    `<option value="${d.id}" ${d.id === discId ? 'selected' : ''}>${esc(d.codigo)} – ${esc(d.nome)}</option>`).join('');
  const status = atual?.status || 'aprovado';

  openModal(`<h2>${atual ? 'Editar' : 'Adicionar ao'} Histórico</h2>
    <div class="form-group">
      <label class="form-label">Disciplina</label>
      <select id="h-disc" class="form-select" ${atual ? 'disabled' : ''}>${opcoes}</select>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">Status</label>
        <select id="h-status" class="form-select">
          ${Object.entries(STATUS_HIST).map(([v, s]) => `<option value="${v}" ${v === status ? 'selected' : ''}>${s.rotulo}</option>`).join('')}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Nota (opcional)</label>
        <input id="h-nota" class="form-input" type="number" min="0" max="100" step="0.1" value="${esc(atual?.nota ?? '')}"/>
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">Período letivo (opcional)</label>
      <input id="h-pl" class="form-input" placeholder="2026/1" value="${esc(atual?.periodo_letivo ?? '')}"/>
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="salvarTentativa(${id ?? 'null'})">Salvar</button>
    </div>`);
}

async function salvarTentativa(id) {
  const nota = document.getElementById('h-nota').value;
  const corpo = {
    status: document.getElementById('h-status').value,
    nota: nota === '' ? null : Number(nota),
    periodo_letivo: document.getElementById('h-pl').value.trim() || null,
  };
  const r = id
    ? await PUT(`/api/cursos/${CURSO_ID}/historico/${id}`, corpo)
    : await POST(`/api/cursos/${CURSO_ID}/historico`, {...corpo, disciplina_id: Number(document.getElementById('h-disc').value)});
  if (!r.ok) { toast(r.erro || 'Não foi possível salvar.', 'error'); return; }   // a janela fica aberta para corrigir
  closeModal();
  toast(id ? 'Histórico atualizado!' : 'Adicionado ao histórico!', 'success');
  await aposMudarHistorico();
}
