"""
Modelos de CSV para download e o prompt de IA que preenche esses modelos.

Os cabeçalhos vêm dos `Esquema` dos importadores: se uma coluna mudar na 3A/3B,
os modelos e o prompt mudam junto (um teste confere que os modelos são válidos).
"""
from __future__ import annotations

from dataclasses import dataclass

from . import IMPORTADORES

# Uma linha de exemplo por arquivo, na ordem das colunas do esquema.
_EXEMPLOS: dict[str, dict[str, str]] = {
    "curso.csv": {"nome": "Meu Curso", "versao_matriz": "2024", "duracao_semestres": "8",
                  "dias_letivos": "SEG|TER|QUA|QUI|SEX"},
    "disciplinas.csv": {"codigo": "ABC101", "nome": "Introdução ao Curso", "tipo": "obrigatoria",
                        "creditos": "4", "carga_h": "60", "periodo_sugerido": "1", "cor": "#3b82f6", "periodicidade": "sempre"},
    "requisitos.csv": {"disciplina": "ABC102", "requisito": "ABC101", "tipo": "pre", "grupo_alt": ""},
    "turmas.csv": {"disciplina": "ABC101", "periodo_letivo": "2026/1", "codigo_turma": "T1",
                   "docente": "", "vagas": "", "horarios": "SEG 08:00-10:00 | QUA 08:00-10:00", "local": ""},
}


def modelo_csv(arquivo: str) -> str:
    """Cabeçalho completo + uma linha de exemplo. Levanta `KeyError` para arquivo desconhecido."""
    colunas = IMPORTADORES[arquivo].esquema.colunas
    exemplo = _EXEMPLOS[arquivo]
    return ",".join(colunas) + "\n" + ",".join(exemplo.get(c, "") for c in colunas) + "\n"


def listar_modelos() -> list[str]:
    return list(IMPORTADORES)


def _descricao_dos_arquivos(arquivos: tuple[str, ...]) -> str:
    linhas = []
    for nome in arquivos:
        imp = IMPORTADORES[nome]
        obrig = ", ".join(imp.esquema.obrigatorias)
        opc = ", ".join(imp.esquema.opcionais) or "—"
        linhas.append(f"- {nome}: obrigatórias = {obrig}; opcionais = {opc}")
    return "\n".join(linhas)


@dataclass(frozen=True)
class FonteDeDados:
    """Uma origem possível dos dados do curso e como pedir à IA que a converta."""

    chave: str
    titulo: str
    arquivos: tuple[str, ...]   # CSVs que essa fonte costuma preencher
    tarefa: str                 # o que a IA recebe e deve fazer
    regras_extras: str          # regras específicas da fonte (texto já formatado)


FONTES: dict[str, FonteDeDados] = {f.chave: f for f in (
    FonteDeDados(
        chave="matriz",
        titulo="Matriz curricular (PPC)",
        arquivos=("curso.csv", "disciplinas.csv", "requisitos.csv"),
        tarefa="converter a matriz curricular (PPC) do meu curso em arquivos CSV para um planejador acadêmico",
        regras_extras="""- Gere curso.csv, disciplinas.csv e requisitos.csv. NÃO gere turmas.csv (a oferta de horários vem do quadro de horários).
- Uma linha por disciplina em disciplinas.csv, inclusive as optativas listadas no documento.
- Créditos e carga horária: copie do documento; não calcule.
- curso.csv: preencha creditos_optativos_exigidos (créditos de optativas que o aluno precisa cumprir), creditos_obrigatorios e ch_total SE o documento os trouxer; é com eles que o app diz quantas optativas faltam.""",
    ),
    FonteDeDados(
        chave="horarios",
        titulo="Quadro de horários (oferta do período)",
        arquivos=("turmas.csv",),
        tarefa="converter o quadro de horários (oferta do período) do meu curso em turmas.csv para um planejador acadêmico",
        regras_extras="""- Gere APENAS turmas.csv: uma linha por turma (T1, T2, P1...). Se o quadro mostrar uma disciplina em duas turmas, são duas linhas.
- periodo_letivo vem do cabeçalho/título do quadro (AAAA/N). Se não estiver claro, pergunte-me.
- "|" separa os encontros da MESMA turma; sala/local vai na coluna local (uma sala por turma). Sem sala no quadro, deixe vazio.
- docente e vagas: só se constarem no quadro. Turma sem horário definido: deixe horarios vazio (não invente).
- Use os códigos de disciplina exatamente como aparecem no quadro; eles precisam existir na matriz já importada.""",
    ),
    FonteDeDados(
        chave="web",
        titulo="Site institucional (curso, departamento, catálogo)",
        arquivos=("curso.csv", "disciplinas.csv", "requisitos.csv", "turmas.csv"),
        tarefa="reunir os dados do meu curso a partir de páginas de sites institucionais e convertê-los em arquivos CSV para um planejador acadêmico",
        regras_extras="""- Use somente o que as páginas realmente dizem; se duas páginas divergirem, não escolha: deixe vazio e me avise.
- Depois dos CSVs, liste cada dado duvidoso com a URL de onde veio (ou "não encontrado").
- Ementas e textos descritivos não têm coluna: ignore-os. Gere só os arquivos para os quais encontrou dados.
- Créditos e carga horária: copie da página; não calcule nem estime.""",
    ),
)}


def listar_fontes() -> list[str]:
    return list(FONTES)


def gerar_prompt_ia(fonte: str = "matriz") -> str:
    """
    Texto para colar numa IA junto com o documento/links da fonte escolhida; ela
    devolve os CSVs. Levanta `KeyError` para fonte desconhecida.
    """
    f = FONTES[fonte]
    exemplos = "\n\n".join(f"{nome}\n{modelo_csv(nome).strip()}" for nome in f.arquivos if nome != "curso.csv")
    return f"""Você vai {f.tarefa}.

REGRAS (siga à risca):
1. NUNCA invente dados. Se a informação não está no documento, deixe a célula VAZIA (vazio = desconhecido; não escreva 0, "N/A" nem "-").
2. Um arquivo CSV por bloco de código, com o nome do arquivo antes do bloco. Separador vírgula; textos com vírgula entre aspas.
3. Use exatamente os cabeçalhos abaixo. Gere apenas os arquivos para os quais o documento tem informação.
{_descricao_dos_arquivos(f.arquivos)}
{f.regras_extras}

FORMATOS:
- tipo da disciplina: obrigatoria | optativa | eletiva (obrigatório; se não estiver claro, pergunte-me).
- tipo do requisito: pre (pré-requisito) | co (correquisito).
- requisitos "A ou B": use o mesmo valor em grupo_alt nas linhas alternativas (ex.: G1). Sem grupo = todos obrigatórios.
- periodo_letivo: AAAA/N (ex.: 2026/1). cor: #rrggbb (opcional).
- periodicidade (disciplinas.csv): sempre | impar | par = em que períodos letivos a disciplina é oferecida (impar = só AAAA/1, par = só AAAA/2). TODA disciplina precisa de periodicidade: se o documento não disser, deixe vazio e liste o código ao final para eu informar (nunca assuma \"sempre\"). No quadro de horários, quem só tem turma em períodos de uma paridade é dessa paridade.
- horarios (turmas.csv): "SEG 16:00-18:00 | QUI 14:00-16:00". O "|" separa encontros da MESMA turma (todos obrigatórios).
  Alternativas de matrícula (turma T1 ou T2) são LINHAS diferentes, nunca "|". Dias: SEG TER QUA QUI SEX SAB DOM.
- componente (turmas.csv, opcional): se o quadro separa TEORIA e PRÁTICA em turmas diferentes (ex.: T1 teórica; P1 e P2 práticas, e o aluno se matricula em uma de cada), marque teorica ou pratica em cada linha. Turma que já inclui tudo: deixe vazio.
- codigo_turma é obrigatório em turmas.csv (T1, T2, P1...). Todo código em requisitos/turmas deve existir em disciplinas.csv.

EXEMPLOS DE FORMATO (dados fictícios):
{exemplos}

Ao final, liste as dúvidas e tudo que ficou vazio por não constar no documento.
"""
