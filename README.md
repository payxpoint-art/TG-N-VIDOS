# Telegram Channel Backup Tool (channel se channel, Google Drive nahi chahiye)

Ab Google Drive ka jhanjhat khatam. Tool aise kaam karta hai:
1. Source channel select karo (jiska backup lena hai)
2. Destination channel/group select karo (jaha backup jayega)
3. Tool har video/photo/file ko pehle apne server pe download karega, fir usse
   destination channel me naya message bana ke bhej dega (forward nahi — kyunki
   forwarding off hai, isliye download+upload tarika use ho raha hai)
4. Dashboard pe live logs aur stats dikhte rahenge (kitna backup hua, koi error
   aaya to turant wahi dikh jayega)

## Step 1 — Telegram API credentials lo
1. `my.telegram.org` pe jao, apne number se login karo
2. "API Development Tools" pe click karo
3. Koi bhi App name daal ke create karo
4. **api_id** aur **api_hash** milega — safe copy kar lo

## Step 2 — Session string banao (apne computer pe, sirf ek baar)
1. Python installed honi chahiye
2. Terminal me:
   ```
   pip install telethon
   ```
3. Isi repo ki `generate_session.py` file apne computer pe rakho, chalao:
   ```
   python generate_session.py
   ```
4. api_id, api_hash daalo, phone number daalo, OTP daalo
5. Jo lambi session string print hogi wo copy kar lo (kisi ke saath share mat karna)

## Step 3 — GitHub pe code push karo
```
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/USERNAME/tg-backup-tool.git
git push -u origin main
```

## Step 4 — Railway pe deploy karo
1. `railway.app` > "New Project" > "Deploy from GitHub repo" > apna repo select karo
2. "Variables" tab me sirf ye 3 daalo:
   ```
   TG_API_ID = <Step 1 wala api_id>
   TG_API_HASH = <Step 1 wala api_hash>
   TG_SESSION_STRING = <Step 2 wali session string>
   ```
3. Deploy hone do

## Step 5 — Domain nikalo aur use karo
1. Railway "Settings" > "Networking" > "Generate Domain"
2. Wo URL kholo — saare groups/channels dikhenge
3. Jis channel ka backup lena hai uske aage "Select" dabao
4. Ab destination list dikhegi — jis channel/group me backup bhejna hai wahan
   "Yaha Backup Karo" dabao
5. Turant niche live stats aur logs dikhne lagenge:
   - Kitne videos/photos/files backup hue
   - Kitne fail hue, aur kyun (exact error line-by-line)
6. Backup background me chalta rahega, browser band kar bhi do to Railway pe
   chalta rahega
7. Beech me ruk jaye to dobara "Select" > "Yaha Backup Karo" dabao — resume
   hoga (last message se aage se chalega, dobara shuru nahi hoga)

## Important Notes
- **Rate limit:** Telegram thoda dheere-dheere allow karta hai bahut saara
  download/upload karne pe. 10,000 items me time lagega, chalta rehne dena.
- **Storage:** Railway ka disk temporary hota hai — file download hote hi
  turant send karke delete ho jaati hai, isliye disk space ki dikkat nahi
  aani chahiye.
- **Progress DB:** `backup.db` file me progress save hoti hai. Railway restart
  hone par ye reset ho sakti hai agar Volume attach nahi hai. Agar aisa ho to
  bata dena, Postgres wala permanent solution bana denge.
- **TG_SESSION_STRING** kisi ke saath share mat karna — password jaisa hi
  sensitive hai.
