# Ye script sirf ek baar apne LOCAL computer par chalana hai (Railway par nahi).
# Ye phone number aur OTP mangega, aur ek session string generate karega.
# Wo string Railway env variable TG_SESSION_STRING me daalni hai.

from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = input("API ID: ")
api_hash = input("API Hash: ")

with TelegramClient(StringSession(), int(api_id), api_hash) as client:
    print("\n=== Ye session string copy karo aur Railway me TG_SESSION_STRING me daalo ===\n")
    print(client.session.save())
    print("\n===============================================================\n")
