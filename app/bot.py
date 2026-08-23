import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from sqlalchemy import select

from .config import settings
from .db import Session, Plan, User, Order, Subscription, Setting

log = logging.getLogger(__name__)


def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_pair(text: str) -> tuple[str, str]:
    parts = text.split("|", 1)
    return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""


async def cfg(key: str, default: str = "") -> str:
    async with Session() as session:
        row = await session.get(Setting, key)
        return row.value if row else default


async def setcfg(key: str, value: str) -> None:
    async with Session() as session:
        row = await session.get(Setting, key)
        if row:
            row.value = value
        else:
            session.add(Setting(key=key, value=value))
        await session.commit()


async def is_joined(bot: Bot, uid: int) -> bool:
    enabled = (await cfg("force_join_enabled", str(settings.force_join_enabled).lower())).lower() == "true"
    channel = await cfg("force_join_channel", settings.force_join_channel)
    if not enabled or not channel:
        return True
    try:
        member = await bot.get_chat_member(channel, uid)
        return member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }
    except Exception:
        log.exception("force-join check failed")
        return False


async def gate(message: Message, bot: Bot) -> bool:
    if await is_joined(bot, message.from_user.id):
        return True
    channel = await cfg("force_join_channel", settings.force_join_channel)
    url = await cfg("force_join_channel_url", settings.force_join_channel_url)
    if not url and channel.startswith("@"):
        url = f"https://t.me/{channel.lstrip('@')}"
    rows = []
    if url:
        rows.append([InlineKeyboardButton(text="عضویت", url=url)])
    rows.append([InlineKeyboardButton(text="✅ بررسی", callback_data="checkjoin")])
    await message.answer("🔒 ابتدا عضو کانال شوید.", reply_markup=kb(rows))
    return False


async def ensure_user(user) -> None:
    async with Session() as session:
        row = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one_or_none()
        if not row:
            session.add(User(telegram_id=user.id, username=user.username or ""))
        else:
            row.username = user.username or row.username
        await session.commit()


async def plans():
    async with Session() as session:
        return (await session.execute(select(Plan).where(Plan.active.is_(True)).order_by(Plan.price))).scalars().all()


def plan_buttons(plan_rows):
    return kb([
        [InlineKeyboardButton(
            text=f"{plan.name} — {plan.price:,} {settings.currency_label} / {plan.max_configs} کانفیگ",
            callback_data=f"plan:{plan.id}",
        )]
        for plan in plan_rows
    ])


async def start(message: Message, bot: Bot):
    if not await gate(message, bot):
        return
    await ensure_user(message.from_user)
    plan_rows = await plans()
    if not plan_rows:
        return await message.answer("⚠️ هنوز پلنی تعریف نشده است.")
    rows = [[InlineKeyboardButton(
        text=f"{plan.name} — {plan.price:,} {settings.currency_label} / {plan.max_configs} کانفیگ",
        callback_data=f"plan:{plan.id}",
    )] for plan in plan_rows]
    if settings.monitor_webapp_url:
        rows.append([InlineKeyboardButton(text="📡 ورود به سیستم پایش", web_app=WebAppInfo(url=settings.monitor_webapp_url))])
    welcome = await cfg("welcome", "🛍 فروش سیستم پایش کانفیگ\nیک پلن را انتخاب کنید:")
    await message.answer(welcome, reply_markup=kb(rows))


async def checkjoin(callback: CallbackQuery, bot: Bot):
    if await is_joined(bot, callback.from_user.id):
        await callback.answer("عضویت تأیید شد ✅")
        await callback.message.edit_text("🛍 پلن را انتخاب کنید:", reply_markup=plan_buttons(await plans()))
    else:
        await callback.answer("هنوز عضو کانال نیستید.", show_alert=True)


async def showplans(callback: CallbackQuery):
    await callback.message.edit_text("🛍 انتخاب پلن:", reply_markup=plan_buttons(await plans()))
    await callback.answer()


async def choose(callback: CallbackQuery, bot: Bot):
    if not await is_joined(bot, callback.from_user.id):
        return await callback.answer("ابتدا عضو کانال شوید.", show_alert=True)
    try:
        plan_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await callback.answer("پلن نامعتبر است.", show_alert=True)

    await ensure_user(callback.from_user)
    async with Session() as session:
        plan = await session.get(Plan, plan_id)
        user = (await session.execute(select(User).where(User.telegram_id == callback.from_user.id))).scalar_one()
        if not plan or not plan.active:
            return await callback.answer("پلن نامعتبر است.", show_alert=True)
        order = Order(user_id=user.id, plan_id=plan.id)
        session.add(order)
        await session.commit()

    card = await cfg("card_number", settings.card_number)
    holder = await cfg("card_holder", settings.card_holder)
    instructions = await cfg("payment_instructions", settings.payment_instructions or "پس از واریز رسید را ارسال کنید.")
    await callback.message.edit_text(
        f"💳 {plan.name}\nقیمت: {plan.price:,} {settings.currency_label}\n"
        f"سقف: {plan.max_configs} کانفیگ\n\nشماره کارت: {card}\nبه نام: {holder}\n\n"
        f"{instructions}\n\nسپس رسید را همینجا ارسال کنید.",
        reply_markup=kb([[InlineKeyboardButton(text="بازگشت", callback_data="plans")]]),
    )
    await callback.answer()


async def receipt(message: Message, bot: Bot):
    if not await gate(message, bot):
        return
    async with Session() as session:
        user = (await session.execute(select(User).where(User.telegram_id == message.from_user.id))).scalar_one_or_none()
        if not user:
            return
        order = (
            await session.execute(
                select(Order)
                .where(Order.user_id == user.id, Order.status == "pending")
                .order_by(Order.id.desc())
            )
        ).scalars().first()
        if not order:
            return await message.answer("سفارش بازی برای ارسال رسید ندارید.")
        order.receipt = message.photo[-1].file_id if message.photo else (message.text or message.caption or "")
        order.status = "review"
        await session.commit()
        order_id = order.id

    await message.answer(f"🧾 رسید سفارش #{order_id} ثبت شد و برای بررسی ادمین ارسال می‌شود.")
    for admin_id in settings.admins:
        try:
            await bot.send_message(
                admin_id,
                f"🧾 سفارش #{order_id}\nکاربر: {message.from_user.id}",
                reply_markup=kb([[
                    InlineKeyboardButton(text="✅ تأیید", callback_data=f"approve:{order_id}"),
                    InlineKeyboardButton(text="❌ رد", callback_data=f"reject:{order_id}"),
                ]]),
            )
        except Exception:
            log.exception("failed to notify admin %s", admin_id)


async def monitor_entitlement(telegram_id: int, max_configs: int, days: int):
    if not settings.monitor_api_url or not settings.monitor_api_token:
        return None
    endpoint = settings.monitor_api_url.rstrip("/") + "/api/seller/entitlements"
    headers = {"X-Seller-Token": settings.monitor_api_token}
    payload = {"telegram_id": telegram_id, "max_configs": max_configs, "days": days}
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
        response = await client.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


async def approve(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in settings.admins:
        return
    try:
        order_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await callback.answer("سفارش نامعتبر است.", show_alert=True)

    async with Session() as session:
        order = await session.get(Order, order_id)
        if not order or order.status != "review":
            return await callback.answer("قبلاً پردازش شده.", show_alert=True)
        plan = await session.get(Plan, order.plan_id)
        user = await session.get(User, order.user_id)
        if not plan or not user:
            return await callback.answer("اطلاعات سفارش ناقص است.", show_alert=True)
        order.status = "paid"
        order.paid_at = datetime.now(timezone.utc)
        subscription = Subscription(
            user_id=order.user_id,
            plan_id=plan.id,
            config_count=0,
            expires_at=datetime.now(timezone.utc) + timedelta(days=plan.days),
        )
        session.add(subscription)
        await session.commit()
        telegram_id = user.telegram_id
        plan_name = plan.name
        max_configs = plan.max_configs
        days = plan.days

    monitor = None
    if settings.monitor_api_url and settings.monitor_api_token:
        try:
            monitor = await monitor_entitlement(telegram_id, max_configs, days)
        except Exception:
            log.exception("monitor entitlement activation failed for user %s", telegram_id)

    message = (
        f"✅ پرداخت سفارش #{order_id} تأیید شد.\n📡 پلن پایش: {plan_name}\n"
        f"ظرفیت: {max_configs} کانفیگ\nاعتبار: {days} روز"
    )
    if monitor:
        message += "\n\nبرای افزودن و پایش کانفیگ‌ها از دکمه «ورود به سیستم پایش» استفاده کنید."
    elif settings.monitor_api_url:
        message += "\n\n⚠️ فعال‌سازی سیستم پایش ناموفق بود؛ تنظیمات Monitor API را بررسی کنید."
    else:
        message += "\n\n⚠️ Monitor API تنظیم نشده است."
    await bot.send_message(telegram_id, message)
    await callback.message.edit_text(f"سفارش #{order_id} تأیید شد.")
    await callback.answer()


async def reject(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in settings.admins:
        return
    try:
        order_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await callback.answer("سفارش نامعتبر است.", show_alert=True)
    async with Session() as session:
        order = await session.get(Order, order_id)
        if order:
            order.status = "rejected"
            await session.commit()
    await callback.message.edit_text(f"سفارش #{order_id} رد شد.")
    await callback.answer()


async def monitor_cmd(message: Message):
    if settings.monitor_webapp_url:
        await message.answer(
            "📡 سیستم پایش کانفیگ",
            reply_markup=kb([[InlineKeyboardButton(text="ورود به پایش", web_app=WebAppInfo(url=settings.monitor_webapp_url))]]),
        )
    else:
        await message.answer("⚠️ آدرس Monitor WebApp تنظیم نشده است.")


async def admin(message: Message):
    if message.from_user.id in settings.admins:
        await message.answer(
            "/setcard شماره | نام\n/setjoin @channel | https://t.me/channel\n"
            "/setjoinoff\n/setjoinon\n/setwelcome متن\n/setpayment متن\n"
            "/monitor\n/orders\n/status"
        )


async def setcard(message: Message):
    if message.from_user.id in settings.admins:
        number, holder = parse_pair(message.text.partition(" ")[2])
        await setcfg("card_number", number)
        await setcfg("card_holder", holder)
        await message.answer("✅ ذخیره شد.")


async def setjoin(message: Message):
    if message.from_user.id in settings.admins:
        channel, url = parse_pair(message.text.partition(" ")[2])
        await setcfg("force_join_channel", channel)
        await setcfg("force_join_channel_url", url)
        await setcfg("force_join_enabled", "true")
        await message.answer("✅ فعال شد.")


async def togglejoin(message: Message, on: bool):
    if message.from_user.id in settings.admins:
        await setcfg("force_join_enabled", str(on).lower())
        await message.answer("وضعیت تغییر کرد.")


async def settext(message: Message, key: str, label: str):
    if message.from_user.id in settings.admins:
        await setcfg(key, message.text.partition(" ")[2])
        await message.answer(f"✅ {label} ذخیره شد.")


async def orders(message: Message):
    if message.from_user.id not in settings.admins:
        return
    async with Session() as session:
        rows = (await session.execute(select(Order).order_by(Order.id.desc()).limit(20))).scalars().all()
    await message.answer("\n".join(f"#{row.id} — {row.status} — user:{row.user_id}" for row in rows) or "سفارشی نیست.")


async def status(message: Message):
    if message.from_user.id in settings.admins:
        await message.answer(
            f"Bot فعال\nAdmin IDs: {len(settings.admins)}\n"
            f"Monitor API: {'configured' if settings.monitor_api_url and settings.monitor_api_token else 'not configured'}"
        )


async def run_polling(dispatcher: Dispatcher, bot: Bot):
    await bot.delete_webhook(drop_pending_updates=False)
    me = await bot.get_me()
    log.info("Seller bot connected as @%s (%s)", me.username, me.id)
    await dispatcher.start_polling(bot, handle_signals=False)


def build_bot():
    settings.validate_runtime()
    bot = Bot(settings.token)
    dispatcher = Dispatcher()
    dispatcher.message.register(start, Command("start"))
    dispatcher.callback_query.register(checkjoin, F.data == "checkjoin")
    dispatcher.callback_query.register(showplans, F.data == "plans")
    dispatcher.callback_query.register(choose, F.data.startswith("plan:"))
    dispatcher.callback_query.register(approve, F.data.startswith("approve:"))
    dispatcher.callback_query.register(reject, F.data.startswith("reject:"))
    dispatcher.message.register(admin, Command("admin"))
    dispatcher.message.register(monitor_cmd, Command("monitor"))
    dispatcher.message.register(setcard, Command("setcard"))
    dispatcher.message.register(setjoin, Command("setjoin"))
    dispatcher.message.register(lambda m: togglejoin(m, False), Command("setjoinoff"))
    dispatcher.message.register(lambda m: togglejoin(m, True), Command("setjoinon"))
    dispatcher.message.register(lambda m: settext(m, "welcome", "متن خوشامد"), Command("setwelcome"))
    dispatcher.message.register(lambda m: settext(m, "payment_instructions", "متن پرداخت"), Command("setpayment"))
    dispatcher.message.register(orders, Command("orders"))
    dispatcher.message.register(status, Command("status"))
    # Receipt handler is intentionally last so it cannot swallow commands.
    dispatcher.message.register(receipt, F.photo | F.text)
    return type("Runner", (), {"start": lambda self: run_polling(dispatcher, bot)})()
