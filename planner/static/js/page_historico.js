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
  tb.innerHTML = `<button class="btn btn-ghost btn-sm" onclick="colarAbrir()">Colar ou enviar do sistema acadêmico</button>
    <button class="btn btn-primary btn-sm" onclick="historicoModal()">+ Adicionar</button>`;

  const celula = 'padding:10px 14px';
  const c = document.getElementById('content');
  c.innerHTML = `
  ${S.historico.length === 0 ? `<div class="sim-nota" style="margin:0 0 16px">O histórico é opcional: dá para planejar e simular sem ele. Informando, as disciplinas feitas liberam os pré-requisitos, o Painel prevê a formatura pelo seu ritmo e o Simulador usa a sua taxa de aprovação.
    ${historicoPulado() ? '' : '<button class="btn btn-ghost btn-sm" onclick="pularHistorico()">Pular por agora</button>'}</div>` : ''}
  <div id="colar-bloco"></div>
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
               <div style="max-width:440px;margin:0 auto 14px;color:var(--text2)"><b style="color:var(--text)">Nada informado ainda.</b><br>Adicione as disciplinas que você já fez (aprovado ou reprovado) e as que está cursando agora. Informe também o período letivo (ex.: 2025/2) para o Rumo calcular a sua média e prever a formatura.</div>
               <button class="btn btn-primary" onclick="historicoModal()">+ Adicionar disciplina</button></td></tr>`
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
  desenharColar();     // a colagem aberta sobrevive ao redesenho da tela
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


// ── Colar a tabela do sistema acadêmico (prévia → confirmar) ──────────────
const COLAR = {aberto: false, texto: '', previa: null, ocupado: false, erro: null};
const RESULTADO_COLADO = {
  reconhecida: {cls: 'badge-green', rotulo: 'Reconhecida'},
  nao_encontrada: {cls: 'badge-red', rotulo: 'Não está no curso'},
  duplicada: {cls: 'badge-gray', rotulo: 'Repetida'},
  nao_entendida: {cls: 'badge-yellow', rotulo: 'Não entendida'},
};
window.colarAbrir = () => { COLAR.aberto = true; desenharColar(); document.getElementById('colar-texto')?.focus(); };
// Arquivo .csv/.txt exportado do sistema: o conteúdo vai para a mesma prévia do texto colado.
window.colarArquivo = input => {
  const arq = input.files?.[0];
  if (!arq) return;
  if (arq.size > 100000) { COLAR.erro = 'Arquivo grande demais: exporte só a tabela de disciplinas.'; desenharColar(); return; }
  const leitor = new FileReader();
  leitor.onload = () => { COLAR.texto = String(leitor.result || ''); desenharColar(); colarConferir(false); };
  leitor.onerror = () => { COLAR.erro = 'Não foi possível ler o arquivo.'; desenharColar(); };
  leitor.readAsText(arq, 'utf-8');
};
window.colarFechar = () => { Object.assign(COLAR, {aberto: false, previa: null, erro: null}); desenharColar(); };
window.colarConferir = async (confirmar = false) => {
  COLAR.texto = document.getElementById('colar-texto')?.value ?? COLAR.texto;
  COLAR.ocupado = true; COLAR.erro = null; desenharColar();
  const r = await POST(`/api/cursos/${CURSO_ID}/historico/colar`, {texto: COLAR.texto, confirmar});
  COLAR.ocupado = false;
  if (!r.ok) { COLAR.erro = r.erro || 'Não foi possível ler a tabela.'; desenharColar(); return; }
  COLAR.previa = r;
  if (confirmar) {
    await carregarAluno();
    toast(r.resumo, 'success', 4000);
    Object.assign(COLAR, {aberto: false, previa: null, texto: ''});
    historico();
    return;
  }
  desenharColar();
};
function desenharColar() {
  const alvo = document.getElementById('colar-bloco');
  if (!alvo) return;
  if (!COLAR.aberto) { alvo.innerHTML = ''; return; }
  const p = COLAR.previa;
  alvo.innerHTML = `<div class="card" style="margin-bottom:16px">
    <label class="form-label" for="colar-texto">Cole a tabela do sistema acadêmico (código, período, situação e, se tiver, nota)</label>
    <div class="colar-arquivo">ou envie o arquivo exportado (.csv):
      <input type="file" id="colar-arquivo" accept=".csv,.txt,text/csv,text/plain" aria-label="Arquivo CSV do histórico" onchange="colarArquivo(this)"/></div>
    <textarea class="form-input" id="colar-texto" rows="7" ${COLAR.erro ? 'aria-invalid="true" aria-describedby="colar-erro"' : ''}
      placeholder="INF110    Programação I    2024/1    8,5    Aprovado">${esc(COLAR.texto)}</textarea>
    ${COLAR.erro ? `<div class="campo-erro" id="colar-erro" role="alert">${esc(COLAR.erro)}</div>` : ''}
    <div class="sim-acoes">
      <button class="btn btn-primary btn-sm" onclick="colarConferir(false)" ${COLAR.ocupado ? 'disabled' : ''}>${COLAR.ocupado ? 'Lendo…' : 'Conferir'}</button>
      ${p?.pode_confirmar ? `<button class="btn btn-primary btn-sm" onclick="colarConferir(true)" ${COLAR.ocupado ? 'disabled' : ''}>Adicionar ${p.totais.reconhecida} ao histórico</button>` : ''}
      <button class="btn btn-ghost btn-sm" onclick="colarFechar()">Cancelar</button>
    </div>
    ${p ? `<p class="sim-texto" role="status" style="margin-top:12px"><b>${esc(p.resumo)}</b> Só as reconhecidas são adicionadas.</p>
      <table class="colar-tabela"><thead><tr><th>Linha</th><th>Disciplina</th><th>Período</th><th>Situação</th><th>Nota</th><th>Resultado</th></tr></thead><tbody>
      ${p.linhas.map(l => `<tr><td>${l.numero}</td><td>${esc(l.disciplina ? l.disciplina.codigo + ' · ' + l.disciplina.nome : l.codigo)}</td>
        <td>${esc(l.periodo_letivo || '–')}</td><td>${esc(l.status_txt || '–')}</td><td>${l.nota ?? '–'}</td>
        <td><span class="badge ${RESULTADO_COLADO[l.resultado].cls}">${RESULTADO_COLADO[l.resultado].rotulo}</span>${l.motivo ? ` <small>${esc(l.motivo)}</small>` : ''}</td></tr>`).join('')}
      </tbody></table>` : ''}
  </div>`;
}
