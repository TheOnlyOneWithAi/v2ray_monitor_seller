from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from .db import Session,Plan,Setting,Order
from .config import settings
from html import escape
app=FastAPI(title='V2Ray Monitor Seller')

DEFAULT_HTML='''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{title}}</title><style>body{font-family:system-ui;background:#10131a;color:#fff;margin:0}.wrap{max-width:900px;margin:auto;padding:32px}.plans{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}.card{background:#1b2130;border-radius:18px;padding:22px}.price{font-size:28px;font-weight:800}.btn{display:block;text-align:center;background:#2d7dff;color:#fff;padding:12px;border-radius:12px;text-decoration:none}</style></head><body><div class="wrap"><h1>{{title}}</h1><div class="plans">{{plans}}</div></div></body></html>'''

def render(plans,title='V2Ray Shop'):
    cards=''.join(f'<div class="card"><h2>{escape(p.name)}</h2><div class="price">{p.price:,} تومان</div><p>تا {p.max_configs} کانفیگ</p></div>' for p in plans)
    return DEFAULT_HTML.replace('{{title}}',escape(title)).replace('{{plans}}',cards)

@app.get('/',response_class=HTMLResponse)
async def home():
    async with Session() as s: plans=(await s.execute(select(Plan).where(Plan.active==True).order_by(Plan.price))).scalars().all()
    return render(plans)

@app.get('/health')
async def health(): return {'status':'ok'}
