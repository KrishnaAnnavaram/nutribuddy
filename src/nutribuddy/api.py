"""Optional FastAPI app (extra: api). JSON in, JSON out. The page shows all text with ``textContent``."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .planner import PlanUnavailable
from .safety import InputError
from .service import NutriBuddy
from .sessions import SessionNotFound


class ScreenIn(BaseModel):
    symptoms: str = Field(max_length=5000)


class PlanIn(BaseModel):
    condition: str = Field(max_length=40)
    session_id: str | None = Field(default=None, max_length=64)


class SessionIn(BaseModel):
    condition: str | None = Field(default=None, max_length=40)


class AskIn(BaseModel):
    session_id: str = Field(max_length=64)
    question: str = Field(max_length=5000)


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>nutribuddy</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{font-family:system-ui,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem}
pre{white-space:pre-wrap;background:#f4f4f4;padding:1rem}</style></head><body>
<h1>nutribuddy</h1><p id="disclaimer"></p>
<label>Condition <select id="cond"><option>diabetes</option><option>heart</option><option>thyroid</option></select></label>
<button id="plan">Get a diet plan</button>
<p><input id="q" size="50" placeholder="Follow-up question"><button id="ask">Ask</button></p>
<pre id="out"></pre>
<script>
let sid = null;
const out = document.getElementById('out');
async function post(url, body){const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});return r.json();}
document.getElementById('plan').onclick = async () => {
  const s = await post('/api/session', {condition: document.getElementById('cond').value}); sid = s.session_id;
  const p = await post('/api/plan', {condition: document.getElementById('cond').value, session_id: sid});
  out.textContent = p.text || p.detail; document.getElementById('disclaimer').textContent = p.disclaimer || '';
};
document.getElementById('ask').onclick = async () => {
  if (!sid) { out.textContent = 'Get a diet plan first.'; return; }
  const a = await post('/api/ask', {session_id: sid, question: document.getElementById('q').value});
  out.textContent = (a.text || a.detail) + '\\n\\n' + (a.sources || []).join('\\n');
};
</script></body></html>"""


def create_app(bot: NutriBuddy) -> FastAPI:
    from .render import plan_to_text

    app = FastAPI(title="nutribuddy", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def page() -> str:
        return PAGE

    @app.post("/api/screen")
    def screen(body: ScreenIn) -> dict:
        try:
            return bot.screen(body.symptoms).to_dict()
        except InputError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/session")
    def session(body: SessionIn) -> dict:
        try:
            return {"session_id": bot.new_session(body.condition)}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/plan")
    def plan(body: PlanIn) -> dict:
        try:
            p = bot.plan(body.condition, session_id=body.session_id)
        except SessionNotFound as exc:
            raise HTTPException(404, "unknown session") from exc
        except PlanUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {**p.to_dict(), "text": plan_to_text(p)}

    @app.post("/api/ask")
    def ask(body: AskIn) -> dict:
        try:
            return bot.ask(body.session_id, body.question).to_dict()
        except SessionNotFound as exc:
            raise HTTPException(404, "unknown session") from exc
        except InputError as exc:
            raise HTTPException(422, str(exc)) from exc

    return app
