import os, time
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel
import sqlite3

API_KEY = os.getenv("API_KEY", "change-me")

def auth(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing/invalid token")
    token = authorization.split(" ", 1)[1]
    if token != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return True

DB_PATH = os.getenv("DB_PATH", "data.db")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init():
    conn = db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS state(
        k TEXT PRIMARY KEY, v TEXT, updated_at INTEGER)""")
    c.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS memory
        USING fts5(event, tags, created_at UNINDEXED, tokenize = 'porter')""")
    c.execute("""CREATE TABLE IF NOT EXISTS goals(
        id INTEGER PRIMARY KEY AUTOINCREMENT, goal TEXT, status TEXT, created_at INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS goal_notes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, goal_id INTEGER, note TEXT, created_at INTEGER)""")
    conn.commit(); conn.close()

init()
app = FastAPI(title="External Memory & State")

class KV(BaseModel):
    key: str
    value: str

class MemoryIn(BaseModel):
    event: str
    tags: Optional[List[str]] = None

class GoalIn(BaseModel):
    goal: str

class ProgressIn(BaseModel):
    goal_id: int
    status: Optional[str] = None
    note: Optional[str] = None

@app.post("/state/set")
def state_set(body: KV, _=Depends(auth)):
    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO state(k,v,updated_at) VALUES(?,?,?) "
              "ON CONFLICT(k) DO UPDATE SET v=excluded.v, updated_at=excluded.updated_at",
              (body.key, body.value, int(time.time())))
    conn.commit(); conn.close()
    return {"ok": True}

@app.get("/state/get")
def state_get(key: str, _=Depends(auth)):
    conn = db(); c = conn.cursor()
    row = c.execute("SELECT v FROM state WHERE k=?", (key,)).fetchone()
    conn.close()
    return {"value": row["v"] if row else None}

@app.post("/memory/add")
def memory_add(body: MemoryIn, _=Depends(auth)):
    tags = ",".join(body.tags) if body.tags else ""
    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO memory(event, tags, created_at) VALUES(?,?,?)",
              (body.event, tags, int(time.time())))
    conn.commit(); conn.close()
    return {"ok": True}

@app.get("/memory/search")
def memory_search(q: str, limit: int = 20, _=Depends(auth)):
    conn = db(); c = conn.cursor()
    rows = c.execute("SELECT rowid, event, tags FROM memory WHERE memory MATCH ? LIMIT ?",
                     (q, limit)).fetchall()
    conn.close()
    return [{"id": r["rowid"], "event": r["event"], "tags": r["tags"]} for r in rows]

@app.post("/goals/add")
def goals_add(body: GoalIn, _=Depends(auth)):
    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO goals(goal, status, created_at) VALUES(?,?,?)",
              (body.goal, "new", int(time.time())))
    conn.commit()
    gid = c.lastrowid
    conn.close()
    return {"id": gid, "goal": body.goal, "status": "new"}

@app.post("/goals/progress")
def goals_progress(body: ProgressIn, _=Depends(auth)):
    conn = db(); c = conn.cursor()
    if body.status:
        c.execute("UPDATE goals SET status=? WHERE id=?", (body.status, body.goal_id))
    if body.note:
        c.execute("INSERT INTO goal_notes(goal_id, note, created_at) VALUES(?,?,?)",
                  (body.goal_id, body.note, int(time.time())))
    conn.commit(); conn.close()
    return {"ok": True}

@app.get("/context/export")
def context_export(max_tokens: int = 1500, _=Depends(auth)):
    # Simple export: latest state + last N memory lines + active goals
    conn = db(); c = conn.cursor()
    state = c.execute("SELECT k, v FROM state ORDER BY updated_at DESC").fetchall()
    goals = c.execute("SELECT id, goal, status FROM goals ORDER BY created_at DESC LIMIT 20").fetchall()
    mem  = c.execute("SELECT event, tags FROM memory ORDER BY rowid DESC LIMIT 50").fetchall()
    conn.close()

    lines = ["# State:"]
    lines += [f"- {r['k']}: {r['v']}" for r in state]
    lines += ["", "# Goals:"]
    lines += [f"- [{r['status']}] ({r['id']}) {r['goal']}" for r in goals]
    lines += ["", "# Recent Memory:"]
    lines += [f"- {r['event']} ({r['tags']})" for r in mem]
    export = "\n".join(lines)
    # (For MVP we don’t hard-trim by tokens; most OSS endpoints accept long prompts. Add summarization later.)
    return {"prompt_block": export[:20000]}