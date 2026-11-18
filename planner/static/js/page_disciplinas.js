// ═══════════════════════════════════════════════════════
// PAGE: DISCIPLINAS
// ═══════════════════════════════════════════════════════
function disciplinas() {
  const tb = document.getElementById('topbar-actions');
  // O catálogo só muda por importação de CSV (não há edição na tela).
  tb.innerHTML = `<a class="btn btn-primary btn-sm" href="/importar">Atualizar por importação</a>`;

  let _q = '';
  const c = document.getElementById('content');
  c.innerHTML = `
  <div class="card" style="margin-bottom:16px;padding:12px 16px">
    <div class="search-wrap">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <input class="search-input" placeholder="Buscar por nome ou código..." id="disc-search" oninput="renderDiscTable(this.value)"/>
    </div>
  </div>
  <div id="disc-table-wrap"></div>
  `;
  renderDiscTable('');
}

window.renderDiscTable = function(q) {
  const filtered = S.disciplinas.filter(d =>
    !q || d.nome.toLowerCase().includes(q.toLowerCase()) || d.codigo.toLowerCase().includes(q.toLowerCase())
  );
  const wrap = document.getElementById('disc-table-wrap');
  if (!wrap) return;
  wrap.innerHTML = `<div class="card" style="padding:0;overflow:hidden">
    <table style="width:100%;border-collapse:collapse">
      <thead>
        <tr style="background:var(--bg3)">
          ${['Código','Nome','Período','CH','Créditos','Turmas','Pré-req',''].map(h=>
            `<th style="padding:10px 14px;text-align:left;font-size:11px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--border)">${h}</th>`
          ).join('')}
        </tr>
      </thead>
      <tbody>
        ${filtered.map(d => {
          const prereqs = d.prerequisitos||[];
          return `<tr style="border-bottom:1px solid var(--border)" onmouseenter="this.style.background='var(--bg3)'" onmouseleave="this.style.background=''">
            <td style="padding:10px 14px">
              <span style="font-size:12px;font-weight:700;color:${esc(d.cor)}">${esc(d.codigo)}</span>
            </td>
            <td style="padding:10px 14px;font-size:13px;font-weight:500">${esc(d.nome)}</td>
            <td style="padding:10px 14px;font-size:12px;color:var(--text2)">${periodStr(d.periodo)}</td>
            <td style="padding:10px 14px;font-size:12px;color:var(--text2)">${valorOu(d.carga_h, 'h')}</td>
            <td style="padding:10px 14px;font-size:12px;color:var(--text2)">${valorOu(d.creditos)}</td>
            <td style="padding:10px 14px;font-size:11px;color:var(--text2)">
              ${(n => n ? `${n} turma${n>1?'s':''}` : '–')(turmasDaDisciplina(d.id).length)}
            </td>
            <td style="padding:10px 14px">
              ${prereqs.filter(p=>p.tipo==='pre').map(p=>`<span class="tag" style="margin:1px">${esc(p.codigo)}</span>`).join('')||'–'}
            </td>
            <td style="padding:10px 14px"><button class="btn btn-ghost btn-sm" style="font-size:10px" onclick="showDiscDetail(${d.id})">Ver</button></td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>
  </div>`;
};
