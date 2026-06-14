#!/usr/bin/env python3
import os
import requests
import sys

FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET')
FEISHU_APP_TOKEN = os.environ.get('FEISHU_APP_TOKEN')
FEISHU_BITABLE_TABLE_ID = os.environ.get('FEISHU_BITABLE_TABLE_ID')


def log(message):
    print(f"[DEBUG] {message}")


def get_feishu_token():
    """获取飞书 tenant_access_token"""
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        log("ERROR: FEISHU_APP_ID 或 FEISHU_APP_SECRET 未设置")
        sys.exit(1)

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()

        if result.get("code") != 0:
            log(f"ERROR: 获取 token 失败: {result}")
            sys.exit(1)

        log("✓ 成功获取 tenant_access_token")
        return result["tenant_access_token"]
    except Exception as e:
        log(f"ERROR: 获取 token 异常: {e}")
        sys.exit(1)


def get_bitable_records(token):
    """从多维表格获取数据"""
    if not FEISHU_APP_TOKEN or not FEISHU_BITABLE_TABLE_ID:
        log("ERROR: FEISHU_APP_TOKEN 或 FEISHU_BITABLE_TABLE_ID 未设置")
        sys.exit(1)

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_BITABLE_TABLE_ID}/records"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        result = response.json()

        if result.get("code") != 0:
            log(f"ERROR: 获取数据失败: {result}")
            sys.exit(1)

        records = result.get("data", {}).get("items", [])
        log(f"✓ 成功获取 {len(records)} 条记录")

        return records
    except Exception as e:
        log(f"ERROR: 获取数据异常: {e}")
        sys.exit(1)


def get_image_preview_url(file_token, token):
    """获取图片的预览 URL（使用 POST 方法）"""
    url = f"https://open.feishu.cn/open-apis/drive/v1/files/{file_token}/preview/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "type": "image",
        "width": 1200,
        "height": 1200
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        log(f"  Response status: {response.status_code}")
        log(f"  Response headers: {dict(response.headers)}")

        # 尝试解析 JSON
        try:
            result = response.json()
            log(f"  Response body: {result}")
        except:
            log(f"  Response is not JSON, raw text: {response.text[:200]}")

        result = response.json()
        if result.get("code") != 0:
            log(f"ERROR: 获取图片预览 URL 失败: {result}")
            return ""

        # 飞书返回的预览 URL
        preview_url = result.get("data", {}).get("preview_url", "")
        if not preview_url:
            # 尝试其他可能的字段
            preview_url = result.get("data", {}).get("url", "")

        return preview_url
    except Exception as e:
        log(f"ERROR: 获取图片预览 URL 异常: {e}")
        return ""


def process_image_urls(records, token):
    """处理所有记录的图片字段，获取临时预览 URL"""
    unique_tokens = set()

    # 收集所有图片的 file_token（去重）
    for record in records:
        image_value = record.get("fields", {}).get("image")
        if image_value and isinstance(image_value, list):
            for attachment in image_value:
                if isinstance(attachment, dict) and "file_token" in attachment:
                    unique_tokens.add(attachment["file_token"])

    if not unique_tokens:
        return

    log(f"正在获取 {len(unique_tokens)} 个图片的预览 URL...")

    # 只处理第一个图片用于调试
    first_token = list(unique_tokens)[0]
    log(f"测试第一个图片的 file_token: {first_token}")
    preview_url = get_image_preview_url(first_token, token)
    if preview_url:
        log(f"✓ 成功获取预览 URL: {preview_url}")

    # 暂时只处理第一个
    url_map = {}
    for file_token in unique_tokens:
        preview_url = get_image_preview_url(file_token, token)
        if preview_url:
            url_map[file_token] = preview_url

    log(f"✓ 成功获取 {len(url_map)} 个预览 URL")

    # 更新记录中的图片 URL
    for record in records:
        image_value = record.get("fields", {}).get("image")
        if image_value and isinstance(image_value, list):
            for attachment in image_value:
                if isinstance(attachment, dict) and "file_token" in attachment:
                    file_token = attachment["file_token"]
                    if file_token in url_map:
                        attachment["public_url"] = url_map[file_token]


def field_value(record, field_name):
    """从多维表格记录中获取字段值，支持不同类型"""
    fields = record.get("fields", {})
    value = fields.get(field_name)

    if value is None:
        return ""

    # 处理不同的字段类型
    if isinstance(value, list):
        if not value:
            return ""
        # 处理附件类型（图片等）
        if len(value) > 0 and isinstance(value[0], dict):
            attachment = value[0]
            # 优先使用处理后的公共 URL
            if "public_url" in attachment and attachment["public_url"]:
                return attachment["public_url"]
            # 然后使用 tmp_url
            if "tmp_url" in attachment:
                return attachment["tmp_url"]
            # 然后使用 url
            if "url" in attachment:
                return attachment["url"]
        return str(value[0]) if len(value) == 1 else ", ".join(str(v) for v in value)

    return str(value)


def generate_journal_entries(records, section):
    entries = [r for r in records if field_value(r, 'section') == section]
    html = ""
    for entry in entries:
        image = field_value(entry, 'image')
        date = field_value(entry, 'date')
        title = field_value(entry, 'title')
        desc = field_value(entry, 'desc')

        html += f"""<article class="journal-entry">
            <div class="journal-date">
                <span class="date-day">{date}</span>
            </div>
            <div class="journal-content journal-content-block">
                <h3>{title}</h3>
                {f'<img src="{image}" alt="" class="journal-image">' if image else ''}
                <p>{desc}</p>
            </div>
        </article>"""
    return html


def generate_travel_cards(records):
    entries = [r for r in records if field_value(r, 'section') == '行・足迹']
    html = ""
    for entry in entries:
        image = field_value(entry, 'image')
        title = field_value(entry, 'title')
        html += f"""<div class="travel-card">
            <img src="{image}" alt="{title}">
        </div>"""
    return html


def generate_read_watch_cards(records):
    entries = [r for r in records if field_value(r, 'section') == '阅・视界']
    html = ""
    for entry in entries:
        image = field_value(entry, 'image')
        meta = field_value(entry, 'meta')
        title = field_value(entry, 'title')
        desc = field_value(entry, 'desc')
        html += f"""<article class="card">
            <div class="card-image">
                <img src="{image}" alt="">
            </div>
            <div class="card-meta">{meta}</div>
            <h3 class="card-title">{title}</h3>
            <p class="card-desc">{desc}</p>
        </article>"""
    return html


def generate_thought_entries(records):
    entries = [r for r in records if field_value(r, 'section') == '思・杂谈']
    html = ""
    for entry in entries:
        date = field_value(entry, 'date')
        title = field_value(entry, 'title')
        desc = field_value(entry, 'desc')
        html += f"""<article class="journal-entry">
            <div class="journal-date">
                <span class="date-day">{date}</span>
            </div>
            <div class="journal-content">
                <h3>{title}</h3>
                <p>{desc}</p>
            </div>
        </article>"""
    return html


def generate_html(records):
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
                {generate_journal_entries(records, '家・时光')}
            </div>
        </div>
    </section>

    <section id="footprints" class="section" style="background: #fafafa;">
        <div class="container">
            <h2>行・足迹</h2>
            <div class="travel-grid">
                {generate_travel_cards(records)}
            </div>
        </div>
    </section>

    <section id="read-watch" class="section">
        <div class="container">
            <h2>阅・视界</h2>
            <div class="grid-cards">
                {generate_read_watch_cards(records)}
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
    log("=" * 50)
    log("开始生成网站...")
    log("=" * 50)

    # 获取飞书 token
    token = get_feishu_token()

    # 从多维表格获取数据
    records = get_bitable_records(token)

    # 处理图片 URL
    process_image_urls(records, token)

    # 输出记录信息（用于调试）
    if records:
        log(f"第一条记录的 image 值: {field_value(records[0], 'image')}")

    # 生成 HTML
    html = generate_html(records)

    # 写入文件
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)

    log("=" * 50)
    log("✓ HTML 生成成功!")
    log("=" * 50)