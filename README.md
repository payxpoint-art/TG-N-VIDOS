# Telegram Channel Backup Tool

## Is version me kya naya hai

1. **Album/Group support** — Agar source me 5 photos/videos ek saath ek
   group me post hui thi, to destination pe bhi wo **ek hi group** me
   jayengi — alag-alag messages nahi banenge.
2. **Video properly playable** — Original video ki duration/quality info
   copy hoti hai, taki destination pe bhi normal Telegram video jaisa hi
   chale (ek tap me play), "file" jaisa dikhke do-do baar click na karna
   pade.
3. **Bade se bada video bhi jayega** — Koi hard size limit nahi (userbot
   2GB+ tak normally handle kar leta hai).
4. **Caption bilkul original jaisa** — Ab sirf original caption + niche
   "Original date" aur ek chhota tracking tag (`SRC_ID`) jata hai, koi extra
   numbering nahi (jaisa pehle tha).
5. **Telegram Bot — single message live update** — Backup start karne ke
   baad bot EK message bhejta hai jo har 8 second me khud update (edit)
   hota rehta hai jab tak backup complete na ho jaye — chat me spam nahi
   hota.
6. **Cross-account resume** — Naye Railway account/deployment pe bhi
   destination channel se khud pata laga leta hai kaha tak backup ho chuka
   tha, dobara se shuru nahi hoga.

---

## Step 1 — Telegram API credentials
`my.telegram.org` > API Development Tools > App banao > **api_id**, **api_hash** milega

## Step 2 — Session string (apna account, ek baar local pe)
```
pip install telethon
python generate_session.py
```

## Step 3 — Telegram Bot banao
1. `@BotFather` ko `/newbot` bhejo, naam/username do
2. **Bot Token** milega
3. Us bot ko Telegram me kholke ek baar **"Start"** dabao

## Step 4 — Apna Owner ID nikalo
`@userinfobot` ko message karo, wo numeric ID bata dega

## Step 5 — `.env` file me values daalo

Chunki repo private hai, seedha `.env` file edit karo:
```
TG_API_ID=23456789
TG_API_HASH=a1b2c3d4e5f6...
TG_SESSION_STRING=1BvcM...
TG_BOT_TOKEN=123456:ABC-DEF1234...
TG_OWNER_ID=123456789
CONCURRENCY=5
BATCH_SIZE=5
```

## Step 6 — GitHub pe push karo
```
git add .
git commit -m "update"
git push
```
Railway automatically redeploy karega — Variables tab me kuch manually
daalne ki zaroorat nahi, code khud `.env` se read kar lega.

⚠️ Ye tarika sirf tab safe hai jab tak repo **private** hai.

---

## Use kaise karo

### Telegram Bot se (recommended)
1. Apne bot ko kholo, `/start` ya `/channels` bhejo
2. Numbered list aayegi — **jis channel ka backup lena hai uska number bhejo**
3. Fir **destination channel ka number bhejo**
4. Backup shuru ho jayega — ek message aayega jo **khud update hota rahega**
   (live progress: Videos/Photos/Files/Texts/Failed count)
5. `/status` bhej ke kabhi bhi summary dekh sakte ho

### Web Dashboard se
Railway domain kholo, channel select karo, destination select karo, live
stats + logs dikhenge.

---

## Important Notes

- **Duplicate-proof + cross-account resume:** Har group/message DB me aur
  khud destination channel me (`SRC_ID` tag) record hota hai. Naya Railway
  account ho ya deployment restart ho, tool khud detect kar leta hai kaha
  tak ho chuka tha.
- **Caption format** ab bilkul simple hai:
  ```
  <original caption agar tha>
  Original date: 05 Sep 2026, 08:15 PM
  SRC_ID:98234
  ```
  `SRC_ID` line ko destination channel se delete/edit mat karna, isi se
  resume feature kaam karta hai.
- **Video quality:** Videos apni original duration/resolution ke sath
  jaate hain, streaming-enabled — normal video jaisa play hoga.
- **Speed:** `CONCURRENCY` (parallel workers) aur `BATCH_SIZE` `.env` me
  tune kar sakte ho. `CONCURRENCY` 8-10 se zyada mat rakhna (Telegram
  FloodWaitError de sakta hai).
- **TG_SESSION_STRING aur TG_BOT_TOKEN** kisi ke saath share mat karna.
- Bot sirf `TG_OWNER_ID` wale account ko respond karta hai — safe hai.
