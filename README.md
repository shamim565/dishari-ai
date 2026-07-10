# Dishari AI — Airport Travel Partner

An AI-powered travel companion that recognizes a passenger's flight and personally guides them from airport entry to boarding — in Bangla and English, voice-first.

*প্রবেশ থেকে বোর্ডিং — আপনার এআই পথসঙ্গী।*

**Kiosk MVP demo** — a shared airport kiosk at Hazrat Shahjalal International Airport (DAC): a pure voice assistant on the left, ticket scanning and journey tools on the right. One screen, walk up and talk.

> **Presenting this? Read [DEMO_SCRIPT.md](DEMO_SCRIPT.md)** — the full 10-minute live demo script.

## Stack

| Layer | Choice |
|---|---|
| Runtime | Python 3.14 (uv) + Django 6.1 |
| UI | Django templates + htmx + Alpine.js + Tailwind CSS (vendored), mobile-first PWA |
| Database | SQLite (demo) |
| Vision (ticket) | Gemini / GPT — env-switchable (Sprint 2) |
| Chat | Gemini / GPT — env-switchable (Sprint 5) |
| Voice | Web Speech API + Azure Speech bn-BD Neural — guaranteed Bangla (Sprint 5) |

## Quickstart

```bash
uv sync
cp .env.example .env            # or keep the provided .env
uv run manage.py migrate
uv run manage.py demo_setup     # seeds flights + layout, generates tickets, markers, icons
uv run manage.py runserver
```

Open http://localhost:8000 — the kiosk dashboard opens directly: tap the mic and the assistant greets you.

> **Deploying to the VPS?** The kiosk runs at `dishari.tourismbangladesh.live` — follow [docs/deployment-vps.md](docs/deployment-vps.md).

## The single-page kiosk

One screen, two zones, never navigates:

- **Left — Companion Band**: the voice assistant lives in a persistent iframe; it keeps listening and talking no matter what changes on the right
- **Right — the active panel**: ticket · journey · map · navigate · lost · arrival · notifications, switched in place via the bottom dock (htmx) — the URL updates but the page never reloads, so a voice conversation survives every click, scan, and "Done"
- **Bottom dock**: ম্যাপ / ট্রান্সজিট ও আগমন / বিজ্ঞপ্তি tiles; the brand logo returns to the default panel (journey if scanned, else ticket)

## Demo checklist — Kiosk dashboard

1. Open http://localhost:8000/ — the dashboard opens directly (no portal, no language screen; **বাংলা** by default)
2. Left: pure voice assistant — big mic with **শুরু করতে ট্যাপ করুন**
3. Right: **টিকিট স্ক্যান করুন** card + tiles **এয়ারপোর্ট ম্যাপ · ট্রান্সজিট ও আগমন · বিজ্ঞপ্তি**
4. Header: **সেশন শেষ করুন** · bell · **English/বাংলা** toggle — the whole kiosk switches instantly
5. Bottom nav: **হোম · যাত্রা**
6. Tap the mic once → greeting spoken → continuous hands-free voice session; **⏹** ends it, **🔁 আবার শুনুন** replays the last answer

## Demo checklist — Sprint 2 (Ticket Intelligence)

Prerequisite: `uv run manage.py seed_demo`

1. Home → **টিকিট স্ক্যান করুন** → the kiosk shows a **QR code** (the kiosk never takes ticket photos itself)
2. No API key configured → amber demo-mode banner appears (expected)
3. Scan the QR with a phone (same Wi-Fi, `BASE_URL` = laptop LAN IP) → the upload page opens in the phone browser
4. On the phone: tap **ছবি তুলুন** / **গ্যালারি থেকে দিন** with `demo_assets/tickets/BG147_DXB.png` → AI extraction → the phone confirms and **the kiosk switches itself to the journey**
5. The kiosk shows the personalized journey card + welcome, `Rahim Uddin`
6. No phone handy? Tap **ডেমো টিকিট দেখুন** under the QR and pick **BG147 Dhaka → Dubai** from the modal → same journey on the kiosk
7. Language toggle works on every new screen; the phone page follows the kiosk language automatically
8. Error paths: upload a non-image file on the phone → bilingual error banner; unknown flight → "could not find this flight"

### Switching AI providers (no code change)

```env
VISION_PROVIDER=gemini        # or: openai
VISION_MODEL=gemini-2.5-flash # or: gpt-4o-mini
GEMINI_API_KEY=...
OPENAI_API_KEY=...
```

If the configured provider key is missing, the layer falls back to the other provider; if neither key exists, demo mode is shown. Every scan is logged to `TicketScan` (visible in Django admin) for later analytics.

## Demo checklist — Sprint 3 (Journey Engine + Dashboard)

1. Start a journey (demo ticket **BG147 Dubai 19:30** or ticket photo)
2. Verified screen → **Continue** → back on the dashboard, the **right side** now shows your journey:
   - Flight strip with live status chip, counters, block, seat
   - **এখন করুন** hero card: current task in simple Bangla ("চেক-ইন কাউন্টারে যান") + wait warning since check-in is not open yet
   - Countdowns: departure 19:30 / boarding starts 18:45 / leave for gate 18:23, each with time remaining; walk time note
   - Journey timeline: ✅ entry → ▶ check-in → immigration → security → gate → boarding
3. Tap **সম্পন্ন — পরের ধাপ** to advance stages — task, timeline, and gate info update each step
   (wait state changes to boarding task once flight status is BOARDING — operator sets this in Sprint 6)
4. Tap **ধাপ পিছিয়ে যান** to step back — useful during demos
5. Advance to the end → green "যাত্রা সম্পন্ন — শুভ যাত্রা!" completed state
6. The bottom dock holds ম্যাপ / ট্রান্সজিট ও আগমন / বিজ্ঞপ্তি; language toggle switches the whole kiosk to English

## Demo checklist — Sprint 4 (Indoor Navigation + QR Markers)
