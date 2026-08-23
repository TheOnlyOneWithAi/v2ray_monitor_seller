import logging
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.enums import ChatMemberStatus
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
from .config import settings
from .db import Session, Plan, User, Order, Subscription, Setting
log=logging.getLogger(__name__)
def kb(rows):return InlineKeyboardMarkup(inline_keyboard=rows)
def parse_pair(text):
    x=text.split('|',1);return x[0].strip(),x[1].strip() if len(x)>1 else ''
async def cfg(key,default=''):
    async with Session() as s:
        x=await s.get(Setting,key);return x.value if x else default
async def setcfg(key,value):
    async with Session() as s:
        x=await s.get(Setting,key)
        if x:x.value=value
        else:s.add(Setting(key=key,value=value))
        await s.commit()
async def is_joined(bot,uid):
    enabled=(await cfg('force_join_enabled','true')).lower()=='true';channel=await cfg('force_join_channel',settings.force_join_channel)
    if not enabled or not channel:return True
    try:return (await bot.get_chat_member(channel,uid)).status in {ChatMemberStatus.MEMBER,ChatMemberStatus.ADMINISTRATOR,ChatMemberStatus.CREATOR}
    except Exception:return False
async def gate(m,bot):
    if await is_joined(bot,m.from_user.id):return True
    ch=await cfg('force_join_channel',settings.force_join_channel);url=await cfg('force_join_channel_url',settings.force_join_channel_url) or ('https://t.me/'+ch.lstrip('@'))
    await m.answer('🔒 ابتدا عضو کانال شوید.',reply_markup=kb([[InlineKeyboardButton(text='عضویت',url=url)],[InlineKeyboardButton(text='✅ بررسی',callback_data='checkjoin')]]));return False
async def ensure_user(u):
    async with Session() as s:
        x=(await s.execute(select(User).where(User.telegram_id==u.id))).scalar_one_or_none()
        if not x:s.add(User(telegram_id=u.id,username=u.username or ''))
        else:x.username=u.username or x.username
        await s.commit()
async def plans():
    async with Session() as s:return (await s.execute(select(Plan).where(Plan.active==True).order_by(Plan.price))).scalars().all()
def plan_buttons(ps):return kb([[InlineKeyboardButton(text=f'{p.name} — {p.price:,} تومان / {p.max_configs} کانفیگ',callback_data=f'plan:{p.id}')] for p in ps])
async def start(m:Message,bot:Bot):
    if not await gate(m,bot):return
    await ensure_user(m.from_user);ps=await plans()
    if not ps:return await m.answer('⚠️ هنوز پلنی تعریف نشده است.')
    rows=[[InlineKeyboardButton(text=f'{p.name} — {p.price:,} تومان / {p.max_configs} کانفیگ',callback_data=f'plan:{p.id}')] for p in ps]
    if settings.monitor_webapp_url:rows.append([InlineKeyboardButton(text='📡 ورود به سیستم پایش',web_app=WebAppInfo(url=settings.monitor_webapp_url))])
    await m.answer(await cfg('welcome','🛍 فروش سیستم پایش کانفیگ\nیک پلن را انتخاب کنید:'),reply_markup=kb(rows))
async def checkjoin(c:CallbackQuery,bot:Bot):
    if await is_joined(bot,c.from_user.id):await c.answer('عضویت تأیید شد ✅');await c.message.edit_text('🛍 پلن را انتخاب کنید:',reply_markup=plan_buttons(await plans()))
    else:await c.answer('هنوز عضو کانال نیستید.',show_alert=True)
async def showplans(c:CallbackQuery):await c.message.edit_text('🛍 انتخاب پلن:',reply_markup=plan_buttons(await plans()));await c.answer()
async def choose(c:CallbackQuery,bot:Bot):
    if not await is_joined(bot,c.from_user.id):return await c.answer('ابتدا عضو کانال شوید.',show_alert=True)
    pid=int(c.data.split(':')[1]);await ensure_user(c.from_user)
    async with Session() as s:
        p=await s.get(Plan,pid);u=(await s.execute(select(User).where(User.telegram_id==c.from_user.id))).scalar_one()
        if not p or not p.active:return await c.answer('پلن نامعتبر است.',show_alert=True)
        o=Order(user_id=u.id,plan_id=p.id);s.add(o);await s.commit()
    card=await cfg('card_number',settings.card_number);holder=await cfg('card_holder',settings.card_holder);instructions=await cfg('payment_instructions',settings.payment_instructions or 'پس از واریز رسید را ارسال کنید.')
    await c.message.edit_text(f'💳 {p.name}\nقیمت: {p.price:,} تومان\nسقف: {p.max_configs} کانفیگ\n\nشماره کارت: {card}\nبه نام: {holder}\n\n{instructions}\n\nسپس رسید را همینجا ارسال کنید.',reply_markup=kb([[InlineKeyboardButton(text='بازگشت',callback_data='plans')]]));await c.answer()
async def receipt(m:Message,bot:Bot):
    if not await gate(m,bot):return
    async with Session() as s:
        u=(await s.execute(select(User).where(User.telegram_id==m.from_user.id))).scalar_one_or_none()
        if not u:return
        o=(await s.execute(select(Order).where(Order.user_id==u.id,Order.status=='pending').order_by(Order.id.desc()))).scalars().first()
        if not o:return await m.answer('سفارش بازی برای ارسال رسید ندارید.')
        o.receipt=m.photo[-1].file_id if m.photo else (m.text or m.caption or '');o.status='review';await s.commit();oid=o.id
    await m.answer(f'🧾 رسید سفارش #{oid} ثبت شد و برای بررسی ادمین ارسال می‌شود.')
    for aid in settings.admins:
        try:await bot.send_message(aid,f'🧾 سفارش #{oid}\nکاربر: {m.from_user.id}',reply_markup=kb([[InlineKeyboardButton(text='✅ تأیید',callback_data=f'approve:{oid}'),InlineKeyboardButton(text='❌ رد',callback_data=f'reject:{oid}')]]))
        except Exception:log.exception('failed to notify admin %s',aid)
async def monitor_entitlement(telegram_id,max_configs,days):
    if not settings.monitor_api_url or not settings.monitor_api_token:return None
    endpoint=settings.monitor_api_url.rstrip('/')+'/api/seller/entitlements';headers={'X-Seller-Token':settings.monitor_api_token}
    async with httpx.AsyncClient(timeout=20) as client:
        r=await client.post(endpoint,json={'telegram_id':telegram_id,'max_configs':max_configs,'days':days},headers=headers);r.raise_for_status();return r.json()
async def approve(c:CallbackQuery,bot:Bot):
    if c.from_user.id not in settings.admins:return
    oid=int(c.data.split(':')[1])
    async with Session() as s:
        o=await s.get(Order,oid)
        if not o or o.status!='review':return await c.answer('قبلاً پردازش شده.',show_alert=True)
        p=await s.get(Plan,o.plan_id);u=await s.get(User,o.user_id);o.status='paid';o.paid_at=datetime.now(timezone.utc);sub=Subscription(user_id=o.user_id,plan_id=p.id,config_count=0,expires_at=datetime.now(timezone.utc)+timedelta(days=p.days));s.add(sub);await s.commit()
    monitor=None;err=None
    try:monitor=await monitor_entitlement(u.telegram_id,p.max_configs,p.days)
    except Exception as e:err=e;log.exception('monitor entitlement failed')
    msg=f'✅ پرداخت سفارش #{oid} تأیید شد.\n📡 پلن پایش: {p.name}\nظرفیت: {p.max_configs} کانفیگ\nاعتبار: {p.days} روز'
    if monitor:msg+='\n\nبرای افزودن و پایش کانفیگ‌ها از دکمه «ورود به سیستم پایش» استفاده کنید.'
    elif settings.monitor_api_url:msg+='\n\n⚠️ فعال‌سازی سیستم پایش ناموفق بود؛ تنظیمات Monitor API را بررسی کنید.'
    await bot.send_message(u.telegram_id,msg);await c.message.edit_text(f'سفارش #{oid} تأیید شد.');await c.answer()
async def reject(c:CallbackQuery,bot:Bot):
    if c.from_user.id not in settings.admins:return
    oid=int(c.data.split(':')[1])
    async with Session() as s:
        o=await s.get(Order,oid)
        if o:o.status='rejected';await s.commit()
    await c.message.edit_text(f'سفارش #{oid} رد شد.');await c.answer()
async def monitor_cmd(m:Message):
    if settings.monitor_webapp_url:await m.answer('📡 سیستم پایش کانفیگ',reply_markup=kb([[InlineKeyboardButton(text='ورود به پایش',web_app=WebAppInfo(url=settings.monitor_webapp_url))]]))
    else:await m.answer('⚠️ آدرس Monitor WebApp تنظیم نشده است.')
async def admin(m:Message):
    if m.from_user.id in settings.admins:await m.answer('/setcard شماره | نام\n/setjoin @channel | https://t.me/channel\n/setjoinoff\n/setjoinon\n/setwelcome متن\n/setpayment متن\n/monitor\n/orders\n/status')
async def setcard(m:Message):
    if m.from_user.id in settings.admins:
        a,b=parse_pair(m.text.partition(' ')[2]);await setcfg('card_number',a);await setcfg('card_holder',b);await m.answer('✅ ذخیره شد.')
async def setjoin(m:Message):
    if m.from_user.id in settings.admins:
        a,b=parse_pair(m.text.partition(' ')[2]);await setcfg('force_join_channel',a);await setcfg('force_join_channel_url',b);await setcfg('force_join_enabled','true');await m.answer('✅ فعال شد.')
async def togglejoin(m:Message,on):
    if m.from_user.id in settings.admins:await setcfg('force_join_enabled',str(on).lower());await m.answer('وضعیت تغییر کرد.')
async def settext(m:Message,key,label):
    if m.from_user.id in settings.admins:await setcfg(key,m.text.partition(' ')[2]);await m.answer(f'✅ {label} ذخیره شد.')
async def orders(m:Message):
    if m.from_user.id not in settings.admins:return
    async with Session() as s:os=(await s.execute(select(Order).order_by(Order.id.desc()).limit(20))).scalars().all()
    await m.answer('\n'.join(f'#{o.id} — {o.status} — user:{o.user_id}' for o in os) or 'سفارشی نیست.')
async def status(m:Message):
    if m.from_user.id in settings.admins:await m.answer(f'Bot فعال\nAdmin IDs: {len(settings.admins)}\nMonitor API: {"configured" if settings.monitor_api_url and settings.monitor_api_token else "not configured"}')
async def run_polling(dp,bot):
    await bot.delete_webhook(drop_pending_updates=False);me=await bot.get_me();log.info('Seller bot connected as @%s (%s)',me.username,me.id);await dp.start_polling(bot)
def build_bot():
    bot=Bot(settings.bot_token);dp=Dispatcher();dp.message.register(start,Command('start'));dp.callback_query.register(checkjoin,F.data=='checkjoin');dp.callback_query.register(showplans,F.data=='plans');dp.callback_query.register(choose,F.data.startswith('plan:'));dp.message.register(receipt,F.photo|F.text);dp.callback_query.register(approve,F.data.startswith('approve:'));dp.callback_query.register(reject,F.data.startswith('reject:'));dp.message.register(admin,Command('admin'));dp.message.register(monitor_cmd,Command('monitor'));dp.message.register(setcard,Command('setcard'));dp.message.register(setjoin,Command('setjoin'));dp.message.register(lambda m:togglejoin(m,False),Command('setjoinoff'));dp.message.register(lambda m:togglejoin(m,True),Command('setjoinon'));dp.message.register(lambda m:settext(m,'welcome','متن خوشامد'),Command('setwelcome'));dp.message.register(lambda m:settext(m,'payment_instructions','متن پرداخت'),Command('setpayment'));dp.message.register(orders,Command('orders'));dp.message.register(status,Command('status'));return type('Runner',(),{'start':lambda self:run_polling(dp,bot)})()
