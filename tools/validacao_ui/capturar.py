"""Capturas das telas principais (antes/depois da Fase 3): desktop e 390 px, claro e escuro."""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5077"
SAIDA = Path(sys.argv[1])
SAIDA.mkdir(parents=True, exist_ok=True)
erros = []


def entrar(page):
    page.goto(BASE + "/entrar")
    page.evaluate("""async () => fetch('/api/auth/entrar', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({access_token: 'dev:aluno@teste.com'})})""")
    return page.evaluate("async () => ((await (await fetch('/api/cursos')).json()).cursos || []).find(c => c.meu)?.id")


def esperar(page, ms=600):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(ms)


with sync_playwright() as p:
    nav = p.chromium.launch()
    for largura in (1366, 390):
        for tema in ("light", "dark"):
            ctx = nav.new_context(viewport={"width": largura, "height": 900}, color_scheme=tema)
            page = ctx.new_page()
            page.on("console", lambda m, l=largura, t=tema: m.type == "error" and erros.append(f"[{l}/{t}] {m.text}"))
            page.on("pageerror", lambda e, l=largura, t=tema: erros.append(f"[{l}/{t}] pageerror: {e}"))
            cid = entrar(page)
            page.goto(f"{BASE}/curso/{cid}")
            esperar(page)
            s = f"{largura}-{tema}"
            for tela in ("dashboard", "historico", "rotina", "planner", "calendario", "simulador"):
                page.evaluate(f"irPara('{tela}')")
                esperar(page, 5000 if tela == "simulador" else 600)
                # o app rola num contêiner interno: captura a viewport no topo (e o resto em seguida)
                page.screenshot(path=str(SAIDA / f"{tela}-{s}.png"))
            # a sugestão mora no Planejamento ("Sugerir plano")
            page.evaluate("irPara('planner')")
            esperar(page, 800)
            page.evaluate("abrirSugestao()")
            page.evaluate("void simSugerir()")
            page.wait_for_function("SIM.sug.estado !== 'carregando'", timeout=60000)
            esperar(page, 300)
            page.screenshot(path=str(SAIDA / f"planner-sugestao-{s}.png"))
            larg = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            if larg > 2:
                erros.append(f"[{s}] rolagem horizontal de {larg}px")
            ctx.close()
    nav.close()
print(json.dumps(erros, ensure_ascii=False, indent=1))
