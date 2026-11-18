"""Ponto de entrada da Vercel (função serverless Python): expõe `app` (WSGI)."""
import os

# Na Vercel o ambiente é sempre produção; `create_app` falha cedo se faltar
# DATABASE_URL, SECRET_KEY, SUPABASE_URL ou SUPABASE_ANON_KEY.
os.environ["APP_ENV"] = "production"

from planner import create_app  # noqa: E402

app = create_app()
