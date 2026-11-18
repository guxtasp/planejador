"""
Domínio puro: regras de negócio sem SQL nem HTTP (Etapa 2).

Só biblioteca padrão. Entradas são dataclasses imutáveis (`entidades.py`);
os serviços convertem modelos do banco nelas. Módulos:

  entidades   value objects            historico  N tentativas → situação
  requisitos  pré/co, OR, plano        progresso  obrigatórias + optativas
  carga       sobrecarga do semestre   previsao   formatura pela média do aluno
  conflitos   horários por turma         grade      dias/horas derivados dos encontros
  analise     plano completo: carga + requisitos + conflitos (4B)
  painel      status por disciplina + progresso + previsão a partir do histórico (5B)
"""
