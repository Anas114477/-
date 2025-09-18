import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
import random
import aiohttp
from bs4 import BeautifulSoup

# ---------- إعداد البوت ----------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
TOKEN = os.getenv("DISCORD_TOKEN")  # توكن البوت في Replit Secrets
DATA_FILE = "data.json"

# ---------- تحديد الرتب المسموح لها ----------
ROLE_IDS = [123456789012345678, 987654321098765432]  # ضع هنا أيدي الرتب المسموح لها

def has_allowed_role(user: discord.Member) -> bool:
    for role in user.roles:
        if role.id in ROLE_IDS:
            return True
    return False

# ---------- تخزين البيانات ----------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"ads": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"ads": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

DATA = load_data()

# ========== دوال زخرفة النصوص ==========
async def fetch_decorated_text(text, language='arabic'):
    """جلب نصوص مزخرفة من مواقع متخصصة"""
    try:
        async with aiohttp.ClientSession() as session:
            if language == 'arabic':
                url = f"https://zakhrafah.com/?text={text}"
            else:
                url = f"https://zakhrafaasmaa.com/?text={text}"
            
            async with session.get(url) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                decorated_elements = soup.find_all('div', class_='decorated-text')
                if decorated_elements:
                    return decorated_elements[0].text
                return text
    except:
        return text

def basic_decorate(text):
    """زخرفة أساسية كبديل إذا فشل الاتصال بالإنترنت"""
    decorators = {
        'arabic': ['✨ {} ✨', '⦻ {} ⦻', '♕ {} ♕', '⟬ {} ⟭'],
        'english': ['★ {} ★', '✧ {} ✧', '❂ {} ❂', '⬟ {} ⬟']
    }
    lang = 'arabic' if any('\u0600' <= c <= '\u06FF' for c in text) else 'english'
    return random.choice(decorators[lang]).format(text)

# ---------- زخرفة مع دمج أرقام تلقائي ----------
def merge_numbers(text):
    numbers_map_ar = {"ا":"1","ب":"2","ت":"3","ح":"7","س":"5","ل":"1","م":"8","ن":"9","ه":"6","و":"0","ي":"4"}
    numbers_map_en = {"a":"4","b":"8","e":"3","i":"1","o":"0","s":"5","t":"7"}
    new_text = ""
    for ch in text:
        low = ch.lower()
        if '\u0600' <= ch <= '\u06FF':
            new_text += numbers_map_ar.get(ch, ch)
        else:
            new_text += numbers_map_en.get(low, ch)
    return new_text

# ---------- اختيار القناة + أزرار الإرسال ----------
class ChannelSelect(discord.ui.View):
    def __init__(self, user_id, decorated):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.decorated = decorated
        options = []
        for ch in bot.get_all_channels():
            if isinstance(ch, discord.TextChannel):
                options.append(discord.SelectOption(label=ch.name, value=str(ch.id)))
        self.add_item(ChannelDropdown(options, user_id, decorated))

class ChannelDropdown(discord.ui.Select):
    def __init__(self, options, user_id, decorated):
        super().__init__(placeholder="اختر قناة", options=options[:25])
        self.user_id = user_id
        self.decorated = decorated

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ ليس لك.", ephemeral=True)
            return
        channel_id = int(self.values[0])
        channel = bot.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("❌ القناة غير موجودة.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"📢 إرسال الإعلان في {channel.mention}:",
            view=ConfirmSend(self.user_id, self.decorated, channel),
            ephemeral=True
        )

class ConfirmSend(discord.ui.View):
    def __init__(self, user_id, decorated, channel):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.decorated = decorated
        self.channel = channel

    @discord.ui.button(label="مع منشن", style=discord.ButtonStyle.danger)
    async def send_with_mention(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ ليس لك.", ephemeral=True)
            return
        await self.channel.send(f"||@everyone x @here||\n{self.decorated}")
        log_ad(interaction.guild.id, self.user_id, self.channel.id, self.decorated, True)
        await interaction.response.send_message("✅ تم الإرسال مع منشن.", ephemeral=True)

    @discord.ui.button(label="بدون منشن", style=discord.ButtonStyle.success)
    async def send_without_mention(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ ليس لك.", ephemeral=True)
            return
        await self.channel.send(self.decorated)
        log_ad(interaction.guild.id, self.user_id, self.channel.id, self.decorated, False)
        await interaction.response.send_message("✅ تم الإرسال بدون منشن.", ephemeral=True)

def log_ad(guild_id, user_id, channel_id, content, mention):
    DATA.setdefault("ads", []).append({
        "guild_id": guild_id,
        "user_id": user_id,
        "channel_id": channel_id,
        "content": content,
        "mention": mention,
        "timestamp": datetime.utcnow().isoformat()
    })
    save_data(DATA)

# ---------- أوامر البوت ----------
@bot.tree.command(name="sell", description="إرسال إعلان مزخرف")
@app_commands.describe(text="النص المراد إرساله")
async def sell(interaction: discord.Interaction, text: str):
    member = interaction.user
    if not isinstance(member, discord.Member) or not has_allowed_role(member):
        await interaction.response.send_message("❌ ليس لديك الصلاحية لاستخدام هذا الأمر.", ephemeral=True)
        return
    # جلب النص المزخرف من الموقع أولًا
    decorated = await fetch_decorated_text(text)
    if decorated == text:
        decorated = basic_decorate(text)
    decorated = merge_numbers(decorated)
    await interaction.response.send_message(
        f"✅ تم زخرفة النص.\n📝 `{decorated}`\nاختر القناة للإرسال:",
        view=ChannelSelect(member.id, decorated),
        ephemeral=True
    )

@bot.tree.command(name="ads_log", description="عرض آخر الإعلانات المسجلة")
async def ads_log(interaction: discord.Interaction):
    member = interaction.user
    if not isinstance(member, discord.Member) or not has_allowed_role(member):
        await interaction.response.send_message("❌ ليس لديك الصلاحية لاستخدام هذا الأمر.", ephemeral=True)
        return
    guild_ads = [ad for ad in DATA.get("ads", []) if ad["guild_id"] == interaction.guild_id]
    if not guild_ads:
        await interaction.response.send_message("📭 لا توجد إعلانات مسجلة لهذا السيرفر.", ephemeral=True)
        return
    last_ads = guild_ads[-5:]
    msg_lines = []
    for ad in reversed(last_ads):
        user = interaction.guild.get_member(ad["user_id"])
        username = user.mention if user else f"<@{ad['user_id']}>"
        channel = interaction.guild.get_channel(ad["channel_id"])
        channel_mention = channel.mention if channel else "#deleted"
        mention_txt = "مع منشن" if ad["mention"] else "بدون منشن"
        msg_lines.append(
            f"👤 {username}\n📢 {mention_txt}\n📺 {channel_mention}\n📝 {ad['content']}\n🕒 {ad['timestamp']}\n"
        )
    await interaction.response.send_message("\n".join(msg_lines), ephemeral=True)

# ---------- keep_alive لخادم Replit ----------
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_server():
    server_address = ("", 8080)
    httpd = HTTPServer(server_address, SimpleHandler)
    httpd.serve_forever()

Thread(target=run_server).start()

# ---------- تشغيل البوت ----------
@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")

bot.run(TOKEN)
