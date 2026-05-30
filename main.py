from fastapi import FastAPI, UploadFile, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import xml.etree.ElementTree as ET
from datetime import datetime
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.auth.transport.requests import AuthorizedSession

app = FastAPI(title="Bulk Google Indexer")
templates = Jinja2Templates(directory="templates")

os.makedirs("templates", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

SCOPES = ["https://www.googleapis.com/auth/indexing"]
SERVICE_ACCOUNT_FILE = "service-account.json"

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/submit-urls")
async def submit_urls(file: UploadFile = None, urls_text: str = Form(None)):
    urls = []
    
    if file:
        content = await file.read()
        content = content.decode('utf-8')
        urls = [line.strip() for line in content.splitlines() if line.strip().startswith("http")]
    elif urls_text:
        urls = [line.strip() for line in urls_text.splitlines() if line.strip().startswith("http")]

    urls = [url for url in urls if url.startswith("http")][:100]

    if not urls:
        return JSONResponse({"error": "No valid URLs found"}, status_code=400)

    # Generate sitemap
    generate_sitemap(urls)

    # Submit to Google
    results = submit_to_indexing_api(urls)

    return {
        "status": "success",
        "processed": len(urls),
        "sitemap_url": "/download-sitemap",
        "results": results
    }

def generate_sitemap(urls):
    root = ET.Element("urlset", {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"})
    for url in urls:
        url_elem = ET.SubElement(root, "url")
        ET.SubElement(url_elem, "loc").text = url
        ET.SubElement(url_elem, "lastmod").text = datetime.now().strftime("%Y-%m-%d")
        ET.SubElement(url_elem, "changefreq").text = "daily"
        ET.SubElement(url_elem, "priority").text = "0.8"
    
    tree = ET.ElementTree(root)
    tree.write("sitemap.xml", encoding="utf-8", xml_declaration=True)

def submit_to_indexing_api(urls):
    try:
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        session = AuthorizedSession(credentials)
        
        results = []
        for url in urls:
            body = {"url": url, "type": "URL_UPDATED"}
            response = session.post(
                "https://indexing.googleapis.com/v3/urlNotifications:publish",
                json=body
            )
            results.append({
                "url": url,
                "status": response.status_code,
                "response": response.text[:300]
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]

@app.get("/download-sitemap")
async def download_sitemap():
    return FileResponse("sitemap.xml", filename="sitemap.xml")
