from fastapi import FastAPI, Form, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import sqlite3
import re

app = FastAPI()
templates = Jinja2Templates(directory=".")

# Initialize Database and handle migrations automatically
def init_db():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # 1. Create the core table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            summary TEXT,
            content TEXT NOT NULL,
            category TEXT,
            created_at TEXT
        )
    """)
    
    # 2. AUTOMATIC FIX: Safely add image_url if your old database didn't have it
    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN image_url TEXT")
    except sqlite3.OperationalError:
        # This means the column already exists, which is perfect!
        pass
        
    conn.commit()
    conn.close()

init_db()

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[-\s]+', '-', text).strip('-')

def get_db():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# --- WEB ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM articles ORDER BY created_at DESC")
    articles = cursor.fetchall()
    return templates.TemplateResponse(request=request, name="index.html", context={"articles": articles})

@app.get("/news/{slug}", response_class=HTMLResponse)
async def view_article(request: Request, slug: str, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM articles WHERE slug = ?", (slug,))
    article = cursor.fetchone()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return templates.TemplateResponse(request=request, name="index.html", context={"article": article})

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html", context={})

@app.post("/admin/publish")
async def publish_article(
    title: str = Form(...), 
    summary: str = Form(...), 
    content: str = Form(...), 
    category: str = Form(...),
    image_url: str = Form(""), 
    db=Depends(get_db)
):
    slug = slugify(title)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    try:
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO articles (title, slug, summary, content, category, image_url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, slug, summary, content, category, image_url, created_at)
        )
        db.commit()
    except sqlite3.IntegrityError:
        slug = f"{slug}-{int(datetime.now().timestamp())}"
        cursor.execute(
            "INSERT INTO articles (title, slug, summary, content, category, image_url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, slug, summary, content, category, image_url, created_at)
        )
        db.commit()

    return RedirectResponse(url="/", status_code=303)