# Telegram Channel Backup Tool (to Google Drive)

Poori step-by-step guide neeche hai (Hinglish me).

## Step 1 — Telegram API credentials lo
1. Browser me `my.telegram.org` kholo, apne number se login karo.
2. "API Development Tools" pe click karo.
3. Koi bhi App name daal ke create karo.
4. `api_id` aur `api_hash` mil jayega — safe jagah copy kar lo.

## Step 2 — Google Drive API setup karo
1. `console.cloud.google.com` pe jao, naya project banao.
2. "APIs & Services" > "Library" me jao, "Google Drive API" search karke Enable karo.
3. "Credentials" > "Create Credentials" > "Service Account" select karo, koi naam de ke create kar do.
4. Service account bann jaye to us par click karo > "Keys" tab > "Add Key" > "Create new key" > JSON select karo. Ek JSON file download hogi — isi ke andar `client_email` aur private key hai.
5. Google Drive khol ke ek naya folder banao (jaha backup jayega).
6. Us folder ko share karo — JSON file ke andar jo `client_email` hai (kuch aisa dikhega: `xxxx@xxxx.iam.gserviceaccount.com`) usko "Editor" access do.
7. Folder khol ke URL se folder ID copy kar lo: `https://drive.google.com/drive/folders/YEH_WALA_ID`

## Step 3 — Local computer par session string banao
1. Apne computer par Python install hona chahiye.
2. Ek folder banao, usme sirf ye command chalao:
   ```
   pip install telethon
   ```
3. Is repo ki `generate_session.py` file wahi copy karo aur chalao:
   ```
   python generate_session.py
   ```
4. Ye API ID, API Hash maangega (Step 1 wale), fir aapka phone number aur OTP maangega.
5. Login hone ke baad ek lambi session string print hogi — pura copy kar lo. (Ye string kisi ke saath share mat karna, isse aapke account ka full access milta hai)

## Step 4 — GitHub par code push karo
1. GitHub par naya repository banao (e.g. `tg-backup-tool`).
2. Is zip ke andar ki saari files us repo me push kar do:
   ```
   git init
   git add .
   git commit -m "initial commit"
   git branch -M main
   git remote add origin https://github.com/USERNAME/tg-backup-tool.git
   git push -u origin main
   ```
   (`.env` file kabhi push mat karna — `.gitignore` me already excluded hai)

## Step 5 — Railway par deploy karo
1. `railway.app` par login karo, "New Project" > "Deploy from GitHub repo" select karo.
2. Apna `tg-backup-tool` repo choose karo — Railway apne aap `requirements.txt` aur `Procfile` detect kar lega.
3. Deploy hone ke baad "Variables" tab me jao aur ye sab add karo:
   ```
   TG_API_ID = <Step 1 wala api_id>
   TG_API_HASH = <Step 1 wala api_hash>
   TG_SESSION_STRING = <Step 3 wali session string>
   GOOGLE_SERVICE_ACCOUNT_JSON = <Step 2 wali JSON file ka pura content, ek line me>
   DRIVE_FOLDER_ID = <Step 2 wala folder ID>
   ```
   Note: `GOOGLE_SERVICE_ACCOUNT_JSON` daalte waqt pura JSON content copy karke paste kar do (curly braces samet), bas ismein newlines na ho — JSON ko ek single line me minify kar lena (koi bhi "JSON minifier" online tool se ya text editor me "find & replace" karke newlines hata sakte ho).
4. Variables save karne ke baad Railway automatically redeploy karega.

## Step 6 — Tool use karo
1. Railway "Settings" > "Domains" me jao, "Generate Domain" dabao — aapko ek public URL milega.
2. Wo URL browser me kholo — aapko apne saare Telegram groups/channels ki list dikhegi.
3. Jis channel/group ka backup lena hai uske aage "Backup Start" button dabao.
4. Turant niche live stats dikhne lagenge: kitne videos, photos, files backup hue, aur kitne fail hue.
5. Backup chalta rahega background me, beech me tab band kar do to bhi chalta rahega jab tak Railway service running hai.
6. Agar kabhi backup beech me ruk jaye (Railway restart, error, etc.), to dobara "Backup Start" dabao — ye apne aap last wale message se resume hoga, dobara se shuru nahi karega.

## Important Notes
- Railway ka default filesystem restart hone par reset ho sakta hai — agar aisa hota hai to `backup.db` (progress wali file) delete ho jayegi aur backup dobara shuru se chalega. Isse bachne ke liye Railway me "Volume" attach kar sakte ho `backup.db` ke liye, ya Postgres database use kar sakte ho (bata dena agar ye chahiye, main convert kar dunga).
- 10,000 items hai to backup me time lagega (Telegram rate limits ki wajah se) — chalta rehne dena, ruk-ruk ke chalega automatically.
- Content-protected/forwarding-off channel me agar aap admin ho to bhi media download ho jayega (restriction sirf normal members ke liye hota hai jo Telegram app use karte hain, API se admin access nahi rukta).
- `TG_SESSION_STRING` kisi ke saath share mat karna — jitna important password hai utna hi important ye string bhi hai.
