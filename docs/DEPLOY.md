# Deploy: Supabase (login + banco) e Vercel (app)

Você precisa de contas gratuitas no Supabase, na Vercel e no GitHub, e do projeto no GitHub.

## 1. Supabase
1. **New project**: nome, senha do banco (**guarde-a**) e região próxima (ex.: São Paulo).
2. **Connect** (botão no topo do projeto) > copie duas strings, trocando `[YOUR-PASSWORD]` pela senha:
   - **Transaction pooler** (porta **6543**) → será a `DATABASE_URL` da Vercel (o app).
   - **Session pooler** (porta **5432**, host `...pooler.supabase.com`) → só para rodar migrações do seu PC
     (a conexão direta `db.<ref>.supabase.co` pode ser só IPv6 e falhar no Windows).
   Se a senha tiver `@ # / :`, codifique-os na URL (`@` = `%40`).
3. **Project Settings > API**: copie *Project URL* (`SUPABASE_URL`) e a chave *anon/publishable* (`SUPABASE_ANON_KEY`). A chave `service_role` **nunca** entra aqui.
4. **Authentication > Email Templates > Magic Link**: inclua `{{ .Token }}` no texto (o app aceita o código de 6 dígitos).
5. **Authentication > URL Configuration**: depois do passo 3 da Vercel, ponha a URL do site em *Site URL* e, em *Redirect URLs*, `https://SEU-APP.vercel.app/entrar` (mantenha `http://127.0.0.1:5000/entrar` para dev).

## 2. Criar as tabelas no Supabase (do seu PC, PowerShell)
```powershell
$env:APP_ENV="development"
$env:DATABASE_URL="postgresql://postgres.<ref>:<SENHA>@aws-0-<regiao>.pooler.supabase.com:5432/postgres"
python -m pip install -r requirements.txt
python -m flask --app planner db upgrade
python -m flask --app planner db current     # deve mostrar a revisão head
```
Repita o `db upgrade` sempre que uma migração nova for publicada. (Feche o PowerShell depois: a senha ficou na variável.)

## 3. Vercel
1. Suba o projeto ao GitHub (`.env` e `instance/` já estão no `.gitignore`).
2. Vercel > **Add New > Project** > importe o repositório. Framework: *Other* (o `vercel.json` e o `api/index.py` cuidam do resto).
3. **Environment Variables** (Production):
   | Nome | Valor |
   |---|---|
   | `DATABASE_URL` | Transaction pooler (porta 6543) |
   | `SECRET_KEY` | texto aleatório longo (`python -c "import secrets;print(secrets.token_urlsafe(48))"`) |
   | `SUPABASE_URL` | `https://<ref>.supabase.co` |
   | `SUPABASE_ANON_KEY` | chave anon/publishable |
4. **Deploy**. Se o build falhar por versão do Python, defina `PYTHON_VERSION`/`requires-python` conforme a documentação da Vercel (o projeto usa 3.12 no CI).
5. Volte ao passo 5 do Supabase e cadastre a URL final.

## 4. Conferir
- `https://SEU-APP.vercel.app/api/health` responde OK.
- `/entrar`: peça o link/código com seu e-mail, entre, importe `examples/ciencia-da-computacao/*.csv` e monte um plano.
- Erro 500 ao subir = quase sempre variável faltando (o app recusa iniciar sem elas): veja **Deployments > Logs**.

## 5. CI
`.github/workflows/ci.yml` roda `pytest` e confere `db upgrade` + `db check` a cada push/PR.

## Pendências conhecidas (ver PROGRESSO.md)
- Limite de pedidos de login: vale o do próprio Supabase (Authentication > Rate Limits).
- Gravação concorrente do plano: a última gravação vence.
- Arquivos estáticos saem pela função Flask (simples; não vão para CDN).
- Plano gratuito do Supabase pausa projetos inativos: o primeiro acesso depois disso pode demorar.
