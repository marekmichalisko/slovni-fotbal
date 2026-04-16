import os
import requests
import redis
import re
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI()

# Konfigurace ze systému (portálem předvyplněné proměnné)
API_KEY = os.environ.get("OPENAI_API_KEY", "chybi-token")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://kurim.ithope.eu/v1")
MODEL = "gemma3:27b"
# REDIS_HOST musí odpovídat názvu služby v compose.yml
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")

# Připojení k Redis databázi (Druhý kontejner)
try:
    db = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
except Exception:
    db = None

@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "Chyba: Soubor index.html nenalezen."

@app.post("/play")
async def play(request: Request):
    data = await request.json()
    user_word = data.get("word", "").strip().lower()
    
    prompt = f"Jsi skript na slovní fotbal. Vrať POUZE JEDNO české podstatné jméno začínající na '{user_word[-1]}'. Žádné věty."
    
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    try:
        resp = requests.post(f"{BASE_URL}/chat/completions", json=payload, headers=headers, timeout=10)
        ai_word = resp.json()["choices"][0]["message"]["content"].strip().lower()
        ai_word = re.sub(r'[^a-záčďéěíňóřšťúůýž]', '', ai_word.split()[0])
        return {"ai_word": ai_word}
    except Exception as e:
        return {"error": str(e)}

@app.post("/score")
async def save_score(request: Request):
    if not db: return {"status": "error"}
    data = await request.json()
    db.zadd("leaderboard", {data.get("name", "Anonym"): int(data.get("score", 0))})
    return {"status": "ok"}

@app.get("/leaderboard")
async def get_leaderboard():
    if not db: return []
    try:
        top = db.zrevrange("leaderboard", 0, 9, withscores=True)
        return [{"name": k, "score": int(v)} for k, v in top]
    except:
        return []
        


@app.get("/reset-db")
async def reset_db():
    if db:
        db.delete("leaderboard")
        return {"status": "Databáze byla úspěšně promazána"}
    return {"status": "Chyba: Databáze není připojená"}
    
if __name__ == "__main__":
    # Portál přiděluje port dynamicky, uvicorn na něm musí naslouchat
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
