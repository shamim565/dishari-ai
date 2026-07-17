# Demo Script — Dishari AI (HSIA Dhaka kiosk)

A ~10 minute live demonstration. One **kiosk screen** (the app itself) and one **laptop** (operator/control).

> আপনার টিকিট দেখান। বাকিটা AI আপনাকে পথ দেখাবে।

---

## 0. Preparation (5 minutes before)

```bash
uv run manage.py demo_setup      # seeds flights + layout, generates tickets + markers
uv run manage.py runserver 0.0.0.0:8000
```

1. **Kiosk screen** (Chrome, fullscreen) → open `http://localhost:8000/` — the dashboard opens directly
2. **Laptop** → open `http://localhost:8000/ops/` and keep it on screen (PIN `1234`)
3. Optional: print `demo_assets/qr_markers/marker_sheet.html` and place location markers around the room
4. **Phone ticket demo**: keep the kiosk and the demo phone on the **same Wi-Fi** and set `BASE_URL=http://<laptop-LAN-IP>:8000` in `.env` (e.g. `http://192.168.1.20:8000`), then restart the server — the QR link must open on the phone
5. Optional keys in `.env` for full AI + voice:
   - `OPENAI_API_KEY` / `GEMINI_API_KEY` — free-form AI answers
   - `AZURE_SPEECH_KEY` + region — guaranteed bn-BD neural voice
   - Without keys the demo still runs fully (demo answers + device voice)
6. Voice demo: tap the mic once (Chrome requires one gesture) — greeting plays, then it is hands-free

---

## 1. Walk up — one screen, everything (30 s)

1. The kiosk is a single page: the **voice companion lives permanently on the left** (big mic — tap it once and it greets you), and everything else — ticket, journey, map, arrival, notifications — swaps **in place on the right** without ever reloading the assistant
2. Tap the mic → the assistant **speaks first**: *"আসসালামু আলাইকুম! … বলুন — কী জানতে চান?"* → listening starts automatically
3. Say *"আমার গেট কোথায়?"* → the answer is spoken and the conversation continues hands-free; **🔁 আবার শুনুন** replays the last answer; **⏹** ends the voice session

---

## 2. Ticket → Verified journey (1 min)

1. Tap **টিকিট স্ক্যান করুন** → the kiosk shows a **QR code** (it never takes the photo itself)
2. Scan the QR with a **personal phone** (same Wi-Fi) → the upload page opens in the phone browser:
   - **With AI key**: photograph the printed ticket, or open `demo_assets/tickets/BG147_DXB.png` on a second screen and photograph that → AI reads it live
   - **Without key / no phone**: tap **ডেমো টিকিট দেখুন** under the QR → pick **BG147 · Dhaka → Dubai 19:30** from the modal
3. The phone shows *"টিকিট পাওয়া গেছে"* — and the kiosk switches **by itself** to the journey: flight, counters 17-20 · Block A, seat, PNR

---

## 3. Journey dashboard — "এখন আমি কী করব?" (1 min)

1. Show the **এখন করুন** card: *"চেক-ইন কাউন্টারে যান"* + "চেক-ইন এখনো শুরু হয়নি" warning
2. Show the 3 countdowns (departure / boarding / leave-for-gate) and the journey timeline
3. Say: *"এটাই মূল পার্থক্য — ব্যবহারকারী খুঁজতে হয় না, সিস্টেম জানে তার পরের কাজ কী।"*

**Operator twist:** on the laptop tap **Check-in open** for BG147. Within ~10 seconds the phone shows a toast and **speaks**: *"আপনার ফ্লাইটের চেক-ইন শুরু হয়েছে। এখন 17-20, ব্লক A-তে যান।"*

---

## 4. Navigation + QR position (1 min)

1. On the kiosk tap **পথ দেখান** → directions with map route, step list in Bangla, and the **signage card** to look for
2. Scan a location QR marker (or open `/scan/A01/`) → *"আপনার অবস্থান আপডেট হয়েছে"*
3. Ask the voice assistant: *"ইমিগ্রেশন কোথায়?"* → spoken Bangla answer with the route

---

## 5. Voice AI — a continuous voice conversation (1–2 min)

1. The dashboard's left panel is a **pure voice assistant** — no chat text anywhere; just the mic and state
2. Tap the mic **once**: the assistant speaks first — *"আসসালামু আলাইকুম! আমি আপনার এয়ারপোর্ট সঙ্গী। বলুন — কী জানতে চান?"* — then starts listening by itself
3. Speak: *"আমার গেট কোথায়?"* → the reply is **spoken back** → the mic re-opens automatically: **the conversation just continues, hands-free, until you stop it**
4. Interrupt anytime: tap the mic while it is speaking (barge-in) and ask something else
5. Silence is safe: three quiet turns pause the conversation with **"আবার শুরু করুন"**; tap to resume. The red **⏹ button** ends the voice session; **🔁 আবার শুনুন** replays the last answer
6. Language: the header **English/বাংলা** pill switches the whole kiosk instantly
7. Point out: answers use **only airport data** — the AI never invents a gate or time
