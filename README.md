# Trilha — planejador acadêmico (multi-curso)

Monte o plano de matrícula do seu curso: importe a matriz curricular por CSV (`docs/IMPORTACAO.md`), registre seu histórico,
arraste disciplinas entre semestres, escolha turmas **ou defina seus próprios horários** e veja conflitos, requisitos e carga no calendário.

Status e próximos passos: **`docs/PROGRESSO.md`**.

## Desenvolvimento

```bash
pip install -r requirements-dev.txt
pytest                                # testes
flask --app planner db upgrade        # cria/atualiza o banco (SQLite em instance/)
flask --app planner run --debug       # abra http://127.0.0.1:5000/ (entrar, escolher curso ou importar o seu)
```

Login: sem senha, pelo **Supabase Auth** (o projeto não tem servidor de e-mail). Sem Supabase configurado, o dev usa o provedor `dev`
(a tela aceita qualquer e-mail). Para usar o Supabase de verdade, copie `.env.example` para `.env` e preencha `SUPABASE_URL` e `SUPABASE_ANON_KEY`;
no painel do Supabase: Authentication > URL Configuration > **Redirect URLs** = `http://127.0.0.1:5000/entrar` (e a URL de produção + `/entrar`).
Para o código de 6 dígitos funcionar, inclua `{{ .Token }}` no template do e-mail (Authentication > Email Templates).
Se você já tinha cursos importados antes do login existir: `flask --app planner reivindicar-cursos SEU@EMAIL`.
Em produção: `SECRET_KEY`, `DATABASE_URL`, `SUPABASE_URL` (https), `SUPABASE_ANON_KEY`. Passo a passo do deploy (Supabase + Vercel): **`docs/DEPLOY.md`**.

```bash
python -m tools.export_legacy_seed   # regenera examples/ciencia-da-computacao/*.csv a partir do seed legado
```

Motor de regras (sem banco): `planner/domain/` — testável sozinho, só stdlib.

O app original está preservado em `legacy/` apenas para testes de caracterização.
Documentação: `docs/ARQUITETURA.md`, `docs/PLANO_IMPLEMENTACAO.md`, `docs/DIAGNOSTICO.md`.

### Migrações

```bash
flask --app planner db migrate -m "descrição"   # gera migração após mudar um modelo
flask --app planner db upgrade                  # aplica
flask --app planner db check                    # falha se modelos e migrações divergirem
```
