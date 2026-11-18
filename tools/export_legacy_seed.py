"""
Exporta o seed de Ciência da Computação do app legado para CSVs de exemplo.

Uso (a partir da raiz do projeto):
    python -m tools.export_legacy_seed [pasta_de_destino]

Por que ler o seed "rodando" o legado e não copiando os dados à mão?
Assim a fonte da verdade continua sendo `legacy/app_legacy.py`: o script cria
um banco temporário com `init_db()` e converte o que está nele. Nenhum dado
acadêmico é digitado aqui.

Princípio do projeto: NÃO inventar dados. O que o seed não informa sai VAZIO
(= desconhecido). As poucas inferências necessárias estão nomeadas nas
constantes abaixo, cada uma com a origem no próprio seed.

Os nomes das colunas dos CSVs aqui adotados serão formalizados pelo parser da
Etapa 3A (ver ARQUITETURA.md §5).
"""
from __future__ import annotations

import csv
import gc
import sqlite3
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO_PADRAO = RAIZ / "examples" / "ciencia-da-computacao"

# ── Inferências assumidas a partir dos comentários do seed ──────────────────
# O seed comenta "Optativas Oferecidas (Agrupadas no '9º Período')": o 9 era um
# truque do app antigo para agrupá-las; não é um período real da matriz.
PERIODO_SENTINELA_OPTATIVAS = 9

# O seed comenta "2026/1 (Ímpares) e 2026/2 (Pares)": horários de períodos
# ímpares valem para 2026/1 e os de períodos pares para 2026/2.
PERIODO_LETIVO_IMPAR = "2026/1"
PERIODO_LETIVO_PAR = "2026/2"

# O seed rotula as optativas como "26/1 e 26/2" sem dizer qual é de qual
# semestre. Para não escolher por conta própria, a oferta é exportada nos DOIS
# períodos. REVISAR: apague a linha que não se aplica em turmas.csv.
PERIODOS_LETIVOS_DAS_OPTATIVAS = (PERIODO_LETIVO_IMPAR, PERIODO_LETIVO_PAR)

# O legado só tem 1 conjunto de horários por disciplina = 1 turma por oferta.
CODIGO_TURMA_UNICA = "T1"

CABECALHOS = {
    "curso.csv": [
        "nome", "instituicao", "versao_matriz", "creditos_obrigatorios",
        "creditos_optativos_exigidos", "ch_total", "max_creditos_semestre",
        "duracao_semestres", "dias_letivos",
    ],
    "disciplinas.csv": [
        "codigo", "nome", "creditos", "carga_h", "periodo_sugerido", "tipo", "cor",
    ],
    "requisitos.csv": ["disciplina", "requisito", "tipo", "grupo_alt"],
    "turmas.csv": [
        "disciplina", "periodo_letivo", "codigo_turma", "docente", "vagas", "horarios",
    ],
}


# ── Leitura do legado ───────────────────────────────────────────────────────
def ler_seed_legado() -> dict[str, list[sqlite3.Row]]:
    """Cria o banco do legado em pasta temporária e devolve suas tabelas."""
    from legacy import app_legacy  # import tardio: só quem exporta precisa do legado

    original = app_legacy.DB_PATH
    # Windows: o legado abre conexões com `with get_db() as conn`, que confirma a
    # transação mas NÃO fecha a conexão; o SQLite então mantém `seed.db` travado
    # (WinError 32) e a pasta temporária não pode ser apagada. Por isso: fechamos
    # o que é nosso, `gc.collect()` solta as conexões que o legado deixou soltas e
    # `ignore_cleanup_errors` evita que uma sobra no %TEMP% derrube a exportação.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        app_legacy.DB_PATH = Path(pasta) / "seed.db"
        conexao = None
        try:
            app_legacy.init_db()
            conexao = sqlite3.connect(app_legacy.DB_PATH)
            conexao.row_factory = sqlite3.Row
            consultas = {
                "disciplinas": "SELECT * FROM disciplinas ORDER BY id",
                "horarios": "SELECT * FROM horarios ORDER BY id",
                "requisitos": "SELECT * FROM prerequisitos ORDER BY rowid",
            }
            tabelas = {n: conexao.execute(q).fetchall() for n, q in consultas.items()}
        finally:
            if conexao is not None:
                conexao.close()
            app_legacy.DB_PATH = original
            gc.collect()
    return tabelas


# ── Conversão (funções puras: linhas do legado → linhas de CSV) ─────────────
def _eh_optativa(linha) -> bool:
    return linha["periodo"] == PERIODO_SENTINELA_OPTATIVAS


def _periodo_letivo_do(linha) -> tuple[str, ...]:
    if _eh_optativa(linha):
        return PERIODOS_LETIVOS_DAS_OPTATIVAS
    return (PERIODO_LETIVO_IMPAR if linha["periodo"] % 2 else PERIODO_LETIVO_PAR,)


def montar_curso() -> list[dict]:
    """Só o que o seed afirma: o nome e a "Matriz 2023" do comentário."""
    return [{"nome": "Ciência da Computação", "versao_matriz": "2023"}]


def montar_disciplinas(tabelas) -> list[dict]:
    return [
        {
            "codigo": d["codigo"],
            "nome": d["nome"],
            "creditos": d["creditos"],
            "carga_h": d["carga_h"],
            # Optativa não tem período sugerido: vazio, não "9".
            "periodo_sugerido": None if _eh_optativa(d) else d["periodo"],
            "tipo": "optativa" if _eh_optativa(d) else "obrigatoria",
            "cor": d["cor"],
        }
        for d in tabelas["disciplinas"]
    ]


def montar_requisitos(tabelas) -> list[dict]:
    codigo_de = {d["id"]: d["codigo"] for d in tabelas["disciplinas"]}
    return [
        {
            "disciplina": codigo_de[r["disciplina_id"]],
            "requisito": codigo_de[r["requisito_id"]],
            "tipo": r["tipo"],
            # O legado não tem alternativas (OU): grupo vazio = todos obrigatórios.
        }
        for r in tabelas["requisitos"]
    ]


def formatar_horarios(encontros) -> str:
    """[(SEG,16:00,18:00), ...] → "SEG 16:00-18:00 | QUI 14:00-16:00"."""
    return " | ".join(f"{e['dia']} {e['inicio']}-{e['fim']}" for e in encontros)


def montar_turmas(tabelas) -> list[dict]:
    """Uma turma por (disciplina com horário × período letivo). Docente e vagas ficam vazios."""
    encontros_por_disciplina: dict[int, list] = {}
    for h in tabelas["horarios"]:
        encontros_por_disciplina.setdefault(h["disciplina_id"], []).append(h)

    turmas = []
    for d in tabelas["disciplinas"]:
        encontros = encontros_por_disciplina.get(d["id"])
        if not encontros:  # sem horário no seed = sem turma (não inventamos)
            continue
        for periodo in _periodo_letivo_do(d):
            turmas.append({
                "disciplina": d["codigo"],
                "periodo_letivo": periodo,
                "codigo_turma": CODIGO_TURMA_UNICA,
                "horarios": formatar_horarios(encontros),
            })
    return turmas


# ── Escrita ─────────────────────────────────────────────────────────────────
def _escrever_csv(caminho: Path, cabecalho: list[str], linhas: list[dict]) -> None:
    # utf-8-sig (BOM): o Excel abre os acentos corretamente; o parser da 3A aceita ambos.
    with open(caminho, "w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=cabecalho, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(linhas)  # None vira célula vazia


def exportar(destino: Path = DESTINO_PADRAO) -> dict[str, int]:
    """Gera os 4 CSVs em `destino` e devolve {arquivo: nº de linhas de dados}."""
    tabelas = ler_seed_legado()
    conteudo = {
        "curso.csv": montar_curso(),
        "disciplinas.csv": montar_disciplinas(tabelas),
        "requisitos.csv": montar_requisitos(tabelas),
        "turmas.csv": montar_turmas(tabelas),
    }
    destino.mkdir(parents=True, exist_ok=True)
    for nome, linhas in conteudo.items():
        _escrever_csv(destino / nome, CABECALHOS[nome], linhas)
    return {nome: len(linhas) for nome, linhas in conteudo.items()}


def main(argv: list[str]) -> None:
    destino = Path(argv[1]) if len(argv) > 1 else DESTINO_PADRAO
    for nome, quantidade in exportar(destino).items():
        print(f"{destino / nome}: {quantidade} linhas")


if __name__ == "__main__":
    main(sys.argv)
