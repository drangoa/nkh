import asyncio
import json
import os
import time
from telethon import TelegramClient, events, functions, types
from telethon.tl.functions.channels import EditAdminRequest, EditBannedRequest, GetParticipantRequest
from telethon.tl.types import ChatAdminRights, ChatBannedRights, ChannelParticipantAdmin, ChannelParticipantCreator
from telethon.sessions import StringSession

# جلب البيانات من Secrets لضمان الأمان والاستمرارية
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
session_string = os.getenv('SESSION_STRING')
DB_FILE = 'database.json'
TARGET_LINK = 'https://t.me/+pfqNFy_tVE4yMjNi'
# استخدام StringSession بدلاً من الملف العادي ليعمل على الاستضافة السحابية
client = TelegramClient(StringSession(session_string), api_id, api_hash)

# نظام حفظ واستعادة البيانات
if os.path.exists(DB_FILE):
    try:
        with open(DB_FILE, 'r') as f:
            active_cases = json.load(f)
    except: active_cases = {}
else:
    active_cases = {}

def save_db():
    with open(DB_FILE, 'w') as f:
        json.dump(active_cases, f)

ignore_list = {}
allowed_ranks = ["مدير", "منشئ", "المالك", "𝗢𝗪𝗡𝗘𝗥 🎖️"]
disallowed_ranks = ["العضو", "ادمن", "الادمن"]

async def is_target_chat(event):
    try:
        chat = await event.get_chat()

async def check_pending_tasks():
    """مراقبة المهام وإعادة الرتب مع اليوزر تلقائياً"""
    while True:
        current_time = time.time()
        to_delete = []
        for cid, data in list(active_cases.items()):
            if data['status'] == 'verified' and current_time >= data['end_time']:
                try:
                    chat_id, victim_id = int(data['chat_id']), int(data['victim_id'])
                    victim_user = data.get('victim_user', '')
                    rank_to_up = data['original_rank'] if data['original_rank'] not in disallowed_ranks else "مميز"
                    up_cmd = f"رفع {rank_to_up} {victim_user}"
                    
                    if data.get('old_rights'):
                        rights = types.ChatAdminRights(**data['old_rights'])
                        await client(EditAdminRequest(chat_id, victim_id, rights, rank="Admin"))
                    
                    await client.send_message(chat_id, up_cmd)
                    print(f"[+] تم الرفع التلقائي: {up_cmd}")
                    to_delete.append(cid)
                except Exception as e: print(f"[!] خطأ استعادة: {e}")
        
        if to_delete:
            for k in to_delete: del active_cases[k]
            save_db()
        await asyncio.sleep(10)

async def start_verification(event):
    """دالة التحقق بانتظار رد البوت"""
    sender_id = event.sender_id
    chat_id = event.chat_id
    if sender_id in ignore_list and time.time() < ignore_list[sender_id]: return None
    if not event.is_reply: return None

    await event.respond("مسح رتب التسلية")
    await asyncio.sleep(2)
    await event.reply("رتبته")

    loop = asyncio.get_event_loop()
    bot_response_future = loop.create_future()

    @client.on(events.NewMessage(chats=chat_id))
    async def temp_bot_handler(bot_event):
        if "• رتبته هي" in bot_event.text:
            if not bot_response_future.done():
                bot_response_future.set_result(bot_event.text)

    try:
        rank_text = await asyncio.wait_for(bot_response_future, timeout=30)
        client.remove_event_handler(temp_bot_handler)
        if any(dr in rank_text for dr in disallowed_ranks):
            ignore_list[sender_id] = time.time() + 3600
            return None
        for r in allowed_ranks:
            if r in rank_text: return r
        return "العضو"
    except:
        client.remove_event_handler(temp_bot_handler)
        return None

@client.on(events.NewMessage(pattern=r"^ساترن انذار$"))
async def warning_handler(event):
    original_rank = await start_verification(event)
    if not original_rank: return
    reply_msg = await event.get_reply_message()
    victim = await client.get_entity(reply_msg.sender_id)
    v_user = f"@{victim.username}" if victim.username else f"[{victim.id}](tg://user?id={victim.id})"
    
    await client.send_message("me", f"⚠️ مخالفة جديدة من: {v_user}")

    old_rights = None
    try:
        p = await client(GetParticipantRequest(event.chat_id, victim.id))
        if isinstance(p.participant, (ChannelParticipantAdmin, ChannelParticipantCreator)):
            old_rights = p.participant.admin_rights.__dict__
            await client(EditAdminRequest(event.chat_id, victim.id, ChatAdminRights(post_messages=False), rank="نزع مؤقت"))
    except: pass

    await reply_msg.reply("تكم")
    await asyncio.sleep(2)
    await reply_msg.reply("تك")
    await event.reply("يرجى من احد المشرفين كتابة (صح مخالف) لتثبيت التهمه...")

    case_id = f"{event.chat_id}_{victim.id}"
    active_cases[case_id] = {
        'status': 'pending', 'victim_id': victim.id, 'chat_id': event.chat_id,
        'victim_user': v_user, 'old_rights': old_rights, 
        'original_rank': original_rank, 'type': 'انذار', 
        'reply_to': reply_msg.id, 'end_time': 0
    }
    save_db()

@client.on(events.NewMessage(pattern=r"^ساترن كتم$"))
async def mute_handler(event):
    original_rank = await start_verification(event)
    if not original_rank: return
    reply_msg = await event.get_reply_message()
    victim = await client.get_entity(reply_msg.sender_id)
    v_user = f"@{victim.username}" if victim.username else f"[{victim.id}](tg://user?id={victim.id})"
    
    await client.send_message("me", f"🔇 كتم جديد لـ: {v_user}")

    await reply_msg.reply("تكم")
    await asyncio.sleep(2)
    await reply_msg.reply("تك")
    await event.reply("يرجى من احد المشرفين كتابة (صح مخالف) لتثبيت التهمه...")

    case_id = f"{event.chat_id}_{victim.id}"
    active_cases[case_id] = {
        'status': 'pending', 'victim_id': victim.id, 'chat_id': event.chat_id,
        'victim_user': v_user, 'old_rights': None, 
        'original_rank': original_rank, 'type': 'كتم', 
        'reply_to': reply_msg.id, 'end_time': 0
    }
    save_db()

@client.on(events.NewMessage(pattern="^صح مخالف$"))
async def validator(event):
    for cid, data in list(active_cases.items()):
        if data['chat_id'] == event.chat_id and data['status'] == 'pending':
            res_p = await client(GetParticipantRequest(event.chat_id, event.sender_id))
            if isinstance(res_p.participant, (ChannelParticipantAdmin, ChannelParticipantCreator)):
                data['status'] = 'verified'
                data['end_time'] = time.time() + 280 
                if data['type'] == 'انذار':
                    for m in ["انذار", "،", "مد"]:
                        await client.send_message(event.chat_id, m, reply_to=data['reply_to']); await asyncio.sleep(1.5)
                else:
                    await client(EditBannedRequest(event.chat_id, data['victim_id'], ChatBannedRights(until_date=time.time()+600, send_messages=True)))
                    await client.send_message(event.chat_id, "كتم", reply_to=data['reply_to'])
                save_db()
                break

async def start_bot():
    await client.start()
    # تجربة: سيرسل الحساب رسالة لنفسه (Saved Messages) بمجرد التشغيل
    await client.send_message("me", "تم تشغيل ساترن بنجاح وأنا أسمعك الآن!")
    
    print("--- ساترن: نظام الرفع باليوزر مفعّل الآن ---")
    client.loop.create_task(check_pending_tasks())
    
    try:
        await asyncio.wait_for(client.run_until_disconnected(), timeout=280)
    except asyncio.TimeoutError:
        print("--- إعادة تشغيل دورية للحفاظ على الاتصال ---")
        await client.disconnect()
