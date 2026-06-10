#!/usr/bin/env python3
import os
import requests
import json

APP_ID = os.environ.get('FEISHU_APP_ID')
APP_SECRET = os.environ.get('FEISHU_APP_SECRET')
TABLE_ID = os.environ.get('FEISHU_TABLE_ID')

def get_feishu_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {"app_id": APP_ID, "app_secret": APP_SECRET}
    response = requests.post(url, headers=headers, json=data)
    return response.json()["tenant_access_token"]

def get_table_records(token):
    url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{TABLE_ID}/values/A1:Z100"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    return response.json()

def get_image_url_from_token(token, file_token):
    """通过文件令牌获取图片URL"""
    url = f"https://open.feishu.cn/open-apis/drive/v1/medias/{file_token}/download"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, allow_redirects=False)
    if response.status_code == 302:
        return response.headers.get('Location', '')
    return ""

def extract_image_url(token, image_value):
    """解析飞书表格中的图片字段"""
    if not image_value:
        return ""
    
    try:
        # 尝试解析为 JSON（飞书图片字段格式）
        image_data = json.loads(image_value)
        if isinstance(image_data, list) and len(image_data) > 0:
            # 优先使用 url 字段
            if 'url' in image_data[0] and image_data[0]['url']:
                return image_data[0]['url']
            # 如果没有 url，尝试使用 file_token 获取
            if 'file_token' in image_data[0]:
                return get_image_url_from_token(token, image_data[0]['file_token'])
        return ""
    except (json.JSONDecodeError, TypeError):
        # 如果不是 JSON，直接作为 URL 使用
        return image_value

# ... 其他函数 ...

def generate_journal_entries(records, token, section):
    entries = [r for r in records if r.get('section') == section]
    html = ""
    for entry in entries:
        image_url = extract_image_url(token, entry.get('image', ''))
        html += f"""<article class="journal-entry">
            <div class="journal-date">
                <span class="date-day">{entry.get('date', '1')}</span>
            </div>
            <div class="journal-content journal-content-block">
                <h3>{entry.get('title', '')}</h3>
                {f'<img src="{image_url}" alt="" class="journal-image">' if image_url else ''}
                <p>{entry.get('desc', '')}</p>
            </div>
        </article>"""
    return html

def generate_html(data, token):
    records = []
    if "valueRange" in data.get("data", {}):
        headers = data["data"]["valueRange"]["values"][0] if data["data"]["valueRange"]["values"] else []
        for row in data["data"]["valueRange"]["values"][1:]:
            record = {}
            for i, header in enumerate(headers):
                record[header] = row[i] if i < len(row) else ""
            records.append(record)
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>可颂集｜sakura | 我的生活记录</title>
    <style>
        :root {{
            --font-primary: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            --font-serif: "Georgia", "Times New Roman", serif;
            --color-bg: #ffffff;
            --color-text-main: #2c2c2c;
            --color-text-muted: #888888;
            --color-accent: #d4c4b4;
            --color-border: #f0f0f0;
            --spacing-unit: 8px;
            --container-width: 1024px;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: var(--font-primary); background: var(--color-bg); color: var(--color-text-main); line-height: 1.7; -webkit-font-smoothing: antialiased; }}
        a {{ color: inherit; text-decoration: none; transition: opacity 0.2s; }}
        a:hover {{ opacity: 0.7; }}
        h1, h2, h3 {{ font-weight: 400; line-height: 1.3; letter-spacing: -0.5px; }}
        h1 {{ font-size: 2.5rem; }}
        h2 {{ font-size: 2rem; margin-bottom: calc(var(--spacing-unit) * 4); text-align: center; }}
        h3 {{ font-size: 1.25rem; }}
        p {{ margin-bottom: calc(var(--spacing-unit) * 2); }}
        img {{ max-width: 100%; height: auto; display: block; background: #f8f8f8; }}
        .container {{ width: 92%; max-width: var(--container-width); margin: 0 auto; }}
        .section {{ padding: calc(var(--spacing-unit) * 12) 0; }}
        
        .navbar {{
            padding: calc(var(--spacing-unit) * 3) 0;
            position: sticky; top: 0;
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(10px); z-index: 100;
        }}
        .navbar-content {{ display: flex; justify-content: space-between; align-items: center; }}
        .brand {{ font-family: var(--font-serif); font-size: 1.5rem; letter-spacing: 1px; }}
        .nav-links {{ display: flex; gap: calc(var(--spacing-unit) * 4); }}
        .nav-links a {{ font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; color: var(--color-text-muted); font-weight: 500; }}
        .nav-links a:hover {{ color: var(--color-text-main); }}

        .hero {{ text-align: center; padding: calc(var(--spacing-unit) * 6) 0 calc(var(--spacing-unit) * 10); }}
        .hero-image-container {{ height: 60vh; min-height: 400px; overflow: hidden; margin-bottom: calc(var(--spacing-unit) * 5); }}
        .hero-image {{ width: 100%; height: 100%; object-fit: cover; }}

        .grid-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: calc(var(--spacing-unit) * 6) calc(var(--spacing-unit) * 4);
        }}
        .card {{ display: flex; flex-direction: column; }}
        .card-image {{
            aspect-ratio: 3 / 4; margin-bottom: calc(var(--spacing-unit) * 2.5);
            overflow: hidden; border-radius: 2px;
        }}
        .card-image img {{ width: 100%; height: 100%; object-fit: cover; transition: transform 0.5s ease; }}
        .card:hover .card-image img {{ transform: scale(1.03); }}
        .card-meta {{
            font-size: 0.75rem; color: var(--color-accent);
            text-transform: uppercase; letter-spacing: 1px; font-weight: 600;
        }}
        .card-title {{ font-size: 1.1rem; }}
        .card-desc {{ font-size: 0.9rem; color: var(--color-text-muted); line-height: 1.5; }}

        .journal-list {{ display: flex; flex-direction: column; gap: calc(var(--spacing-unit) * 10); }}
        .journal-entry {{
            display: grid; grid-template-columns: 120px 1fr;
            gap: calc(var(--spacing-unit) * 6); padding-bottom: calc(var(--spacing-unit) * 6);
            border-bottom: 1px solid var(--color-border);
        }}
        .journal-entry:last-child {{ border-bottom: none; }}
        .journal-date {{ text-align: right; font-family: var(--font-serif); color: var(--color-text-muted); }}
        .date-day {{ font-size: 2rem; font-weight: 700; color: var(--color-text-main); }}
        .journal-content-block h3 {{ font-size: 1.5rem; }}
        .journal-image {{ width: 100%; aspect-ratio: 16 / 9; border-radius: 2px; margin: calc(var(--spacing-unit) * 4) 0; }}

        .travel-grid {{
            display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: calc(var(--spacing-unit) * 3);
        }}
        .travel-card {{ aspect-ratio: 1; overflow: hidden; border-radius: 2px; }}
        .travel-card img {{ width: 100%; height: 100%; object-fit: cover; }}

        .footer {{
            padding: calc(var(--spacing-unit) * 8) 0; text-align: center;
            border-top: 1px solid var(--color-border); margin-top: calc(var(--spacing-unit) * 4);
            font-size: 0.85rem; color: var(--color-text-muted);
        }}

        @media (max-width: 768px) {{
            .journal-entry {{ grid-template-columns: 1fr; }}
            .journal-date {{ text-align: left; }}
            h1 {{ font-size: 2rem; }}
            h2 {{ font-size: 1.75rem; }}
        }}
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="container navbar-content">
            <a href="#" class="brand">可颂集｜sakura</a>
            <div class="nav-links">
                <a href="#family-moments">家・时光</a>
                <a href="#footprints">行・足迹</a>
                <a href="#read-watch">阅・视界</a>
                <a href="#thoughts">思・杂谈</a>
            </div>
        </div>
    </nav>

    <header class="hero">
        <div class="container">
            <div class="hero-image-container">
                <img src="https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=minimalist%20lifestyle%20journal%20aesthetic%20soft%20natural%20light%20cozy%20reading%20corner&image_size=landscape_16_9" alt="首页大图" class="hero-image">
            </div>
            <h1>记录生活，珍藏那些稍纵即逝的瞬间。</h1>
            <p style="font-family: var(--font-serif); font-size: 1.2rem; color: var(--color-text-muted); margin-top: calc(var(--spacing-unit) * 2); font-style: italic;">— A minimalist chronicle of life and thoughts.</p>
        </div>
    </header>

    <section id="family-moments" class="section">
        <div class="container">
            <h2>家・时光</h2>
            <div class="journal-list">
                {generate_journal_entries(records, token, '家・时光')}
            </div>
        </div>
    </section>

    <section id="footprints" class="section" style="background: #fafafa;">
        <div class="container">
            <h2>行・足迹</h2>
            <div class="travel-grid">
                {generate_travel_cards(records, token)}
            </div>
        </div>
    </section>

    <section id="read-watch" class="section">
        <div class="container">
            <h2>阅・视界</h2>
            <div class="grid-cards">
                {generate_read_watch_cards(records, token)}
            </div>
        </div>
    </section>

    <section id="thoughts" class="section" style="background: #fafafa;">
        <div class="container">
            <h2>思・杂谈</h2>
            <div class="journal-list">
                {generate_thought_entries(records)}
            </div>
        </div>
    </section>

    <footer class="footer">
        <div class="container">
            <p>可颂集｜sakura</p>
            <p style="margin-top: calc(var(--spacing-unit) * 2); font-size: 0.75rem; opacity: 0.5;">© 2024 · 记录生活中的美好瞬间</p>
        </div>
    </footer>
</body>
</html>"""
    
    return html

if __name__ == "__main__":
    token = get_feishu_token()
    data = get_table_records(token)
    html = generate_html(data, token)
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    
    print("✓ HTML generated successfully!")
