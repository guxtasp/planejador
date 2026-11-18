// ═══════════════════════════════════════════════════════
// PLANOS DO ALUNO (Etapa 5B-2)
// Os planos moram no SERVIDOR, por usuário. Aqui ficam só uma cópia de trabalho e
// a fila de gravação; nenhuma regra de negócio (o julgamento é de
// `POST /api/cursos/<id>/plano/analisar`).
//
//   plano    = {id (do servidor), nome, semestres: [semestre]}
//   semestre = {id (só local, serve ao DOM), rotulo, periodo_letivo|null, itens: [{disciplina_id, turma_id|null}]}
//
// Edição: o cliente altera a cópia, a tela reage na hora e o plano INTEIRO é enviado
// (`PUT /planos/<id>`). As gravações saem uma de cada vez e, se o plano mudar de novo
// durante o envio, só a versão mais recente é enviada em seguida.
//
// O que existia no navegador (versão anterior, `localStorage`) é movido para a conta
// uma vez (`migrarDoNavegador`).
// ═══════════════════════════════════════════════════════
const Planos = (() => {
  const URL_BASE = `/api/cursos/${CURSO_ID}/planos`;
  const CHAVE_ATUAL = `planejador:plano-atual:v2:${CURSO_ID}`;   // só preferência: qual plano abrir
  const CHAVE_LEGADA = `planejador:planos:v1:${CURSO_ID}`;       // planos da 4B (migrados e apagados)

  let lista = [];
  let atualId = null;
  let proximoSemestre = 1;
  let carregado = false;
  const pendentes = new Set();   // ids de planos com alteração ainda não enviada
  let gravando = false;

  // ── armazenamento do navegador (nunca derruba a tela) ──────────────────
  const lerChave = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const gravarChave = (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* sem storage: segue sem lembrar */ } };
  const apagarChave = k => { try { localStorage.removeItem(k); } catch (e) { /* idem */ } };

  // ── conversão servidor ⇄ cópia de trabalho ─────────────────────────────
  const novoSemestre = (rotulo, periodo = null, itens = []) =>
    ({id: proximoSemestre++, rotulo, periodo_letivo: periodo, itens});

  const doServidor = p => ({
    id: p.id, nome: p.nome,
    semestres: p.semestres.map(s => novoSemestre(s.rotulo, s.periodo_letivo, s.itens.map(i => ({...i})))),
  });

  const paraServidor = p => ({
    nome: p.nome,
    semestres: p.semestres.map(s => ({rotulo: s.rotulo, periodo_letivo: s.periodo_letivo, itens: s.itens})),
  });

  const atual = () => lista.find(p => p.id === atualId) || null;
  const semestre = id => atual()?.semestres.find(s => s.id === id) || null;

  // ── gravação ───────────────────────────────────────────────────────────
  async function drenar() {
    if (gravando) return;
    gravando = true;
    try {
      while (pendentes.size) {
        const id = pendentes.values().next().value;
        pendentes.delete(id);
        const plano = lista.find(p => p.id === id);
        if (!plano) continue;                      // excluído enquanto esperava
        const r = await PUT(`${URL_BASE}/${id}`, paraServidor(plano));
        if (!r.ok) {
          toast(r.erro || 'Não foi possível salvar o plano.', 'error');
          if (r.status !== 404 && r.status !== 422) pendentes.add(id);   // erro de rede: tenta de novo na próxima alteração
          break;
        }
      }
    } finally { gravando = false; }
  }

  function marcar(plano) {
    pendentes.add(plano.id);
    drenar();
  }

  const editar = (fn) => { const p = atual(); if (!p) return; fn(p); marcar(p); };

  return {
    carregado: () => carregado,

    async carregar() {
      const r = await GET(URL_BASE);
      if (!r.ok) { toast(r.erro || 'Não foi possível carregar seus planos.', 'error'); return false; }
      lista = r.planos.map(doServidor);
      const lembrado = Number(lerChave(CHAVE_ATUAL));
      atualId = lista.find(p => p.id === lembrado)?.id ?? lista[0]?.id ?? null;
      carregado = true;
      return true;
    },

    // Move para a conta os planos que a versão anterior guardava neste navegador.
    // Itens que já não batem com o curso (reimportação) são descartados antes de enviar.
    async migrarDoNavegador() {
      let antigos;
      try { antigos = JSON.parse(lerChave(CHAVE_LEGADA) || 'null'); } catch (e) { antigos = null; }
      if (!antigos || !Array.isArray(antigos.planos) || !antigos.planos.length) { apagarChave(CHAVE_LEGADA); return 0; }

      const discIds = new Set(S.disciplinas.map(d => d.id));
      const turmaPorId = new Map(S.turmas.map(t => [t.id, t]));
      let movidos = 0;
      for (const antigo of [...antigos.planos]) {
        const vistas = new Set();
        const corpo = {
          nome: String(antigo.nome || 'Plano').slice(0, 200),
          semestres: (antigo.semestres || []).slice(0, 20).map((s, i) => ({
            rotulo: String(s.rotulo || `Semestre ${i + 1}`).slice(0, 50),
            periodo_letivo: s.periodo_letivo || null,
            itens: (s.itens || []).filter(it => discIds.has(it.disciplina_id) && !vistas.has(it.disciplina_id))
              .map(it => {
                vistas.add(it.disciplina_id);
                const t = turmaPorId.get(it.turma_id);
                const turmaValida = t && t.disciplina_id === it.disciplina_id && s.periodo_letivo && t.periodo_letivo === s.periodo_letivo;
                return {disciplina_id: it.disciplina_id, turma_id: turmaValida ? t.id : null};
              }),
          })),
        };
        const r = await POST(URL_BASE, corpo);
        if (!r.ok) { toast(r.erro || 'Não foi possível mover um plano deste navegador para a sua conta.', 'warn'); break; }
        lista.push(doServidor(r.plano));
        movidos++;
        antigos.planos = antigos.planos.filter(p => p !== antigo && p.id !== antigo.id);
        if (antigos.planos.length) gravarChave(CHAVE_LEGADA, JSON.stringify(antigos)); else apagarChave(CHAVE_LEGADA);
      }
      if (movidos) {
        if (atualId == null) atualId = lista[0]?.id ?? null;
        toast(movidos === 1 ? 'Seu plano deste navegador foi salvo na conta.' : `${movidos} planos deste navegador foram salvos na conta.`, 'success');
      }
      return movidos;
    },

    planos: () => lista,
    atual,
    atualId: () => atualId,
    selecionar(id) { atualId = id; gravarChave(CHAVE_ATUAL, String(id)); },

    async criar(nome, numSemestres) {
      const corpo = {nome, semestres: Array.from({length: numSemestres}, (_, i) => ({rotulo: `Semestre ${i + 1}`, periodo_letivo: null, itens: []}))};
      const r = await POST(URL_BASE, corpo);
      if (!r.ok) { toast(r.erro || 'Não foi possível criar o plano.', 'error'); return null; }
      const plano = doServidor(r.plano);
      lista.push(plano);
      this.selecionar(plano.id);
      return plano;
    },

    async excluir(id) {
      const r = await DEL(`${URL_BASE}/${id}`);
      if (!r.ok && r.status !== 404) { toast(r.erro || 'Não foi possível excluir o plano.', 'error'); return false; }
      pendentes.delete(id);
      lista = lista.filter(p => p.id !== id);
      if (atualId === id) { atualId = lista[0]?.id ?? null; if (atualId != null) gravarChave(CHAVE_ATUAL, String(atualId)); }
      return true;
    },

    adicionarSemestre() {
      editar(p => p.semestres.push(novoSemestre(`Semestre ${p.semestres.length + 1}`)));
    },

    definirPeriodo(semId, periodo) {
      editar(() => {
        const s = semestre(semId); if (!s) return;
        s.periodo_letivo = periodo || null;
        s.itens.forEach(i => { i.turma_id = null; });   // turmas pertencem a um período
      });
    },

    // Mover = tirar dos outros semestres do plano e pôr neste. Disciplina só aparece uma vez.
    adicionar(semId, discId) {
      editar(p => {
        const alvo = semestre(semId); if (!alvo) return;
        p.semestres.forEach(s => { s.itens = s.itens.filter(i => i.disciplina_id !== discId); });
        alvo.itens.push({disciplina_id: discId, turma_id: null});
      });
    },

    remover(semId, discId) {
      editar(() => { const s = semestre(semId); if (s) s.itens = s.itens.filter(i => i.disciplina_id !== discId); });
    },

    definirTurma(semId, discId, turmaId) {
      editar(() => {
        const item = semestre(semId)?.itens.find(i => i.disciplina_id === discId);
        if (item) { item.turma_id = turmaId || null; if (item.turma_id) delete item.encontros_livres; }   // turma OU horários próprios
      });
    },

    // Horários definidos pelo aluno (não dependem de quadro importado nem de período letivo).
    // Substitui a turma escolhida; lista vazia volta ao estado "sem horário".
    definirEncontros(semId, discId, encontros) {
      editar(() => {
        const item = semestre(semId)?.itens.find(i => i.disciplina_id === discId);
        if (!item) return;
        if (encontros.length) { item.encontros_livres = encontros; item.turma_id = null; }
        else delete item.encontros_livres;
      });
    },

    // Formato esperado pela análise do servidor.
    paraAnalise() {
      const p = atual();
      return {semestres: (p?.semestres || []).map(s => ({periodo_letivo: s.periodo_letivo, itens: s.itens}))};
    },
  };
})();
