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
            reading_time INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)
    
    # Migrations for existing databases transitioning over
    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN reading_time INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()

init_db()

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[-\s]+', '-', text).strip('-')

def calculate_reading_time(html_content: str) -> int:
    # Strip HTML tags to count raw words roughly
    clean_text = re.sub(r'<[^>]*>', ' ', html_content)
    words = clean_text.split()
    word_count = len(words)
    # Average reading speed: 200 words per minute
    minutes = max(1, round(word_count / 200))
    return minutes

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
    query = "SELECT * FROM articles WHERE status = 'published'"
    params = []

    if q:
        query += " AND (title LIKE ? OR summary LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    
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

# --- ADMIN PANEL & MANAGEMENT ROUTES ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, edit_id: int = None, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM articles ORDER BY created_at DESC")
    all_articles = cursor.fetchall()
    
    # If editing, grab the targeted article data to fill the form
    article_to_edit = None
    if edit_id:
        cursor.execute("SELECT * FROM articles WHERE id = ?", (edit_id,))
        article_to_edit = cursor.fetchone()
        
    return templates.TemplateResponse(
        request=request, 
        name="admin.html", 
        context={"articles": all_articles, "edit_article": article_to_edit}
    )

@app.post("/admin/publish")
async def publish_or_update_article(
    article_id: str = Form(None), # Present only during edits
    title: str = Form(...), 
    summary: str = Form(...), 
    content: str = Form(...), 
    category: str = Form(...),
    image_url: str = Form(""), 
    status: str = Form("published"),
    db=Depends(get_db)
):
    cursor = db.cursor()
    reading_time = calculate_reading_time(content)
    
    if article_id and article_id.strip() != "":
        # UPDATE EXISTING ARTICLE
        cursor.execute(
            """UPDATE articles 
               SET title=?, summary=?, content=?, category=?, image_url=?, status=?, reading_time=? 
               WHERE id=?""",
            (title, summary, content, category, image_url, status, reading_time, int(article_id))
        )
    else:
        # INSERT NEW ARTICLE
        slug = slugify(title)
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        cursor.execute("SELECT id FROM articles WHERE slug = ?", (slug,))
        if cursor.fetchone():
            slug = f"{slug}-{int(datetime.now().timestamp())}"
        
        cursor.execute(
            """INSERT INTO articles (title, slug, summary, content, category, image_url, status, reading_time, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, slug, summary, content, category, image_url, status, reading_time, created_at)
        )
        
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/delete/{article_id}")
async def delete_article(article_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)