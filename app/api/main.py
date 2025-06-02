import csv, io, hmac, hashlib, os, time
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse
from fastapi.security import OAuth2AuthorizationCodeBearer
from pymongo import DESCENDING
from urllib.parse import urlencode
...
SECRET = os.getenv("EXPORT_SECRET", "change_me")      # ↔ .env
OAUTH_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("OAUTH_REDIRECT", "http://localhost:8000/callback")

oauth_scheme = OAuth2AuthorizationCodeBearer(
        authorizationUrl="https://discord.com/api/oauth2/authorize",
        tokenUrl="https://discord.com/api/oauth2/token",
        scopes={"identify": "Read your Discord user ID"}
)

def sign(payload: str) -> str:
    return hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()

def verify(payload: str, sig: str) -> bool:
    return hmac.compare_digest(sign(payload), sig)

# ---------- CSV helpers ----------
def to_csv_rows(cursor, fields):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for doc in cursor:
        writer.writerow({f: doc.get(f, "") for f in fields})
    buffer.seek(0)
    return buffer

def csv_response(buffer, filename):
    return StreamingResponse(buffer,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'})

# ---------- Export routes ----------
@app.get("/export/leaderboard.csv")
def csv_leader(metric: str = "quests"):
    cur = players.find({}, {"player_id": 1, metric: 1})\
                 .sort(metric, DESCENDING).limit(100)
    buf = to_csv_rows(cur, ["player_id", metric])
    return csv_response(buf, f"leader_{metric}.csv")

@app.get("/export/churn.csv")
def csv_churn(days: int = 30):
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=days)
    cur = players.find({"last_active": {"$lt": cutoff}},
                       {"player_id": 1, "last_active": 1})
    buf = to_csv_rows(cur, ["player_id", "last_active"])
    return csv_response(buf, f"churn_{days}.csv")

@app.get("/export/player/{pid}.json")
def export_player(pid: int):
    doc = players.find_one({"player_id": pid}, {"_id":0})
    if not doc:
        raise HTTPException(404, "player not found")
    return JSONResponse(doc)

# ---------- Signed-link wrapper ----------
@app.get("/download")
def download(file: str, sig: str):
    if not verify(file, sig):
        raise HTTPException(403, "bad signature")
    return RedirectResponse(url=file)

# ---------- Discord OAuth ----------
@app.get("/login/discord")
def login_discord():
    params = urlencode({
        "response_type":"code",
        "client_id": OAUTH_CLIENT_ID,
        "scope": "identify",
        "redirect_uri": REDIRECT_URI
    })
    return RedirectResponse(f"https://discord.com/api/oauth2/authorize?{params}")

@app.get("/callback")
def callback(code: str):
    # exchange code → access_token, fetch user id (see FastAPI OAuth example) :contentReference[oaicite:0]{index=0}
    # Issue your own JWT or session cookie here
    return {"status": "logged in"}