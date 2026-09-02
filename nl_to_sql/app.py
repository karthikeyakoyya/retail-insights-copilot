"""
app.py
------
Serves query_copilot.answer() over HTTP so the dashboard (or curl, or Postman)
can ask real questions against the live DuckDB warehouse instead of the
static client-side replay baked into the dashboard's Ask-the-Manifest panel.

Run:
    cd nl_to_sql
    uvicorn app:app --reload --port 8008

Then:
    curl -X POST http://localhost:8008/ask \
         -H "Content-Type: application/json" \
         -d '{"question": "which state has the worst delivery delay?"}'
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from query_copilot import answer

app = FastAPI(title="Retail Insights Copilot — Query API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo project; lock this down before any real deployment
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class Question(BaseModel):
    question: str


@app.get("/")
def health():
    return {"status": "ok", "service": "retail-insights-copilot"}


@app.post("/ask")
def ask(q: Question):
    result = answer(q.question)
    return {
        "question": result.question,
        "sql": result.sql,
        "answer": result.answer,
        "mode": result.mode,
    }
