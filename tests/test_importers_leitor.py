"""Etapa 3A — leitura bruta de CSV: encoding, BOM, delimitador, cabeçalho, linhas."""
import pytest

from planner.importers import DisciplinaImporter, Severidade

CAB = "codigo,nome,tipo,creditos\n"
LINHA = "INF110,Programação I,obrigatoria,6\n"


def importar(conteudo):
    return DisciplinaImporter().importar(conteudo)


def mensagens(resultado, severidade=None):
    return [i.mensagem for i in resultado.issues if severidade in (None, i.severidade)]


class TestEncoding:
    def test_utf8_simples(self):
        r = importar((CAB + LINHA).encode("utf-8"))
        assert [d.nome for d in r.registros] == ["Programação I"] and not r.issues

    def test_utf8_com_bom(self):
        r = importar(("﻿" + CAB + LINHA).encode("utf-8"))
        assert len(r.registros) == 1 and not r.issues  # BOM não vira parte do nome "codigo"

    def test_texto_ja_decodificado_com_bom(self):
        assert len(importar("﻿" + CAB + LINHA).registros) == 1

    def test_windows_1252_le_com_aviso(self):
        r = importar((CAB + LINHA).encode("cp1252"))
        assert r.registros[0].nome == "Programação I"
        assert any("Windows-1252" in m for m in mensagens(r, Severidade.AVISO))

    def test_arquivo_binario_e_recusado(self):
        r = importar(b"PK\x03\x04\x00\x00xlsx-fake")
        assert r.tem_erros and not r.registros
        assert "não parece ser texto" in r.erros[0].mensagem

    def test_arquivo_vazio(self):
        for conteudo in ("", "   \n\n", b""):
            r = importar(conteudo)
            assert r.tem_erros and "vazio" in r.erros[0].mensagem


class TestDelimitador:
    @pytest.mark.parametrize("delim", [",", ";", "\t"])
    def test_detecta_delimitador(self, delim):
        texto = delim.join(["codigo", "nome", "tipo", "creditos"]) + "\n" + \
            delim.join(["INF110", "Programação I", "obrigatoria", "6"]) + "\n"
        r = importar(texto)
        assert not r.issues and r.registros[0].creditos == 6

    def test_virgula_dentro_de_aspas_nao_divide(self):
        r = importar(CAB + 'INF110,"Cálculo, Limites e Séries",obrigatoria,4\n')
        assert r.registros[0].nome == "Cálculo, Limites e Séries"

    def test_ponto_e_virgula_com_virgula_decimal_no_texto(self):
        r = importar("codigo;nome;tipo;creditos\nINF110;Programação I, avançada;obrigatoria;6,0\n")
        assert r.registros[0].nome == "Programação I, avançada" and r.registros[0].creditos == 6


class TestCabecalho:
    def test_coluna_obrigatoria_ausente_bloqueia_o_arquivo(self):
        r = importar("codigo,nome\nINF110,Programação I\n")
        assert r.tem_erros and not r.registros
        assert "tipo" in r.erros[0].mensagem and r.erros[0].linha == 1

    def test_cabecalho_ignora_caixa_acento_e_espacos(self):
        r = importar("Código,NOME,Tipo,Créditos\nINF110,Programação I,obrigatoria,6\n")
        assert not r.issues and r.registros[0].creditos == 6

    def test_aliases_sao_resolvidos(self):
        r = importar("Cod,Nome,Tipo,Carga Horária,Período\nINF110,Programação I,obrigatoria,90,1\n")
        assert not r.issues
        assert (r.registros[0].carga_h, r.registros[0].periodo_sugerido) == (90, 1)

    def test_coluna_desconhecida_e_so_aviso(self):
        r = importar("codigo,nome,tipo,observacao\nINF110,Programação I,obrigatoria,x\n")
        assert len(r.registros) == 1 and not r.tem_erros
        assert "observacao" in mensagens(r, Severidade.AVISO)[0]

    def test_coluna_repetida_bloqueia(self):
        r = importar("codigo,nome,tipo,nome\nINF110,A,obrigatoria,B\n")
        assert r.tem_erros and "repetida" in r.erros[0].mensagem

    def test_linhas_em_branco_antes_do_cabecalho(self):
        assert len(importar("\n\n" + CAB + LINHA).registros) == 1


class TestLinhas:
    def test_numero_da_linha_e_do_arquivo(self):
        r = importar(CAB + LINHA + "INF112,Programação II,tipo_ruim,6\n")
        assert [(i.linha, i.coluna) for i in r.erros] == [(3, "tipo")]

    def test_linha_em_branco_e_ignorada_mas_conta_na_numeracao(self):
        r = importar(CAB + LINHA + "\n,,,\nINF112,Programação II,tipo_ruim,6\n")
        assert r.linhas_lidas == 2 and r.erros[0].linha == 5

    def test_celulas_faltando_no_fim_viram_vazio(self):
        r = importar(CAB + "INF110,Programação I,obrigatoria\n")
        assert r.registros[0].creditos is None and not r.issues

    def test_colunas_demais_descarta_a_linha(self):
        r = importar(CAB + "INF110,Cálculo, Limites,obrigatoria,4\n" + LINHA)
        assert len(r.registros) == 1 and r.registros[0].codigo == "INF110"
        assert r.linhas_descartadas == 1 and "aspas" in r.erros[0].mensagem

    def test_linha_com_erro_nao_derruba_as_outras(self):
        r = importar(CAB + "INF1,A,xx,1\nINF2,B,optativa,2\nINF3,C,obrigatoria,abc\n")
        assert [d.codigo for d in r.registros] == ["INF2"]
        assert r.linhas_lidas == 3 and len(r.erros) == 2

    def test_issue_serializa_para_json(self):
        r = importar(CAB + "INF1,A,xx,1\n")
        d = r.erros[0].para_dict()
        assert d["severidade"] == "erro" and d["arquivo"] == "disciplinas.csv" and d["linha"] == 2
