"""
Fluxos do app no navegador (Playwright), contra um servidor local com login dev:

    AUTH_PROVEDOR=dev DATABASE_URL=sqlite:///…/ui.db flask --app planner run --port 5077
    python tools/validacao_ui/fluxos.py <raiz do projeto> <pasta das capturas>

Imprime {"falhas": [...], "console": [...]} — as duas listas vazias = tudo certo.
O banco precisa de um curso do usuário dev com um plano (ver `capturar.py`/docs/PROGRESSO.md).
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5077"
RAIZ = Path(sys.argv[1])
SAIDA = Path(sys.argv[2]); SAIDA.mkdir(parents=True, exist_ok=True)
falhas, console = [], []


def checar(cond, msg):
    if not cond:
        falhas.append(msg)


def esperar(page, ms=500):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(ms)


with sync_playwright() as p:
    nav = p.chromium.launch()
    ctx = nav.new_context(viewport={"width": 1366, "height": 900})
    page = ctx.new_page()
    page.on("console", lambda m: m.type == "error" and console.append(m.text))
    page.on("pageerror", lambda e: console.append(f"pageerror: {e}"))
    page.goto(BASE + "/entrar")
    page.evaluate("""async () => fetch('/api/auth/entrar', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({access_token: 'dev:aluno@teste.com'})})""")
    cid = page.evaluate("async () => ((await (await fetch('/api/cursos')).json()).cursos || []).find(c => c.meu)?.id")
    page.evaluate(f"""async () => fetch('/api/cursos/{cid}/preferencias', {{method: 'PUT', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{indisponiveis: [{{dia: 'TER', inicio: '18:00', fim: '23:00', motivo: 'trabalho'}}]}})}})""")
    # plano com um semestre de quadro real e turmas ainda não escolhidas (para ver a escolha automática)
    disc = page.evaluate(f"async () => (await (await fetch('/api/cursos/{cid}/disciplinas')).json()).disciplinas")
    cod = {d["codigo"]: d["id"] for d in disc}
    page.evaluate(f"""async p => fetch('/api/cursos/{cid}/planos', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(p)}})""", {"nome": "Teste automático", "semestres": [
        {"rotulo": "Semestre 1", "periodo_letivo": "2026/1",
         "itens": [{"disciplina_id": cod[c], "turma_id": None} for c in ("MAT140", "MAT131", "INF150")]}]})
    page.goto(f"{BASE}/curso/{cid}")
    esperar(page)

    # ── menu e rota ──
    itens = page.evaluate("[...document.querySelectorAll('.nav-item')].map(n => n.dataset.page)")
    checar(itens[:6] == ["dashboard", "historico", "rotina", "planner", "calendario", "simulador"], f"menu fora de ordem: {itens}")
    page.evaluate("irPara('rotina')"); esperar(page, 400)
    checar(page.inner_text("#page-title") == "Minha rotina", "tela Minha rotina não abriu")
    checar(page.locator("#grade-semanal").count() == 1 and page.locator("#pref-optativas").count() == 1,
           "Minha rotina sem grade ou sem optativas")
    page.screenshot(path=str(SAIDA / "rotina.png"))

    # ── Planejamento: turmas automáticas e troca manual ──
    page.evaluate("const p = Planos.planos().find(x => x.nome === 'Teste automático'); Planos.selecionar(p.id); S.currentPlano = p.id;")
    page.evaluate("irPara('planner')"); esperar(page, 1200)
    auto = page.evaluate("Planos.atual().semestres[0].itens.map(i => [i.turma_id, !!i.turma_auto])")
    checar(all(t and a for t, a in auto), f"turmas não foram escolhidas automaticamente: {auto}")
    checar(page.locator(".turma-origem").first.inner_text().startswith("✓ escolhida pelo Rumo"), "cartão não diz que a turma é automática")
    page.screenshot(path=str(SAIDA / "planner-turmas-automaticas.png"))
    sel = page.locator(".turma-sel").first
    opcoes = sel.locator("option").all_inner_texts()
    if len(opcoes) > 1:
        sel.select_option(index=1); esperar(page, 800)
        checar(not page.evaluate("Planos.atual().semestres[0].itens[0].turma_auto"), "troca manual não ficou fixa")
        page.locator(".toast-acao button").first.click(); esperar(page, 800)

    # ── Planejamento: Sugerir plano (com comparação) ──
    page.evaluate("const p = Planos.planos().find(x => x.nome === 'Plano sugerido') || Planos.planos()[0]; Planos.selecionar(p.id); S.currentPlano = p.id;")
    page.evaluate("irPara('planner')"); esperar(page, 800)
    page.get_by_role("button", name="✨ Sugerir plano").click(); esperar(page, 300)
    checar(page.is_visible("#sug-bloco"), "painel de sugestão não abriu no Planejamento")
    page.evaluate("void simSugerir()"); page.wait_for_timeout(600)
    checar(page.locator("#etapas-sug li").count() == 5, "sem etapas durante a sugestão")
    t0 = time.time()
    page.wait_for_function("SIM.sug.estado !== 'carregando'", timeout=60000)
    page.wait_for_function("SIM.sim.estado !== 'carregando'", timeout=60000)
    print("sugestão levou %.1fs" % (time.time() - t0))
    esperar(page, 400)
    checar(page.locator(".comparacao tbody tr").count() == 7, "comparação Plano atual × Sugestão ausente")
    msg_fim = page.evaluate("SIM.sug.dados.fim_de_curso_mensagem || ''")
    checar("fim do curso" in msg_fim, f"sugestão não explica o TCC no fim: {msg_fim!r}")
    page.evaluate("document.querySelector('.comparacao')?.scrollIntoView()"); page.wait_for_timeout(200)
    page.screenshot(path=str(SAIDA / "planner-sugestao.png"))

    # ── fixar disciplina + optativas na rotina → sugestão respeita, abre espaço no meio, não sai pior ──
    page.evaluate(f"""async () => fetch('/api/cursos/{cid}/preferencias', {{method: 'PUT', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{...S.preferencias, optativas_faltando: 12, juntas_respondida: true}})}}).then(r => r.json()).then(j => S.preferencias = j.preferencias)""")
    page.evaluate(f"cursarEmPeriodo({cod['INF213']})"); page.wait_for_timeout(300)
    page.screenshot(path=str(SAIDA / "fixar-periodo.png"))
    page.select_option("#fixa-periodo", "2028/1")
    page.locator("#modal-box .btn-primary").click(); esperar(page, 600)
    checar(any(f["periodo"] == "2028/1" for f in page.evaluate("S.preferencias.fixas || []")), "fixação não foi guardada")
    page.evaluate("void simSugerir()")
    page.wait_for_function("SIM.sug.estado !== 'carregando'", timeout=60000); esperar(page, 400)
    sug = page.evaluate("SIM.sug.dados")
    onde = {i["disciplina"]["codigo"]: s["periodo"] for s in sug["semestres"] for i in s["itens"]}
    checar(onde.get("INF213") == "2028/1", f"fixação não respeitada: INF213 em {onde.get('INF213')}")
    opt = [s["creditos_optativos"] for s in sug["semestres"]]
    checar(sum(opt) == 12 and opt[-1] == 0, f"optativas fora do meio: {opt}")
    atual = page.evaluate("SIM.sim.dados?.indicadores?.find(x => x.chave === 'formatura')?.valor")
    print("formatura plano atual", atual, "| sugestão", sug["metricas"]["periodo_fim"], "| optativas por semestre", opt)
    page.evaluate("document.querySelector('.sim-reserva')?.scrollIntoView({block:'center'})"); page.wait_for_timeout(200)
    page.screenshot(path=str(SAIDA / "sugestao-optativas-meio.png"))

    # ── Simulador: só avalia, 5 abas, rotina resumida, link para sugerir ──
    page.evaluate("irPara('simulador')"); esperar(page, 5000)
    checar(page.locator("[role=tab]").count() == 5, "Simulador não tem 5 abas")
    checar(page.locator("#aba-sugestao").count() == 0, "a Sugestão ainda está no Simulador")
    checar(page.locator(".sim-rotina").count() == 1 and page.locator(".sim-explica").count() == 1, "Simulador não diz o que avalia")
    page.locator("#aba-geral").focus(); page.keyboard.press("End"); esperar(page, 200)
    checar(page.evaluate("SIM.aba") == "probabilidade", "End não foi para a última aba")
    page.screenshot(path=str(SAIDA / "simulador.png"))

    # ── Histórico: CSV ──
    page.evaluate("irPara('historico')"); esperar(page, 400)
    page.evaluate("colarAbrir()"); page.wait_for_timeout(200)
    csv_path = SAIDA / "historico_teste.csv"
    csv_path.write_text('codigo,disciplina,periodo,ch,nota,situacao\nINF112,Programação II,2026/2,90,"7,5",Aprovado\nXYZ999,Outra,2026/2,60,8,Aprovado\n', encoding="utf-8")
    page.set_input_files("#colar-arquivo", str(csv_path)); esperar(page, 700)
    tot = page.evaluate("COLAR.previa?.totais")
    checar(tot and tot["nao_encontrada"] == 1 and tot["reconhecida"] + tot["duplicada"] == 1, f"prévia do CSV errada: {tot}")
    page.screenshot(path=str(SAIDA / "historico-csv.png"))
    csv_path.unlink()
    ctx.close()
    nav.close()

print(json.dumps({"falhas": falhas, "console": console}, ensure_ascii=False, indent=1))
