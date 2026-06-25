from fastapi import FastAPI, Form, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import sqlite3
import re

app = FastAPI()
templates = Jinja2Templates(directory=".")

def init_db():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    # Enable WAL mode for better concurrent read/write performance
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()
    
    # Core table setup
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            summary TEXT,
            content TEXT NOT NULL,
            category TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'published',
            created_at TEXT
        )
    """)
    
    # Migrations for old databases transitioning over
    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN image_url TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN status TEXT DEFAULT 'published'")
    except sqlite3.OperationalError:
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
async def homepage(request: Request, q: str = None, cat: str = None, db=Depends(get_db)):
    cursor = db.cursor()
    
    # Base Query: Only show published articles to the public
    query = "SELECT * FROM articles WHERE status = 'published'"
    params = []

    # Dynamic Feature: Search Filter
    if q:
        query += " AND (title LIKE ? OR summary LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    
    # Dynamic Feature: Category Filter
    if cat:
        query += " AND category = ?"
        params.append(cat)

    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, tuple(params))
    articles = cursor.fetchall()
    
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"articles": articles, "search_query": q, "selected_cat": cat}
    )

@app.get("/news/{slug}", response_class=HTMLResponse)
async def view_article(request: Request, slug: str, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM articles WHERE slug = ?", (slug,))
    article = cursor.fetchone()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return templates.TemplateResponse(request=request, name="article.html", context={"article": article})

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, db=Depends(get_db)):
    cursor = db.cursor()
    # Dashboard shows all items (Drafts + Published) to the writer
    cursor.execute("SELECT * FROM articles ORDER BY created_at DESC")
    all_articles = cursor.fetchall()
    return templates.TemplateResponse(request=request, name="admin.html", context={"articles": all_articles})

@app.post("/admin/publish")
async def publish_article(
    title: str = Form(...), 
    summary: str = Form(...), 
    content: str = Form(...), 
    category: str = Form(...),
    image_url: str = Form(""), 
    status: str = Form("published"), # Captures "draft" or "published"
    db=Depends(get_db)
):
    slug = slugify(title)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor = db.cursor()
    
    # Prevent slug collisions elegantly
    cursor.execute("SELECT id FROM articles WHERE slug = ?", (slug,))
    if cursor.fetchone():
        slug = f"{slug}-{int(datetime.now().timestamp())}"
    
    cursor.execute(
        "INSERT INTO articles (title, slug, summary, content, category, image_url, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (title, slug, summary, content, category, image_url, status, created_at)
    )
    db.commit()

    return RedirectResponse(url="/admin" if status == "draft" else "/", status_code=303)