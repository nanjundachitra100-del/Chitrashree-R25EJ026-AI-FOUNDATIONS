from fastapi import FastAPI, Form, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import sqlite3
import re
import os

app = FastAPI()
templates = Jinja2Templates(directory=".")

# --- VERCEL READ-ONLY ENVIRONMENT FIX ---
# Vercel serverless functions are read-only. We use the /tmp directory if deployed.
IS_VERCEL = "VERCEL" in os.environ
DB_PATH = "/tmp/database.db" if IS_VERCEL else "database.db"

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()
    
    # Core Table Setup: Portfolios / Profiles
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            bio TEXT,
            industry TEXT,
            profile_image_url TEXT,
            skills TEXT,
            created_at TEXT
        )
    """)

    # Project Media Table (Linked to portfolio via portfolio_id)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            project_title TEXT NOT NULL,
            description TEXT,
            media_url TEXT,
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

# Run the database initialization safely
init_db()

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[-\s]+', '-', text).strip('-')

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# --- PUBLIC WEB ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def home_discovery_page(request: Request, q: str = None, ind: str = None, db=Depends(get_db)):
    """Discovery page displaying all user portfolios with search filters."""
    cursor = db.cursor()
    query = "SELECT * FROM portfolios"
    params = []

    conditions = []
    if q:
        conditions.append("(user_name LIKE ? OR skills LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    
    if ind:
        conditions.append("industry = ?")
        params.append(ind)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY created_at DESC"
    cursor.execute(query, tuple(params))
    portfolios = cursor.fetchall()
    
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"portfolios": portfolios, "search_query": q, "selected_industry": ind}
    )

@app.get("/portfolio/{slug}", response_class=HTMLResponse)
async def view_public_portfolio(request: Request, slug: str, db=Depends(get_db)):
    """Publicly accessible view of an individual's complete portfolio profile."""
    cursor = db.cursor()
    
    # Get portfolio owner data
    cursor.execute("SELECT * FROM portfolios WHERE slug = ?", (slug,))
    portfolio = cursor.fetchone()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio profile not found")
    
    # Fetch linked projects
    cursor.execute("SELECT * FROM projects WHERE portfolio_id = ?", (portfolio["id"],))
    projects = cursor.fetchall()
    
    return templates.TemplateResponse(
        request=request, 
        name="portfolio_view.html", 
        context={"portfolio": portfolio, "projects": projects}
    )

# --- PORTFOLIO CREATION & MANAGEMENT ROUTES (Dashboard) ---

@app.get("/dashboard", response_class=HTMLResponse)
async def user_dashboard(request: Request, edit_id: int = None, db=Depends(get_db)):
    """Dashboard view allowing users to see their profile metadata and manage showcases."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM portfolios ORDER BY created_at DESC")
    all_portfolios = cursor.fetchall()
    
    portfolio_to_edit = None
    linked_projects = []
    
    if edit_id:
        cursor.execute("SELECT * FROM portfolios WHERE id = ?", (edit_id,))
        portfolio_to_edit = cursor.fetchone()
        if portfolio_to_edit:
            cursor.execute("SELECT * FROM projects WHERE portfolio_id = ?", (edit_id,))
            linked_projects = cursor.fetchall()
        
    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context={"portfolios": all_portfolios, "edit_portfolio": portfolio_to_edit, "projects": linked_projects}
    )

@app.post("/dashboard/save")
async def save_or_update_portfolio(
    portfolio_id: str = Form(None),
    user_name: str = Form(...), 
    bio: str = Form(...), 
    industry: str = Form(...),
    skills: str = Form(...),
    profile_image_url: str = Form(""), 
    db=Depends(get_db)
):
    """Saves profile updates or creates a brand new public portfolio page."""
    cursor = db.cursor()
    
    if portfolio_id and portfolio_id.strip() != "":
        # Update Profile
        cursor.execute(
            """UPDATE portfolios 
               SET user_name=?, bio=?, industry=?, skills=?, profile_image_url=? 
               WHERE id=?""",
            (user_name, bio, industry, skills, profile_image_url, int(portfolio_id))
        )
    else:
        # Create Profile
        slug = slugify(user_name)
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        cursor.execute("SELECT id FROM portfolios WHERE slug = ?", (slug,))
        if cursor.fetchone():
            slug = f"{slug}-{int(datetime.now().timestamp())}"
        
        cursor.execute(
            """INSERT INTO portfolios (user_name, slug, bio, industry, skills, profile_image_url, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_name, slug, bio, industry, skills, profile_image_url, created_at)
        )
        
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.post("/dashboard/project/add")
async def add_project_to_portfolio(
    portfolio_id: int = Form(...),
    project_title: str = Form(...),
    description: str = Form(...),
    media_url: str = Form(""),
    db=Depends(get_db)
):
    """Allows uploading individual projects directly linked under a specific portfolio identity."""
    cursor = db.cursor()
    cursor.execute(
        """INSERT INTO projects (portfolio_id, project_title, description, media_url) 
           VALUES (?, ?, ?, ?)""",
        (portfolio_id, project_title, description, media_url)
    )
    db.commit()
    return RedirectResponse(url=f"/dashboard?edit_id={portfolio_id}", status_code=303)

@app.post("/dashboard/delete/{portfolio_id}")
async def delete_portfolio(portfolio_id: int, db=Depends(get_db)):
    """Removes a profile along with all associated projects cascaded down the data loop."""
    cursor = db.cursor()
    cursor.execute("DELETE FROM portfolios WHERE id = ?", (portfolio_id,))
    cursor.execute("DELETE FROM projects WHERE portfolio_id = ?", (portfolio_id,))
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)