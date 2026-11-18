"""
Planejador Acadêmico - Sistema de planejamento de matrícula com SQLite local
Run: python app.py  →  Acesse http://localhost:5000
"""
import json
import sqlite3
import webbrowser
import threading
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
from pathlib import Path

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

DB_PATH = Path.home() / ".planner_academico" / "database.db"
DB_PATH.parent.mkdir(exist_ok=True)

# ─── DATABASE ────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS disciplinas (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo     TEXT UNIQUE NOT NULL,
            nome       TEXT NOT NULL,
            carga_h    INTEGER NOT NULL,
            creditos   INTEGER NOT NULL,
            periodo    INTEGER NOT NULL,
            cor        TEXT DEFAULT '#3b82f6'
        );

        CREATE TABLE IF NOT EXISTS horarios (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            disciplina_id INTEGER NOT NULL REFERENCES disciplinas(id) ON DELETE CASCADE,
            dia          TEXT NOT NULL,
            inicio       TEXT NOT NULL,
            fim          TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS prerequisitos (
            disciplina_id  INTEGER NOT NULL REFERENCES disciplinas(id) ON DELETE CASCADE,
            requisito_id   INTEGER NOT NULL REFERENCES disciplinas(id) ON DELETE CASCADE,
            tipo           TEXT NOT NULL CHECK(tipo IN ('pre','co')),
            PRIMARY KEY (disciplina_id, requisito_id, tipo)
        );

        CREATE TABLE IF NOT EXISTS historico (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            disciplina_id INTEGER NOT NULL REFERENCES disciplinas(id) ON DELETE CASCADE,
            status        TEXT NOT NULL CHECK(status IN ('aprovado','reprovado','cursando')),
            periodo_letivo TEXT,
            nota          REAL
        );

        CREATE TABLE IF NOT EXISTS planos (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            nome       TEXT NOT NULL,
            criado_em  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS plano_semestres (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            plano_id  INTEGER NOT NULL REFERENCES planos(id) ON DELETE CASCADE,
            semestre  INTEGER NOT NULL,
            label     TEXT
        );

        CREATE TABLE IF NOT EXISTS plano_disciplinas (
            semestre_id   INTEGER NOT NULL REFERENCES plano_semestres(id) ON DELETE CASCADE,
            disciplina_id INTEGER NOT NULL REFERENCES disciplinas(id) ON DELETE CASCADE,
            PRIMARY KEY (semestre_id, disciplina_id)
        );
        """)
    _seed_if_empty()


def _seed_if_empty():
    with get_db() as conn:
        if conn.execute("SELECT COUNT(*) FROM disciplinas").fetchone()[0] > 0:
            return
        
        # Currículo de Ciência da Computação (Matriz 2023) + Optativas (26/1 e 26/2)
        disciplinas = [
            # 1º período
            ("INF110","Programação I",90,6,1,"#3b82f6"),
            ("INF150","Introdução aos Sistemas Lógicos",30,2,1,"#8b5cf6"),
            ("INF191","Introdução à Ciência da Computação",30,2,1,"#10b981"),
            ("MAT131","Introdução à Álgebra",60,4,1,"#f59e0b"),
            ("MAT140","Cálculo I",60,4,1,"#f59e0b"),

            # 2º período
            ("EST105","Iniciação à Estatística",60,4,2,"#f59e0b"),
            ("INF112","Programação II",90,6,2,"#3b82f6"),
            ("LET215","Inglês I",60,4,2,"#06b6d4"),
            ("MAT135","Geometria Analítica e Álgebra Linear",90,6,2,"#f59e0b"),
            ("MAT147","Cálculo II",60,4,2,"#f59e0b"),

            # 3º período
            ("INF130","Teoria da Computação",60,4,3,"#6366f1"),
            ("INF213","Estruturas de Dados",90,6,3,"#3b82f6"),
            ("INF230","Matemática Discreta",60,4,3,"#6366f1"),
            ("INF280","Pesquisa Operacional I",60,4,3,"#84cc16"),
            ("MAT241","Cálculo III",60,4,3,"#f59e0b"),

            # 4º período
            ("INF220","Banco de Dados I",60,4,4,"#06b6d4"),
            ("INF222","Computação Experimental",30,2,4,"#64748b"),
            ("INF250","Organização de Computadores",60,4,4,"#8b5cf6"),
            ("INF310","Programação Concorrente e Distribuída",60,4,4,"#14b8a6"),
            ("INF330","Teoria e Modelos de Grafos",60,4,4,"#6366f1"),
            ("INF332","Projeto e Análise de Algoritmos",60,4,4,"#6366f1"),

            # 5º período
            ("INF221","Engenharia de Software I",60,4,5,"#84cc16"),
            ("INF331","Linguagens Formais e Autômatos",60,4,5,"#6366f1"),
            ("INF420","Inteligência Artificial I",60,4,5,"#a855f7"),
            ("INF450","Arquitetura de Computadores",60,4,5,"#8b5cf6"),
            ("INF452","Redes de Computadores",60,4,5,"#ec4899"),
            ("MAT271","Cálculo Numérico",60,4,5,"#f59e0b"),

            # 6º período
            ("ERU324","Metodologia de Pesquisa",60,4,6,"#64748b"),
            ("INF321","Projeto e Desenvolvimento de Sistemas para a Web",60,4,6,"#84cc16"),
            ("INF340","Linguagens de Programação",60,4,6,"#3b82f6"),
            ("INF421","Sistemas de Informação",60,4,6,"#06b6d4"),
            ("INF441","Construção de Compiladores",60,4,6,"#6366f1"),
            ("INF451","Sistemas Operacionais",60,4,6,"#14b8a6"),

            # 7º período
            ("INF497","Projeto Final de Curso",0,0,7,"#64748b"),
            ("INF498","Seminário I",30,2,7,"#64748b"),

            # 8º período
            ("INF499","Seminário II",30,2,8,"#64748b"),

            # Optativas Oferecidas (Agrupadas no "9º Período" / Laranja)
            ("INF115","Programação Funcional",60,4,9,"#f97316"),
            ("INF282","Pesquisa Operacional III",60,4,9,"#f97316"),
            ("INF311","Programação para Dispositivos Móveis",60,4,9,"#f97316"),
            ("INF323","Engenharia de Software II",60,4,9,"#f97316"),
            ("INF333","Programação Competitiva",60,4,9,"#f97316"),
            ("INF390","Computação Gráfica",60,4,9,"#f97316"),
            ("INF394","Processamento Digital de Imagens",60,4,9,"#f97316"),
            ("INF425","Ciência de Dados",60,4,9,"#f97316"),
            ("INF442","Padrões de Projeto",60,4,9,"#f97316"),
            ("INF491","Tóp. Esp.: Comp. Musical / IHC",60,4,9,"#f97316"),
            ("INF492","Tóp. Esp.: RNC / Visão Computac.",60,4,9,"#f97316"),
            ("INF493","Tóp. Esp.: Introdução à Cibersegurança",60,4,9,"#f97316"),
            ("INF494","Tóp. Esp.: Process. Alto Desemp. com GPUs",60,4,9,"#f97316"),
        ]
        conn.executemany(
            "INSERT INTO disciplinas(codigo,nome,carga_h,creditos,periodo,cor) VALUES(?,?,?,?,?,?)",
            disciplinas
        )

        # Mapeamento de Horários combinando 2026/1 (Ímpares) e 2026/2 (Pares)
        horarios = [
            # --- 1º período (2026/1) ---
            ("INF110", [("SEG", "16:00", "18:00"), ("QUI", "14:00", "16:00"), ("SEX", "14:00", "16:00")]),
            ("INF150", [("QUA", "14:00", "16:00")]),
            ("INF191", [("TER", "16:00", "18:00")]),
            ("MAT131", [("TER", "14:00", "16:00"), ("QUI", "16:00", "18:00")]),
            ("MAT140", [("SEG", "14:00", "16:00"), ("QUA", "16:00", "18:00")]),

            # --- 2º período (2026/2) ---
            ("MAT135", [("SEG", "08:00", "10:00"), ("QUA", "10:00", "12:00"), ("QUI", "10:00", "12:00")]),
            ("INF112", [("SEG", "10:00", "12:00"), ("TER", "08:00", "10:00"), ("QUI", "08:00", "10:00")]),
            ("EST105", [("SEG", "16:00", "18:00"), ("QUI", "14:00", "16:00")]),
            ("LET215", [("QUA", "14:00", "16:00"), ("QUI", "16:00", "18:00")]),
            ("MAT147", [("QUA", "08:00", "10:00"), ("SEX", "10:00", "12:00")]),

            # --- 3º período (2026/1) ---
            ("INF130", [("TER", "08:00", "10:00"), ("QUI", "10:00", "12:00")]),
            ("INF213", [("SEG", "10:00", "12:00"), ("QUA", "14:00", "16:00"), ("QUI", "08:00", "10:00")]),
            ("INF230", [("QUA", "08:00", "10:00"), ("SEX", "10:00", "12:00")]),
            ("INF280", [("TER", "10:00", "12:00"), ("SEX", "08:00", "10:00")]),
            ("MAT241", [("SEG", "08:00", "10:00"), ("QUA", "10:00", "12:00")]),

            # --- 4º período (2026/2) ---
            ("INF220", [("SEG", "14:00", "16:00"), ("QUA", "16:00", "18:00")]),
            ("INF222", [("QUA", "14:00", "16:00")]),
            ("INF250", [("TER", "14:00", "16:00"), ("QUI", "16:00", "18:00")]),
            ("INF310", [("TER", "10:00", "12:00"), ("QUI", "10:00", "12:00")]),
            ("INF330", [("TER", "16:00", "18:00"), ("SEX", "14:00", "16:00")]),
            ("INF332", [("SEG", "16:00", "18:00"), ("QUI", "14:00", "16:00")]),

            # --- 5º período (2026/1) ---
            ("INF221", [("SEG", "14:00", "16:00"), ("QUA", "16:00", "18:00")]),
            ("INF331", [("TER", "14:00", "16:00"), ("QUI", "16:00", "18:00")]),
            ("INF420", [("TER", "16:00", "18:00"), ("SEX", "14:00", "16:00")]),
            ("INF450", [("SEG", "16:00", "18:00"), ("QUI", "14:00", "16:00")]),
            ("INF452", [("QUA", "14:00", "16:00"), ("SEX", "16:00", "18:00")]),
            ("MAT271", [("TER", "08:00", "10:00"), ("QUI", "10:00", "12:00")]),

            # --- 6º período (2026/2) ---
            ("ERU324", [("TER", "16:00", "18:00"), ("QUI", "08:00", "10:00")]),
            ("INF321", [("SEG", "10:00", "12:00"), ("QUI", "14:00", "16:00")]),
            ("INF340", [("QUA", "08:00", "10:00"), ("SEX", "10:00", "12:00")]),
            ("INF421", [("TER", "10:00", "12:00"), ("SEX", "08:00", "10:00")]),
            ("INF441", [("SEG", "08:00", "10:00"), ("QUA", "10:00", "12:00")]),
            ("INF451", [("TER", "08:00", "10:00"), ("QUI", "10:00", "12:00")]),

            # --- 7º e 8º período (Seminários) ---
            ("INF498", [("QUA", "10:00", "12:00")]),
            ("INF499", [("QUA", "10:00", "12:00")]),

            # --- Optativas ---
            ("INF115", [("QUA", "14:00", "16:00"), ("SEX", "14:00", "16:00")]),
            ("INF282", [("TER", "14:00", "16:00"), ("QUI", "14:00", "16:00")]),
            ("INF311", [("SEG", "10:00", "12:00"), ("QUA", "08:00", "10:00")]),
            ("INF323", [("SEG", "14:00", "16:00"), ("QUA", "16:00", "18:00")]),
            ("INF333", [("TER", "10:00", "12:00"), ("QUI", "16:00", "18:00")]),
            ("INF390", [("SEG", "16:00", "18:00"), ("QUI", "14:00", "16:00")]),
            ("INF394", [("SEG", "14:00", "16:00"), ("QUA", "16:00", "18:00")]),
            ("INF425", [("SEG", "16:00", "18:00"), ("QUI", "14:00", "16:00")]),
            ("INF442", [("TER", "16:00", "18:00"), ("SEX", "14:00", "16:00")]),
            ("INF491", [("QUI", "08:00", "10:00"), ("SEX", "10:00", "12:00")]),
            ("INF492", [("TER", "08:00", "10:00"), ("QUI", "10:00", "12:00")]),
            ("INF493", [("TER", "08:00", "10:00"), ("QUI", "10:00", "12:00")]),
            ("INF494", [("SEG", "18:30", "20:30"), ("QUA", "18:30", "20:30")]),
        ]
        
        for cod, slots in horarios:
            disc_id = conn.execute("SELECT id FROM disciplinas WHERE codigo=?", (cod,)).fetchone()
            if disc_id:
                # Limpa horários antigos caso existam para a mesma disciplina (evita duplicatas ao rodar de novo)
                conn.execute("DELETE FROM horarios WHERE disciplina_id=?", (disc_id[0],))
                for dia, ini, fim in slots:
                    conn.execute(
                        "INSERT INTO horarios(disciplina_id,dia,inicio,fim) VALUES(?,?,?,?)",
                        (disc_id[0], dia, ini, fim)
                    )

        # Pré-requisitos
        prereqs = [
            ("EST105", "MAT140", "pre"),
            ("INF112", "INF110", "pre"),
            ("MAT147", "MAT140", "pre"),
            ("INF130", "MAT131", "pre"),
            ("INF213", "INF112", "pre"),
            ("INF230", "MAT131", "co"),
            ("INF280", "INF110", "pre"),
            ("INF280", "MAT135", "pre"),
            ("MAT241", "MAT135", "pre"),
            ("MAT241", "MAT140", "pre"),
            ("INF220", "INF213", "pre"),
            ("INF222", "EST105", "pre"),
            ("INF250", "INF150", "pre"),
            ("INF250", "INF110", "pre"),
            ("INF310", "INF213", "pre"),
            ("INF330", "INF213", "pre"),
            ("INF332", "INF213", "pre"),
            ("INF332", "INF230", "pre"),
            ("INF221", "INF220", "pre"),
            ("INF331", "MAT131", "pre"),
            ("INF420", "INF213", "pre"),
            ("INF420", "MAT135", "pre"),
            ("INF420", "MAT241", "pre"),
            ("INF450", "INF250", "pre"),
            ("INF452", "INF250", "pre"),
            ("MAT271", "MAT135", "pre"),
            ("MAT271", "MAT147", "pre"),
            ("MAT271", "INF110", "pre"),
            ("INF321", "INF221", "pre"),
            ("INF321", "INF452", "pre"),
            ("INF340", "INF112", "pre"),
            ("INF421", "INF221", "pre"),
            ("INF441", "INF250", "pre"),
            ("INF441", "INF331", "pre"),
            ("INF451", "INF310", "pre"),
            ("INF497", "INF221", "pre"),
            ("INF497", "ERU324", "co"),
            ("INF498", "INF497", "co"),
            ("INF499", "INF497", "co"),
            ("INF499", "INF498", "pre"),
            
            # Requisitos Comuns para Optativas
            ("INF282", "INF280", "pre"),
            ("INF323", "INF221", "pre"),
            ("INF390", "INF213", "pre"),
            ("INF390", "MAT135", "pre"),
            ("INF394", "INF213", "pre"),
            ("INF442", "INF213", "pre"),
        ]
        
        for disc, req, tipo in prereqs:
            disc_id = conn.execute("SELECT id FROM disciplinas WHERE codigo=?", (disc,)).fetchone()
            req_id = conn.execute("SELECT id FROM disciplinas WHERE codigo=?", (req,)).fetchone()
            if disc_id and req_id:
                conn.execute(
                    "INSERT OR IGNORE INTO prerequisitos(disciplina_id, requisito_id, tipo) VALUES(?,?,?)",
                    (disc_id[0], req_id[0], tipo)
                )

        # Histórico de exemplo (aprovado nos primeiros 2 períodos)
        aprovados = ["MAT001","ALG001","INT001","PRG001","ELE001","MAT002","MAT003","PRG002","FIS001","ARQ001"]
        for cod in aprovados:
            disc = conn.execute("SELECT id FROM disciplinas WHERE codigo=?", (cod,)).fetchone()
            if disc:
                conn.execute(
                    "INSERT INTO historico(disciplina_id,status,periodo_letivo,nota) VALUES(?,?,?,?)",
                    (disc[0], "aprovado", "2023.1", 7.5)
                )

        # Plano padrão
        conn.execute("INSERT INTO planos(nome) VALUES('Meu Plano Principal')")
        plano_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for s in range(1, 5):
            conn.execute(
                "INSERT INTO plano_semestres(plano_id,semestre,label) VALUES(?,?,?)",
                (plano_id, s, f"Semestre {s}")
            )


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def row_to_dict(row):
    return dict(row) if row else None


def rows_to_list(rows):
    return [dict(r) for r in rows]


def get_aprovados():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT disciplina_id FROM historico WHERE status='aprovado'"
        ).fetchall()
        return {r[0] for r in rows}


def get_cursando():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT disciplina_id FROM historico WHERE status='cursando'"
        ).fetchall()
        return {r[0] for r in rows}


def check_prereqs(disc_id, aprovados_ids, cursando_ids=None):
    """Returns (ok, missing_pre, missing_co)"""
    cursando_ids = cursando_ids or set()
    with get_db() as conn:
        reqs = conn.execute(
            """SELECT p.requisito_id, p.tipo, d.nome, d.codigo
               FROM prerequisitos p JOIN disciplinas d ON d.id=p.requisito_id
               WHERE p.disciplina_id=?""",
            (disc_id,)
        ).fetchall()
    missing_pre, missing_co = [], []
    for r in reqs:
        if r["tipo"] == "pre" and r["requisito_id"] not in aprovados_ids:
            missing_pre.append({"id": r["requisito_id"], "nome": r["nome"], "codigo": r["codigo"]})
        if r["tipo"] == "co" and r["requisito_id"] not in (aprovados_ids | cursando_ids):
            missing_co.append({"id": r["requisito_id"], "nome": r["nome"], "codigo": r["codigo"]})
    return (len(missing_pre) == 0 and len(missing_co) == 0), missing_pre, missing_co


def get_disc_horarios(disc_id):
    with get_db() as conn:
        return rows_to_list(conn.execute(
            "SELECT dia, inicio, fim FROM horarios WHERE disciplina_id=?", (disc_id,)
        ).fetchall())


def check_horario_conflict(disc_id, other_ids):
    """Returns list of conflicts"""
    h1 = get_disc_horarios(disc_id)
    conflicts = []
    for oid in other_ids:
        if oid == disc_id:
            continue
        h2 = get_disc_horarios(oid)
        for a in h1:
            for b in h2:
                if a["dia"] == b["dia"]:
                    a_ini = a["inicio"]; a_fim = a["fim"]
                    b_ini = b["inicio"]; b_fim = b["fim"]
                    if a_ini < b_fim and a_fim > b_ini:
                        with get_db() as conn:
                            oname = conn.execute(
                                "SELECT nome, codigo FROM disciplinas WHERE id=?", (oid,)
                            ).fetchone()
                        conflicts.append({
                            "com_id": oid,
                            "com_nome": oname["nome"],
                            "com_codigo": oname["codigo"],
                            "dia": a["dia"],
                            "horario": f"{a_ini}–{a_fim} conflita com {b_ini}–{b_fim}"
                        })
    return conflicts


# ─── API ROUTES ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── Disciplinas ──
@app.route("/api/disciplinas", methods=["GET"])
def get_disciplinas():
    with get_db() as conn:
        discs = rows_to_list(conn.execute(
            "SELECT * FROM disciplinas ORDER BY periodo, nome"
        ).fetchall())
        for d in discs:
            d["horarios"] = rows_to_list(conn.execute(
                "SELECT dia,inicio,fim FROM horarios WHERE disciplina_id=?", (d["id"],)
            ).fetchall())
            d["prerequisitos"] = rows_to_list(conn.execute(
                """SELECT d2.id, d2.codigo, d2.nome, p.tipo
                   FROM prerequisitos p JOIN disciplinas d2 ON d2.id=p.requisito_id
                   WHERE p.disciplina_id=?""", (d["id"],)
            ).fetchall())
    return jsonify(discs)


@app.route("/api/disciplinas", methods=["POST"])
def create_disciplina():
    data = request.json
    with get_db() as conn:
        conn.execute(
            "INSERT INTO disciplinas(codigo,nome,carga_h,creditos,periodo,cor) VALUES(?,?,?,?,?,?)",
            (data["codigo"], data["nome"], data["carga_h"], data["creditos"],
             data["periodo"], data.get("cor", "#3b82f6"))
        )
        disc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for h in data.get("horarios", []):
            conn.execute(
                "INSERT INTO horarios(disciplina_id,dia,inicio,fim) VALUES(?,?,?,?)",
                (disc_id, h["dia"], h["inicio"], h["fim"])
            )
        for p in data.get("prerequisitos", []):
            conn.execute(
                "INSERT OR IGNORE INTO prerequisitos(disciplina_id,requisito_id,tipo) VALUES(?,?,?)",
                (disc_id, p["id"], p["tipo"])
            )
    return jsonify({"ok": True, "id": disc_id})


@app.route("/api/disciplinas/<int:disc_id>", methods=["PUT"])
def update_disciplina(disc_id):
    data = request.json
    with get_db() as conn:
        conn.execute(
            "UPDATE disciplinas SET codigo=?,nome=?,carga_h=?,creditos=?,periodo=?,cor=? WHERE id=?",
            (data["codigo"], data["nome"], data["carga_h"], data["creditos"],
             data["periodo"], data.get("cor", "#3b82f6"), disc_id)
        )
        conn.execute("DELETE FROM horarios WHERE disciplina_id=?", (disc_id,))
        for h in data.get("horarios", []):
            conn.execute(
                "INSERT INTO horarios(disciplina_id,dia,inicio,fim) VALUES(?,?,?,?)",
                (disc_id, h["dia"], h["inicio"], h["fim"])
            )
        conn.execute("DELETE FROM prerequisitos WHERE disciplina_id=?", (disc_id,))
        for p in data.get("prerequisitos", []):
            conn.execute(
                "INSERT OR IGNORE INTO prerequisitos(disciplina_id,requisito_id,tipo) VALUES(?,?,?)",
                (disc_id, p["id"], p["tipo"])
            )
    return jsonify({"ok": True})


@app.route("/api/disciplinas/<int:disc_id>", methods=["DELETE"])
def delete_disciplina(disc_id):
    with get_db() as conn:
        conn.execute("DELETE FROM disciplinas WHERE id=?", (disc_id,))
    return jsonify({"ok": True})


# ── Histórico ──
@app.route("/api/historico", methods=["GET"])
def get_historico():
    with get_db() as conn:
        rows = rows_to_list(conn.execute(
            """SELECT h.*, d.nome, d.codigo, d.creditos, d.periodo
               FROM historico h JOIN disciplinas d ON d.id=h.disciplina_id
               ORDER BY h.id""").fetchall())
    return jsonify(rows)


@app.route("/api/historico", methods=["POST"])
def add_historico():
    data = request.json
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM historico WHERE disciplina_id=?", (data["disciplina_id"],)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE historico SET status=?,periodo_letivo=?,nota=? WHERE disciplina_id=?",
                (data["status"], data.get("periodo_letivo"), data.get("nota"), data["disciplina_id"])
            )
        else:
            conn.execute(
                "INSERT INTO historico(disciplina_id,status,periodo_letivo,nota) VALUES(?,?,?,?)",
                (data["disciplina_id"], data["status"], data.get("periodo_letivo"), data.get("nota"))
            )
    return jsonify({"ok": True})


@app.route("/api/historico/<int:hist_id>", methods=["DELETE"])
def del_historico(hist_id):
    with get_db() as conn:
        conn.execute("DELETE FROM historico WHERE id=?", (hist_id,))
    return jsonify({"ok": True})


# ── Planos ──
@app.route("/api/planos", methods=["GET"])
def get_planos():
    with get_db() as conn:
        planos = rows_to_list(conn.execute("SELECT * FROM planos ORDER BY id").fetchall())
        for p in planos:
            sems = rows_to_list(conn.execute(
                "SELECT * FROM plano_semestres WHERE plano_id=? ORDER BY semestre",
                (p["id"],)
            ).fetchall())
            for s in sems:
                discs = rows_to_list(conn.execute(
                    """SELECT d.id, d.codigo, d.nome, d.carga_h, d.creditos, d.periodo, d.cor
                       FROM plano_disciplinas pd JOIN disciplinas d ON d.id=pd.disciplina_id
                       WHERE pd.semestre_id=?""",
                    (s["id"],)
                ).fetchall())
                for d in discs:
                    d["horarios"] = rows_to_list(conn.execute(
                        "SELECT dia,inicio,fim FROM horarios WHERE disciplina_id=?", (d["id"],)
                    ).fetchall())
                s["disciplinas"] = discs
            p["semestres"] = sems
    return jsonify(planos)


@app.route("/api/planos", methods=["POST"])
def create_plano():
    data = request.json
    with get_db() as conn:
        conn.execute("INSERT INTO planos(nome) VALUES(?)", (data["nome"],))
        plano_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for i in range(1, data.get("num_semestres", 4) + 1):
            conn.execute(
                "INSERT INTO plano_semestres(plano_id,semestre,label) VALUES(?,?,?)",
                (plano_id, i, f"Semestre {i}")
            )
    return jsonify({"ok": True, "id": plano_id})


@app.route("/api/planos/<int:plano_id>", methods=["DELETE"])
def delete_plano(plano_id):
    with get_db() as conn:
        conn.execute("DELETE FROM planos WHERE id=?", (plano_id,))
    return jsonify({"ok": True})


@app.route("/api/planos/<int:plano_id>/semestres", methods=["POST"])
def add_semestre(plano_id):
    with get_db() as conn:
        max_s = conn.execute(
            "SELECT COALESCE(MAX(semestre),0) FROM plano_semestres WHERE plano_id=?", (plano_id,)
        ).fetchone()[0]
        new_s = max_s + 1
        conn.execute(
            "INSERT INTO plano_semestres(plano_id,semestre,label) VALUES(?,?,?)",
            (plano_id, new_s, f"Semestre {new_s}")
        )
        sem_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return jsonify({"ok": True, "id": sem_id, "semestre": new_s})


@app.route("/api/semestres/<int:sem_id>/disciplinas", methods=["POST"])
def add_disc_plano(sem_id):
    data = request.json
    disc_id = data["disciplina_id"]

    aprovados = get_aprovados()
    cursando = get_cursando()

    # Pegar outras disciplinas já no semestre para checar conflito
    with get_db() as conn:
        others = [r[0] for r in conn.execute(
            "SELECT disciplina_id FROM plano_disciplinas WHERE semestre_id=?", (sem_id,)
        ).fetchall()]

    ok_req, missing_pre, missing_co = check_prereqs(disc_id, aprovados, cursando)
    conflicts = check_horario_conflict(disc_id, others)

    # Ainda insere mas retorna avisos
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO plano_disciplinas(semestre_id,disciplina_id) VALUES(?,?)",
            (sem_id, disc_id)
        )

    return jsonify({
        "ok": True,
        "avisos": {
            "prereqs_pendentes": missing_pre,
            "coreqs_pendentes": missing_co,
            "conflitos_horario": conflicts
        }
    })


@app.route("/api/semestres/<int:sem_id>/disciplinas/<int:disc_id>", methods=["DELETE"])
def rem_disc_plano(sem_id, disc_id):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM plano_disciplinas WHERE semestre_id=? AND disciplina_id=?",
            (sem_id, disc_id)
        )
    return jsonify({"ok": True})


# ── Assistente de progressão ──
@app.route("/api/assistente", methods=["GET"])
def assistente():
    aprovados = get_aprovados()
    cursando = get_cursando()
    combinados = aprovados | cursando

    with get_db() as conn:
        todas = rows_to_list(conn.execute("SELECT * FROM disciplinas").fetchall())
        total_creditos = conn.execute("SELECT SUM(creditos) FROM disciplinas").fetchone()[0] or 0
        creditos_aprovados = conn.execute(
            """SELECT COALESCE(SUM(d.creditos),0)
               FROM historico h JOIN disciplinas d ON d.id=h.disciplina_id
               WHERE h.status='aprovado'"""
        ).fetchone()[0]

    elegiveis, bloqueadas, concluidas, em_andamento = [], [], [], []

    for d in todas:
        did = d["id"]
        if did in aprovados:
            concluidas.append(d)
            continue
        if did in cursando:
            em_andamento.append(d)
            continue

        ok, mp, mc = check_prereqs(did, aprovados, cursando)
        motivos = []
        for x in mp:
            motivos.append(f"Pré-req pendente: {x['codigo']} - {x['nome']}")
        for x in mc:
            motivos.append(f"Correq pendente: {x['codigo']} - {x['nome']}")

        if ok:
            elegiveis.append(d)
        else:
            d["bloqueio_motivos"] = motivos
            bloqueadas.append(d)

    pct = round((creditos_aprovados / total_creditos * 100) if total_creditos else 0, 1)
    creditos_restantes = total_creditos - creditos_aprovados

    # Estimativa: média de 20 créditos/semestre
    media_cred_sem = 20
    sems_restantes = max(0, -(-creditos_restantes // media_cred_sem))

    return jsonify({
        "elegiveis": elegiveis,
        "bloqueadas": bloqueadas,
        "concluidas": concluidas,
        "em_andamento": em_andamento,
        "stats": {
            "total_creditos": total_creditos,
            "creditos_aprovados": creditos_aprovados,
            "creditos_restantes": creditos_restantes,
            "percentual_concluido": pct,
            "semestres_restantes_estimado": sems_restantes,
            "total_disciplinas": len(todas),
            "disciplinas_concluidas": len(concluidas),
            "disciplinas_em_andamento": len(em_andamento),
            "disciplinas_elegiveis": len(elegiveis),
        }
    })


# ── Validação de semestre ──
@app.route("/api/validar_semestre/<int:sem_id>", methods=["GET"])
def validar_semestre(sem_id):
    aprovados = get_aprovados()
    cursando = get_cursando()

    with get_db() as conn:
        discs = [r[0] for r in conn.execute(
            "SELECT disciplina_id FROM plano_disciplinas WHERE semestre_id=?", (sem_id,)
        ).fetchall()]
        creditos = conn.execute(
            f"""SELECT COALESCE(SUM(creditos),0) FROM disciplinas
                WHERE id IN ({','.join('?'*len(discs)) if discs else '0'})""",
            discs
        ).fetchone()[0] if discs else 0

    todos_problemas = []

    for did in discs:
        ok, mp, mc = check_prereqs(did, aprovados, cursando)
        if not ok:
            with get_db() as conn:
                dn = conn.execute("SELECT nome, codigo FROM disciplinas WHERE id=?", (did,)).fetchone()
            for p in mp:
                todos_problemas.append({
                    "tipo": "prerequisito",
                    "disciplina": f"{dn['codigo']} - {dn['nome']}",
                    "mensagem": f"Pré-requisito não cumprido: {p['codigo']} - {p['nome']}"
                })
            for p in mc:
                todos_problemas.append({
                    "tipo": "correquisito",
                    "disciplina": f"{dn['codigo']} - {dn['nome']}",
                    "mensagem": f"Correquisito não selecionado: {p['codigo']} - {p['nome']}"
                })

        for oid in discs:
            if oid <= did:
                continue
            cf = check_horario_conflict(did, [oid])
            for c in cf:
                with get_db() as conn:
                    dn = conn.execute("SELECT nome, codigo FROM disciplinas WHERE id=?", (did,)).fetchone()
                todos_problemas.append({
                    "tipo": "horario",
                    "disciplina": f"{dn['codigo']} - {dn['nome']}",
                    "mensagem": f"Conflito de horário com {c['com_codigo']} - {c['com_nome']} na {c['dia']}: {c['horario']}"
                })

    sobrecarga = creditos > 28
    if sobrecarga:
        todos_problemas.append({
            "tipo": "sobrecarga",
            "disciplina": "Geral",
            "mensagem": f"Sobrecarga de créditos: {creditos} créditos (máx. recomendado: 28)"
        })

    return jsonify({
        "problemas": todos_problemas,
        "creditos_total": creditos,
        "sobrecarga": sobrecarga,
        "ok": len(todos_problemas) == 0
    })


# ─── RUN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("\n" + "="*55)
    print("  📚  Planejador Acadêmico — rodando localmente")
    print("  🌐  Acesse: http://localhost:5000")
    print("  💾  Banco de dados:", DB_PATH)
    print("  ⚡  Pressione Ctrl+C para encerrar")
    print("="*55 + "\n")

    def open_browser():
        import time
        time.sleep(1.2)
        webbrowser.open("http://localhost:5000")

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
