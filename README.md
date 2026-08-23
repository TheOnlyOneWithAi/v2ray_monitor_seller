# V2Ray Monitor Seller

Telegram sales bot for the V2Ray monitor ecosystem.

## Default plans
- 99,000 تومان — up to 3 configs
- 199,000 تومان — up to 10 configs
- 299,000 تومان — up to 27 configs

Plans are stored in the database and can be extended later.

## Features
- Telegram sales flow
- Manual card-payment workflow with receipt review
- Admin approval/rejection
- Forced channel membership with live `getChatMember` checks
- Runtime card-holder/card-number settings
- Runtime welcome/payment text settings
- Web storefront
- SQLite persistence
- systemd deployment
- no manual `.env` editing: installer asks for the bot token and admin IDs and generates runtime secrets

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/TheOnlyOneWithAi/v2ray_monitor_seller/main/install.sh | bash
```

The installer asks for the Telegram bot token and admin Telegram IDs, creates the encryption key, virtualenv, database directory and systemd service.

## Admin commands

`/admin`, `/setcard NUMBER | HOLDER`, `/setjoin @channel | https://t.me/channel`, `/setjoinon`, `/setjoinoff`, `/setwelcome TEXT`, `/setpayment TEXT`, `/orders`, `/status`.

The production design keeps payment verification manual: the bot never pretends to verify a bank transfer automatically.
