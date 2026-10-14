# ============================================================
# CRYSTAL GAMES BOT — MAIN.PY
# Python 3.12+ | discord.py 2.7.1
# Single-file Discord games bot
# ============================================================

import os
import io
import re
import json
import time
import random
import asyncio
import logging
import hashlib
from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Thread

import discord
from discord.ext import commands
from flask import Flask, jsonify

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None

# ============================================================
# CONFIGURATION
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

WIN_POINTS = 10
PARTICIPATION_POINTS = 2
GAME_DURATION = 30
MAFIA_MIN_PLAYERS = 4
MAFIA_MAX_PLAYERS = 30
ROULETTE_MAX_PLAYERS = 50

DATABASE_FILE = "crystal_games.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("crystal-games")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="+",
    intents=intents,
    help_command=None,
)

app = Flask(__name__)


@app.route("/")
def home():
    return "CRYSTAL Games Bot is Online!"


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "ready": bot.is_ready(),
        "bot": str(bot.user) if bot.user else None,
    })


def run_web():
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)


# ============================================================
# PERSISTENT DATA
# ============================================================

def load_data():
    if not os.path.exists(DATABASE_FILE):
        return {"scores": {}, "games_played": {}}

    try:
        with open(DATABASE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        data.setdefault("scores", {})
        data.setdefault("games_played", {})
        return data
    except (OSError, json.JSONDecodeError):
        log.exception("Could not load game database")
        return {"scores": {}, "games_played": {}}


DATA = load_data()


def save_data():
    temporary = DATABASE_FILE + ".tmp"

    try:
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(DATA, file, ensure_ascii=False, indent=2)

        os.replace(temporary, DATABASE_FILE)
    except OSError:
        log.exception("Could not save game database")


def score_key(guild_id, user_id):
    return f"{guild_id}:{user_id}"


def add_points(guild_id, user_id, points):
    key = score_key(guild_id, user_id)
    DATA["scores"][key] = DATA["scores"].get(key, 0) + points
    DATA["games_played"][key] = DATA["games_played"].get(key, 0) + 1
    save_data()


def get_points(guild_id, user_id):
    return DATA["scores"].get(score_key(guild_id, user_id), 0)


# ============================================================
# EMBEDS AND HELPERS
# ============================================================

COLOR = discord.Color.from_rgb(90, 200, 255)

def embed(title, description=""):
    result = discord.Embed(
        title=title,
        description=description,
        color=COLOR,
        timestamp=datetime.now(timezone.utc),
    )
    result.set_footer(text="𝗖𝗥𝗬𝗦𝗧𝗔𝗟 store • Games")
    return result


def normalize(text):
    return re.sub(r"\s+", " ", str(text).strip().casefold())


def user_mention(user_id):
    return f"<@{user_id}>"


# ============================================================
# UNIQUE WORDS / UNIQUE IMAGE PUZZLES
# Avoid repeating the same word or puzzle image in a round
# and avoid recent repeats across rounds in this process.
# ============================================================

WORD_BANKS = {
    "animals": [
        "أسد", "نمر", "فيل", "زرافة", "حصان", "جمل", "ذئب",
        "ثعلب", "دب", "أرنب", "سلحفاة", "تمساح", "بطريق",
        "دلفين", "قرش", "صقر", "بومة", "غزال", "كنغر", "قرد",
        "حوت", "نحلة", "فراشة", "عقرب", "أخطبوط", "فهد",
        "باندا", "قنفذ", "ببغاء", "نعامة", "حمامة", "بطة",
        "ماعز", "خروف", "بقرة", "ديك", "دجاجة", "سمكة",
        "ضفدع", "سنجاب", "خفاش", "حمار", "بغل", "يربوع",
        "فقمة", "لاما", "كوالا", "غوريلا", "وحيد القرن",
        "فرس النهر", "سحلية", "ثعبان", "نورس", "غراب",
        "طاووس", "نسر", "سلطعون", "روبيان", "قنديل البحر",
    ],
    "food": [
        "بيتزا", "برجر", "كبسة", "مندي", "مكرونة", "شاورما",
        "فلافل", "حمص", "فول", "سمبوسة", "معصوب", "كنافة",
        "بسبوسة", "لقيمات", "بان كيك", "وافل", "سلطة",
        "شوربة", "سوشي", "لازانيا", "فطيرة", "كريب",
        "آيس كريم", "شوكولاتة", "بسكويت", "تمر", "عسل",
        "جبن", "خبز", "أرز", "دجاج", "سمك", "بطاطس",
        "ذرة", "فشار", "كعكة", "دونات", "مهلبية",
        "مطبق", "جريش", "قرصان", "مرقوق", "مطازيز",
        "فتوش", "تبولة", "مناقيش", "فطائر", "شعيرية",
        "مهلبية", "أرز بالحليب", "سلطة فواكه",
    ],
    "objects": [
        "هاتف", "حاسوب", "ساعة", "كرسي", "طاولة", "نافذة",
        "باب", "مفتاح", "قلم", "دفتر", "كتاب", "حقيبة",
        "مصباح", "مرآة", "مظلة", "وسادة", "بطانية", "مروحة",
        "ثلاجة", "غسالة", "تلفاز", "سماعة", "كاميرا", "نظارة",
        "حذاء", "قبعة", "محفظة", "زجاجة", "كوب", "ملعقة",
        "شوكة", "سكين", "صحن", "قدر", "مقلاة", "مكنسة",
        "مطرقة", "مفك", "مقص", "مسطرة", "ممحاة", "شاحن",
        "لوحة", "خريطة", "مصعد", "دراجة", "سيارة", "حافلة",
        "قطار", "طائرة", "سفينة", "كرة", "مضرب", "خوذة",
        "مظروف", "طابعة", "ميكروفون", "مكبر صوت", "منظار",
    ],
    "places": [
        "مدرسة", "جامعة", "مستشفى", "مطار", "محطة", "مكتبة",
        "حديقة", "متحف", "ملعب", "مسجد", "سوق", "مطعم",
        "مقهى", "فندق", "شاطئ", "جزيرة", "جبل", "صحراء",
        "غابة", "كهف", "قلعة", "قصر", "برج", "قرية", "مدينة",
        "مزرعة", "مخبز", "مصنع", "مسرح", "سينما", "مسبح",
        "ميناء", "جسر", "نفق", "ساحة", "موقف", "محكمة",
        "مركز شرطة", "محطة وقود", "مركز تجاري", "ملجأ",
        "محمية طبيعية", "وادي", "شلال", "بحيرة", "نهر",
        "غرفة", "مطبخ", "سطح", "قبو", "مرصد", "معرض",
    ],
    "countries": [
        "السعودية", "مصر", "العراق", "الأردن", "الكويت",
        "قطر", "البحرين", "عمان", "الإمارات", "اليمن",
        "المغرب", "الجزائر", "تونس", "ليبيا", "السودان",
        "تركيا", "اليابان", "الصين", "الهند", "باكستان",
        "إندونيسيا", "ماليزيا", "أستراليا", "كندا", "أمريكا",
        "البرازيل", "الأرجنتين", "فرنسا", "ألمانيا", "إيطاليا",
        "إسبانيا", "البرتغال", "بريطانيا", "النرويج", "السويد",
        "فنلندا", "روسيا", "أوكرانيا", "المكسيك", "كوريا الجنوبية",
        "تايلاند", "سنغافورة", "جنوب أفريقيا", "نيجيريا",
        "كينيا", "اليونان", "هولندا", "سويسرا", "النمسا",
        "أفغانستان", "بنغلاديش", "سريلانكا", "نيبال",
        "نيوزيلندا", "آيسلندا", "أيرلندا", "بلجيكا",
    ],
    "colors": [
        "أحمر", "أزرق", "أخضر", "أصفر", "برتقالي", "بنفسجي",
        "وردي", "أسود", "أبيض", "رمادي", "بني", "ذهبي",
        "فضي", "تركوازي", "كحلي", "سماوي", "خمري", "زيتي",
        "بيج", "نيلي", "مرجاني", "عنابي", "ليموني", "كريمي",
    ],
    "professions": [
        "طبيب", "مهندس", "معلم", "طيار", "ممرض", "محاسب",
        "مصور", "مترجم", "مزارع", "خباز", "نجار", "حداد",
        "كهربائي", "سباك", "مذيع", "مراسل", "محامي", "قاضي",
        "شرطي", "إطفائي", "مبرمج", "مصمم", "رسام", "كاتب",
        "شاعر", "باحث", "عالم", "فلكي", "جيولوجي", "طبيب أسنان",
        "صيدلي", "بيطري", "مدرب", "حارس", "حكم", "موسيقي",
        "مخرج", "ممثل", "مذيع أخبار", "خبير أرصاد",
        "ميكانيكي", "عامل بناء", "بحار", "غواص", "مخترع",
    ],
}

WORD_RECENT = defaultdict(lambda: deque(maxlen=150))
USED_IN_ROUND = set()


def fresh_word(category):
    bank = list(dict.fromkeys(WORD_BANKS[category]))
    recent = WORD_RECENT[category]

    available = [word for word in bank if normalize(word) not in recent]

    if not available:
        recent.clear()
        available = bank[:]

    word = random.choice(available)
    recent.append(normalize(word))
    return word


def fresh_question(category):
    word = fresh_word(category)

    if category == "animals":
        return word, f"خمن الحيوان: يبدأ اسمه بحرف **{word[0]}**."
    if category == "food":
        return word, f"خمن الطعام: عدد حروفه **{len(word.replace(' ', ''))}**."
    if category == "objects":
        return word, f"خمن الشيء: عدد حروفه **{len(word.replace(' ', ''))}**."
    if category == "places":
        return word, f"خمن المكان: يبدأ اسمه بحرف **{word[0]}**."
    if category == "countries":
        return word, f"خمن الدولة: عدد حروف اسمها **{len(word.replace(' ', ''))}**."
    if category == "colors":
        return word, f"خمن اللون: يبدأ اسمه بحرف **{word[0]}**."
    if category == "professions":
        return word, f"خمن المهنة: عدد حروفها **{len(word.replace(' ', ''))}**."

    return word, "خمن الكلمة المخفية."


# ============================================================
# IMAGE PUZZLES — ORIGINAL GENERATED IMAGES, NO STOCK PHOTOS
# ============================================================

IMAGE_RECENT = deque(maxlen=250)


def puzzle_image(word):
    if Image is None:
        return None

    digest = hashlib.sha256(
        f"{word}:{time.time_ns()}:{random.random()}".encode()
    ).hexdigest()

    # Every image has a unique randomized layout and background.
    seed = int(digest[:12], 16)
    rng = random.Random(seed)

    width, height = 800, 500
    image = Image.new("RGB", (width, height), (190, 245, 250))
    draw = ImageDraw.Draw(image)

    palette = [
        (220, 250, 255),
        (175, 235, 245),
        (200, 245, 240),
        (185, 230, 255),
        (215, 250, 245),
    ]

    background = rng.choice(palette)
    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)

    # Draw an original abstract icon-like puzzle using primitives.
    # The word itself is never printed on the image.
    cx = rng.randint(320, 480)
    cy = rng.randint(180, 300)
    size = rng.randint(90, 145)

    color_pool = [
        (40, 80, 130),
        (30, 110, 150),
        (60, 100, 170),
        (20, 130, 130),
        (70, 90, 110),
        (35, 120, 180),
    ]
    main_color = rng.choice(color_pool)

    shape_type = rng.choice(["circle", "square", "diamond", "triangle"])

    if shape_type == "circle":
        draw.ellipse(
            (cx - size, cy - size, cx + size, cy + size),
            fill=main_color,
        )
    elif shape_type == "square":
        draw.rounded_rectangle(
            (cx - size, cy - size, cx + size, cy + size),
            radius=rng.randint(8, 35),
            fill=main_color,
        )
    elif shape_type == "diamond":
        draw.polygon(
            [
                (cx, cy - size - 20),
                (cx + size, cy),
                (cx, cy + size + 20),
                (cx - size, cy),
            ],
            fill=main_color,
        )
    else:
        draw.polygon(
            [
                (cx, cy - size - 20),
                (cx + size, cy + size),
                (cx - size, cy + size),
            ],
            fill=main_color,
        )

    # Random small marks make every generated image different.
    for _ in range(rng.randint(10, 24)):
        x = rng.randint(20, width - 20)
        y = rng.randint(20, height - 20)
        radius = rng.randint(4, 17)
        mark_color = rng.choice(color_pool + [(255, 255, 255)])
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=mark_color,
        )

    # Add randomized geometric detail.
    for _ in range(rng.randint(3, 8)):
        x1 = rng.randint(0, width - 100)
        y1 = rng.randint(0, height - 100)
        x2 = x1 + rng.randint(25, 100)
        y2 = y1 + rng.randint(25, 100)
        draw.rectangle(
            (x1, y1, x2, y2),
            outline=rng.choice(color_pool),
            width=rng.randint(2, 5),
        )

    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)

    IMAGE_RECENT.append(digest)
    return output


# ============================================================
# GAME DEFINITIONS
# ============================================================

GAME_NAMES = {
    "مافيا": "mafia",
    "روليت": "roulette",
    "اكس او": "xo",
    "حجر ورقة مقص": "rps",
    "الكراسي الموسيقية": "chairs",
    "الغميضة": "hide",
    "معلومات": "trivia",
    "خمن الرسمة": "drawing",
    "خمن الكلمة": "word",
    "أسرع كاتب": "typing",
    "فك الايموجي": "emoji",
    "خمن الدولة": "country",
    "الرقم السري": "number",
    "اكتشف الكذب": "lie",
    "المحقق": "detective",
    "تحدي الانماط": "pattern",
    "سلسلة الكلمات": "chain",
    "تحدي الذاكرة": "memory",
    "بطولة التحديات": "tournament",
    "البحث عن الكنز": "treasure",
    "ترتيب البطاقات": "cards",
    "اكمل التسلسل": "sequence",
    "البحث عن الكلمات": "wordsearch",
    "الرياضيات": "math",
    "سرعة الاستجابة": "reaction",
    "رتب الحروف": "scramble",
    "اكتشف الاختلاف": "difference",
    "خمن اللون": "color",
    "اكتشف النمط": "shapes",
    "حروف الكلمة": "letters",
}

GAME_ALIASES = {
    "مافيا": "mafia",
    "maf ia": "mafia",
    "roulette": "roulette",
    "روليت": "roulette",
    "روليت الاسماء": "roulette",
    "xo": "xo",
    "اكس او": "xo",
    "حجر ورقة مقص": "rps",
    "حجر ورقه مقص": "rps",
    "الكراسي": "chairs",
    "الكراسي الموسيقية": "chairs",
    "الغميضة": "hide",
    "معلومات": "trivia",
    "تحدي المعلومات": "trivia",
    "خمن الرسمة": "drawing",
    "خمن الكلمة": "word",
    "اسرع كاتب": "typing",
    "فك الايموجي": "emoji",
    "خمن الدولة": "country",
    "الرقم السري": "number",
    "اكتشف الكذب": "lie",
    "المحقق": "detective",
    "تحدي الانماط": "pattern",
    "سلسلة الكلمات": "chain",
    "تحدي الذاكرة": "memory",
    "بطولة التحديات": "tournament",
    "البحث عن الكنز": "treasure",
    "ترتيب البطاقات": "cards",
    "اكمل التسلسل": "sequence",
    "البحث عن الكلمات": "wordsearch",
    "الرياضيات": "math",
    "سرعة الاستجابة": "reaction",
    "رتب الحروف": "scramble",
    "اكتشف الاختلاف": "difference",
    "خمن اللون": "color",
    "اكتشف النمط": "shapes",
    "حروف الكلمة": "letters",
}

# ============================================================
# GAME STATE
# ============================================================

ACTIVE_GAMES = {}
ACTIVE_BY_CHANNEL = {}
GAME_LOCKS = defaultdict(asyncio.Lock)


def game_key(ctx):
    return (ctx.guild.id, ctx.channel.id)


def get_active_game(ctx):
    return ACTIVE_GAMES.get(game_key(ctx))


async def register_game(ctx, game):
    key = game_key(ctx)

    if key in ACTIVE_GAMES:
        await ctx.reply(
            "⚠️ توجد لعبة جارية في هذه القناة. انتظر حتى تنتهي."
        )
        return False

    ACTIVE_GAMES[key] = game
    ACTIVE_BY_CHANNEL[key] = game
    return True


async def unregister_game(ctx):
    key = game_key(ctx)
    ACTIVE_GAMES.pop(key, None)
    ACTIVE_BY_CHANNEL.pop(key, None)


# ============================================================
# BASE GAME VIEW
# ============================================================

class JoinGameView(discord.ui.View):
    def __init__(self, game, max_players=30, min_players=2):
        super().__init__(timeout=120)
        self.game = game
        self.max_players = max_players
        self.min_players = min_players
        self.players = {}
        self.started = False
        self.message = None

    def player_list(self):
        if not self.players:
            return "لا يوجد لاعبون حتى الآن."

        return "\n".join(
            f"{index}. <@{user_id}>"
            for index, user_id in enumerate(self.players, 1)
        )

    async def update_message(self, interaction=None):
        description = (
            f"**اللعبة:** {self.game}\n"
            f"**اللاعبون:** {len(self.players)}/{self.max_players}\n\n"
            f"{self.player_list()}\n\n"
            "اضغط انضمام للمشاركة."
        )
        if self.message:
            try:
                await self.message.edit(
                    embed=embed("🎮 تسجيل اللاعبين", description),
                    view=self,
                )
            except discord.HTTPException:
                pass

    @discord.ui.button(
        label="انضمام",
        style=discord.ButtonStyle.success,
        emoji="🎮",
    )
    async def join(self, interaction, button):
        if self.started:
            await interaction.response.send_message(
                "بدأت اللعبة بالفعل.",
                ephemeral=True,
            )
            return

        if interaction.user.bot:
            await interaction.response.send_message(
                "البوتات لا يمكنها المشاركة.",
                ephemeral=True,
            )
            return

        if interaction.user.id in self.players:
            await interaction.response.send_message(
                "أنت منضم بالفعل.",
                ephemeral=True,
            )
            return

        if len(self.players) >= self.max_players:
            await interaction.response.send_message(
                "اكتمل عدد اللاعبين.",
                ephemeral=True,
            )
            return

        self.players[interaction.user.id] = interaction.user
        await interaction.response.send_message(
            "✅ تم تسجيلك في اللعبة.",
            ephemeral=True,
        )
        await self.update_message()

    @discord.ui.button(
        label="مغادرة",
        style=discord.ButtonStyle.secondary,
        emoji="🚪",
    )
    async def leave(self, interaction, button):
        if self.started:
            await interaction.response.send_message(
                "لا يمكنك المغادرة بعد بدء اللعبة.",
                ephemeral=True,
            )
            return

        if interaction.user.id not in self.players:
            await interaction.response.send_message(
                "أنت لست مسجلًا في اللعبة.",
                ephemeral=True,
            )
            return

        self.players.pop(interaction.user.id, None)
        await interaction.response.send_message(
            "تم إخراجك من قائمة اللاعبين.",
            ephemeral=True,
        )
        await self.update_message()

    @discord.ui.button(
        label="بدء اللعبة",
        style=discord.ButtonStyle.primary,
        emoji="▶️",
    )
    async def start(self, interaction, button):
        if self.started:
            await interaction.response.send_message(
                "بدأت اللعبة بالفعل.",
                ephemeral=True,
            )
            return

        if not interaction.guild or not isinstance(
            interaction.user, discord.Member
        ):
            await interaction.response.send_message(
                "هذا الزر متاح داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        if (
            not interaction.user.guild_permissions.manage_guild
            and interaction.user.id not in self.players
        ):
            await interaction.response.send_message(
                "انضم أولًا قبل بدء اللعبة.",
                ephemeral=True,
            )
            return

        if len(self.players) < self.min_players:
            await interaction.response.send_message(
                f"تحتاج اللعبة إلى {self.min_players} لاعبين على الأقل.",
                ephemeral=True,
            )
            return

        self.started = True
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(view=self)
        await self.game_start(interaction)

    async def game_start(self, interaction):
        raise NotImplementedError


# ============================================================
# MAFIA GAME — 4 TO 9: ONE MAFIA, 10 TO 30: TWO MAFIA
# ============================================================

class MafiaView(JoinGameView):
    def __init__(self):
        super().__init__("مافيا", max_players=30, min_players=4)
        self.roles = {}
        self.alive = set()
        self.votes = {}
        self.phase = "lobby"
        self.day_number = 0
        self.night_actions = {}
        self.night_view = None

    async def game_start(self, interaction):
        players = list(self.players.keys())
        count = len(players)

        if count < 4 or count > 30:
            await interaction.followup.send(
                "يجب أن يكون عدد لاعبي المافيا بين 4 و30.",
                ephemeral=True,
            )
            return

        mafia_count = 1 if count <= 9 else 2
        roles = ["مافيا"] * mafia_count + ["طبيب", "محقق"]
        roles += ["مواطن"] * (count - len(roles))
        random.shuffle(roles)

        self.roles = dict(zip(players, roles))
        self.alive = set(players)

        for user_id, role in self.roles.items():
            try:
                user = await bot.fetch_user(user_id)
                await user.send(
                    embed=embed(
                        "🕵️ دورك في لعبة المافيا",
                        f"دورك هو: **{role}**\n"
                        "لا تكشف دورك لبقية اللاعبين.",
                    )
                )
            except (discord.HTTPException, discord.NotFound):
                pass

        await interaction.followup.send(
            embed=embed(
                "🕵️ بدأت المافيا",
                f"عدد اللاعبين: **{count}**\n"
                f"عدد المافيا: **{mafia_count}**\n"
                "تم إرسال الأدوار على الخاص إن كانت الرسائل متاحة.\n"
                "ستبدأ مرحلة الليل.",
            )
        )

        await self.run_night(interaction.channel)

    async def run_night(self, channel):
        self.phase = "night"
        self.day_number += 1
        self.night_actions = {}

        await channel.send(
            embed=embed(
                f"🌙 ليلة رقم {self.day_number}",
                "على الطبيب اختيار من يحميه، وعلى المحقق اختيار من يفحصه.\n"
                "يمكن للمافيا اختيار هدفها عبر الأزرار الخاصة.",
            )
        )

        view = MafiaNightView(self)
        self.night_view = view

        try:
            message = await channel.send(
                "الأدوار الليلية: اختر دورك من الأزرار.",
                view=view,
            )
            view.message = message
        except discord.HTTPException:
            return

        await asyncio.sleep(25)

        mafia = [
            uid for uid in self.alive
            if self.roles.get(uid) == "مافيا"
        ]
        doctors = [
            uid for uid in self.alive
            if self.roles.get(uid) == "طبيب"
        ]
        detectives = [
            uid for uid in self.alive
            if self.roles.get(uid) == "محقق"
        ]

        targets = self.night_actions.get("mafia", [])
        protected = self.night_actions.get("doctor")
        victim = None

        if targets:
            counts = defaultdict(int)
            for target in targets:
                if target in self.alive:
                    counts[target] += 1
            if counts:
                victim = max(counts, key=counts.get)

        if victim == protected:
            await channel.send("🩺 أنقذ الطبيب الشخص المستهدف هذه الليلة.")
        elif victim in self.alive:
            self.alive.discard(victim)
            await channel.send(
                f"🌅 انتهت الليلة. خرج {user_mention(victim)} من اللعبة."
            )
        else:
            await channel.send("🌅 انتهت الليلة دون خروج أي لاعب.")

        checked = self.night_actions.get("detective")
        if checked in self.roles:
            # Send the result only to the detective who made the selection.
            for detective_id in detectives:
                if self.night_actions.get(
                    f"detective_actor_{detective_id}"
                ):
                    try:
                        user = await bot.fetch_user(detective_id)
                        await user.send(
                            f"نتيجة التحقيق: {user_mention(checked)} "
                            f"({'مافيا' if self.roles[checked] == 'مافيا' else 'ليس مافيا'})."
                        )
                    except discord.HTTPException:
                        pass

        if self.check_winner(channel):
            return

        await self.run_day(channel)

    async def run_day(self, channel):
        self.phase = "day"
        self.votes = {}

        view = MafiaVoteView(self)
        await channel.send(
            embed=embed(
                "☀️ مرحلة التصويت",
                "صوّتوا على اللاعب الذي تشكون فيه.\n"
                "لديكم 30 ثانية للتصويت.",
            ),
            view=view,
        )

        await asyncio.sleep(30)

        counts = defaultdict(int)
        for voter, target in self.votes.items():
            if voter in self.alive and target in self.alive:
                counts[target] += 1

        if counts:
            highest = max(counts.values())
            winners = [
                uid for uid, votes in counts.items()
                if votes == highest
            ]

            if len(winners) == 1:
                eliminated = winners[0]
                self.alive.discard(eliminated)
                await channel.send(
                    f"🗳️ تم إخراج {user_mention(eliminated)} بالتصويت."
                )
            else:
                await channel.send("🗳️ تعادل التصويت. لم يخرج أحد.")
        else:
            await channel.send("لم يتم تسجيل أصوات كافية.")

        if self.check_winner(channel):
            return

        await self.run_night(channel)

    def check_winner(self, channel):
        mafia_alive = [
            uid for uid in self.alive
            if self.roles.get(uid) == "مافيا"
        ]
        others_alive = self.alive - set(mafia_alive)

        if not mafia_alive:
            asyncio.create_task(
                channel.send(
                    embed=embed(
                        "🏆 فاز المواطنون!",
                        "تم اكتشاف جميع أفراد المافيا.",
                    )
                )
            )
            self.finish_scores()
            return True

        if len(mafia_alive) >= len(others_alive):
            asyncio.create_task(
                channel.send(
                    embed=embed(
                        "🕵️ فازت المافيا!",
                        "أصبحت المافيا تسيطر على اللعبة.",
                    )
                )
            )
            self.finish_scores(winning_team="مافيا")
            return True

        return False

    def finish_scores(self, winning_team=None):
        for uid in self.players:
            add_points(
                self.message.guild.id if self.message and self.message.guild else 0,
                uid,
                PARTICIPATION_POINTS,
            )

        for uid in self.players:
            if winning_team == "مافيا" and self.roles.get(uid) == "مافيا":
                add_points(
                    self.message.guild.id if self.message and self.message.guild else 0,
                    uid,
                    WIN_POINTS,
                )
            elif winning_team is None and self.roles.get(uid) != "مافيا":
                add_points(
                    self.message.guild.id if self.message and self.message.guild else 0,
                    uid,
                    WIN_POINTS,
                )

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


class MafiaNightView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=25)
        self.game = game

    async def select_target(self, interaction, role):
        if interaction.user.id not in self.game.alive:
            await interaction.response.send_message(
                "أنت خارج اللعبة.",
                ephemeral=True,
            )
            return

        if self.game.roles.get(interaction.user.id) != role:
            await interaction.response.send_message(
                "هذا الخيار غير متاح لدورك.",
                ephemeral=True,
            )
            return

        targets = [
            uid for uid in self.game.alive
            if uid != interaction.user.id
        ]

        if not targets:
            await interaction.response.send_message(
                "لا يوجد لاعبون آخرون.",
                ephemeral=True,
            )
            return

        view = MafiaTargetView(self.game, role, interaction.user.id, targets)
        await interaction.response.send_message(
            "اختر اللاعب:",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(
        label="اختيار هدف المافيا",
        style=discord.ButtonStyle.danger,
    )
    async def mafia(self, interaction, button):
        await self.select_target(interaction, "مافيا")

    @discord.ui.button(
        label="حماية لاعب",
        style=discord.ButtonStyle.success,
    )
    async def doctor(self, interaction, button):
        await self.select_target(interaction, "طبيب")

    @discord.ui.button(
        label="التحقيق مع لاعب",
        style=discord.ButtonStyle.primary,
    )
    async def detective(self, interaction, button):
        await self.select_target(interaction, "محقق")


class MafiaTargetView(discord.ui.View):
    def __init__(self, game, role, actor_id, targets):
        super().__init__(timeout=20)
        self.game = game
        self.role = role
        self.actor_id = actor_id

        options = [
            discord.SelectOption(
                label=str(game.players[uid])[:100],
                value=str(uid),
            )
            for uid in targets[:25]
        ]

        select = discord.ui.Select(
            placeholder="اختر اللاعب",
            min_values=1,
            max_values=1,
            options=options,
        )
        select.callback = self.choose
        self.add_item(select)

    async def choose(self, interaction):
        if interaction.user.id != self.actor_id:
            await interaction.response.send_message(
                "هذه القائمة ليست لك.",
                ephemeral=True,
            )
            return

        target = int(interaction.data["values"][0])

        if self.role == "مافيا":
            current = self.game.night_actions.setdefault("mafia", [])
            current.append(target)
        elif self.role == "طبيب":
            self.game.night_actions["doctor"] = target
        elif self.role == "محقق":
            self.game.night_actions["detective"] = target
            self.game.night_actions[
                f"detective_actor_{self.actor_id}"
            ] = True

        await interaction.response.send_message(
            "✅ تم تسجيل اختيارك سرًا.",
            ephemeral=True,
        )


class MafiaVoteView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=30)
        self.game = game

        options = [
            discord.SelectOption(
                label=str(game.players[uid])[:100],
                value=str(uid),
            )
            for uid in list(game.alive)[:25]
        ]

        if options:
            select = discord.ui.Select(
                placeholder="اختر اللاعب للتصويت",
                min_values=1,
                max_values=1,
                options=options,
            )
            select.callback = self.vote
            self.add_item(select)

    async def vote(self, interaction):
        voter = interaction.user.id

        if voter not in self.game.alive:
            await interaction.response.send_message(
                "أنت خارج اللعبة.",
                ephemeral=True,
            )
            return

        target = int(interaction.data["values"][0])

        if target not in self.game.alive:
            await interaction.response.send_message(
                "هذا اللاعب لم يعد في اللعبة.",
                ephemeral=True,
            )
            return

        self.game.votes[voter] = target
        await interaction.response.send_message(
            "تم تسجيل تصويتك.",
            ephemeral=True,
        )


# ============================================================
# ROULETTE — UP TO 50 PLAYERS
# No betting; selects a player for a harmless challenge.
# ============================================================

class RouletteView(JoinGameView):
    def __init__(self):
        super().__init__("روليت التحديات", max_players=ROULETTE_MAX_PLAYERS, min_players=2)

    async def game_start(self, interaction):
        players = list(self.players.keys())
        if len(players) < 2:
            await interaction.followup.send(
                "تحتاج إلى لاعبين اثنين على الأقل."
            )
            return

        selected = random.choice(players)

        challenges = [
            "اذكر ثلاث دول تبدأ بحرف الميم.",
            "اكتب جملة من خمس كلمات بسرعة.",
            "اذكر خمسة حيوانات في عشر ثوانٍ.",
            "حل لغزًا منطقيًا قصيرًا.",
            "اذكر ثلاثة أشياء لونها أزرق.",
            "اكتب كلمة تبدأ بآخر حرف من اسمك.",
            "اذكر أربع مهن مختلفة.",
            "اذكر خمس فواكه دون تكرار.",
            "اكتب اسم دولة وعاصمتها.",
            "اذكر ثلاثة أشياء تستخدمها يوميًا.",
            "حل مسألة حسابية يرسلها المنظم.",
            "اذكر أربعة ألوان مختلفة.",
            "اكتب جملة تبدأ بحرف السين.",
            "اذكر ثلاثة أشياء توجد في المدرسة.",
            "اذكر خمسة أرقام فردية.",
        ]

        challenge = random.choice(challenges)

        await interaction.followup.send(
            embed=embed(
                "🎡 نتيجة روليت التحديات",
                f"اللاعب المختار: {user_mention(selected)}\n\n"
                f"**التحدي:** {challenge}\n\n"
                "لا توجد مراهنات أو خسارة نقاط بسبب الاختيار العشوائي.",
            )
        )

        for uid in players:
            add_points(
                interaction.guild.id,
                uid,
                PARTICIPATION_POINTS,
            )

        await self.end_game(interaction.guild.id, selected)

    async def end_game(self, guild_id, selected):
        add_points(guild_id, selected, WIN_POINTS)


# ============================================================
# XO
# ============================================================

class XOView(discord.ui.View):
    def __init__(self, player1, player2):
        super().__init__(timeout=120)
        self.players = [player1, player2]
        self.turn = 0
        self.board = [""] * 9
        self.finished = False
        self.buttons = []

        for i in range(9):
            button = discord.ui.Button(
                label="⠀",
                style=discord.ButtonStyle.secondary,
                row=i // 3,
            )
            button.callback = self.make_callback(i)
            self.buttons.append(button)
            self.add_item(button)

    def make_callback(self, index):
        async def callback(interaction):
            if self.finished:
                await interaction.response.send_message(
                    "انتهت اللعبة.",
                    ephemeral=True,
                )
                return

            current = self.players[self.turn]

            if interaction.user.id != current.id:
                await interaction.response.send_message(
                    "ليس دورك.",
                    ephemeral=True,
                )
                return

            if self.board[index]:
                await interaction.response.send_message(
                    "هذا المربع مستخدم.",
                    ephemeral=True,
                )
                return

            mark = "❌" if self.turn == 0 else "⭕"
            self.board[index] = mark

            button = self.buttons[index]
            button.label = mark
            button.disabled = True
            button.style = (
                discord.ButtonStyle.danger
                if mark == "❌"
                else discord.ButtonStyle.primary
            )

            winner = self.check_winner()

            if winner is not None:
                self.finished = True
                for child in self.children:
                    child.disabled = True

                if winner == -1:
                    content = "🤝 تعادل!"
                else:
                    winner_user = self.players[winner]
                    content = f"🏆 الفائز: {winner_user.mention}"
                    add_points(
                        interaction.guild.id,
                        winner_user.id,
                        WIN_POINTS,
                    )

                for user in self.players:
                    add_points(
                        interaction.guild.id,
                        user.id,
                        PARTICIPATION_POINTS,
                    )

                await interaction.response.edit_message(
                    content=content,
                    view=self,
                )
                return

            self.turn = 1 - self.turn

            await interaction.response.edit_message(
                content=f"دور {self.players[self.turn].mention}",
                view=self,
            )

        return callback

    def check_winner(self):
        lines = [
            (0, 1, 2), (3, 4, 5), (6, 7, 8),
            (0, 3, 6), (1, 4, 7), (2, 5, 8),
            (0, 4, 8), (2, 4, 6),
        ]

        for a, b, c in lines:
            if (
                self.board[a]
                and self.board[a] == self.board[b] == self.board[c]
            ):
                return 0 if self.board[a] == "❌" else 1

        if all(self.board):
            return -1

        return None


# ============================================================
# RPS — SECRET BUTTON CHOICES
# ============================================================

class RPSView(discord.ui.View):
    def __init__(self, player1, player2):
        super().__init__(timeout=60)
        self.players = {player1.id: player1, player2.id: player2}
        self.choices = {}
        self.done = False

    async def make_choice(self, interaction, choice):
        if interaction.user.id not in self.players:
            await interaction.response.send_message(
                "هذه المباراة ليست لك.",
                ephemeral=True,
            )
            return

        if interaction.user.id in self.choices:
            await interaction.response.send_message(
                "سجلت اختيارك بالفعل.",
                ephemeral=True,
            )
            return

        self.choices[interaction.user.id] = choice
        await interaction.response.send_message(
            "تم تسجيل اختيارك سرًا.",
            ephemeral=True,
        )

        if len(self.choices) == 2:
            self.done = True
            p1, p2 = list(self.players.keys())
            c1, c2 = self.choices[p1], self.choices[p2]

            if c1 == c2:
                result = "🤝 تعادل!"
            elif (c1, c2) in [
                ("حجر", "مقص"),
                ("ورقة", "حجر"),
                ("مقص", "ورقة"),
            ]:
                result = f"🏆 الفائز: {self.players[p1].mention}"
                add_points(interaction.guild.id, p1, WIN_POINTS)
            else:
                result = f"🏆 الفائز: {self.players[p2].mention}"
                add_points(interaction.guild.id, p2, WIN_POINTS)

            for uid in self.players:
                add_points(
                    interaction.guild.id,
                    uid,
                    PARTICIPATION_POINTS,
                )

            for child in self.children:
                child.disabled = True

            await interaction.channel.send(
                embed=embed(
                    "✊ حجر ورقة مقص",
                    f"{self.players[p1].mention}: **{c1}**\n"
                    f"{self.players[p2].mention}: **{c2}**\n\n"
                    f"{result}",
                ),
                view=self,
            )

    @discord.ui.button(label="حجر", emoji="✊", style=discord.ButtonStyle.primary)
    async def rock(self, interaction, button):
        await self.make_choice(interaction, "حجر")

    @discord.ui.button(label="ورقة", emoji="📄", style=discord.ButtonStyle.primary)
    async def paper(self, interaction, button):
        await self.make_choice(interaction, "ورقة")

    @discord.ui.button(label="مقص", emoji="✂️", style=discord.ButtonStyle.primary)
    async def scissors(self, interaction, button):
        await self.make_choice(interaction, "مقص")


# ============================================================
# SINGLE-PLAYER WORD GUESSING
# ============================================================

class WordGuessView(discord.ui.View):
    def __init__(self, owner_id, guild_id, word, hint):
        super().__init__(timeout=GAME_DURATION)
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.word = word
        self.hint = hint
        self.answered = False

    @discord.ui.button(label="تخمين الإجابة", style=discord.ButtonStyle.success)
    async def guess(self, interaction, button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "هذه الجولة ليست لك.",
                ephemeral=True,
            )
            return

        modal = GuessModal(self)
        await interaction.response.send_modal(modal)


class GuessModal(discord.ui.Modal, title="خمن الكلمة"):
    answer = discord.ui.TextInput(
        label="اكتب إجابتك",
        placeholder="اكتب الكلمة هنا...",
        max_length=80,
    )

    def __init__(self, game_view):
        super().__init__()
        self.game_view = game_view

    async def on_submit(self, interaction):
        view = self.game_view

        if view.answered:
            await interaction.response.send_message(
                "انتهت الجولة.",
                ephemeral=True,
            )
            return

        view.answered = True

        if normalize(self.answer.value) == normalize(view.word):
            add_points(view.guild_id, view.owner_id, WIN_POINTS)
            await interaction.response.send_message(
                embed=embed(
                    "✅ إجابة صحيحة!",
                    f"الكلمة هي **{view.word}**.\n"
                    f"حصلت على {WIN_POINTS} نقاط.",
                )
            )
        else:
            await interaction.response.send_message(
                embed=embed(
                    "❌ إجابة غير صحيحة",
                    f"الإجابة الصحيحة: **{view.word}**",
                )
            )

        view.stop()


# ============================================================
# TRIVIA / MATH / SCRAMBLE / SEQUENCE / COLOR / MEMORY
# ============================================================

TRIVIA = [
    ("ما عاصمة السعودية؟", ["الرياض", "جدة", "مكة"], 0),
    ("كم عدد أيام الأسبوع؟", ["5", "7", "8"], 1),
    ("ما الكوكب المعروف بالكوكب الأحمر؟", ["الزهرة", "المريخ", "زحل"], 1),
    ("كم يساوي 9 × 8؟", ["72", "64", "81"], 0),
    ("ما أكبر محيط على الأرض؟", ["الأطلسي", "الهندي", "الهادئ"], 2),
    ("ما عاصمة اليابان؟", ["طوكيو", "أوساكا", "كيوتو"], 0),
    ("كم عدد أضلاع المثلث؟", ["2", "3", "4"], 1),
    ("ما الغاز الذي تحتاجه النباتات للبناء الضوئي؟", ["الأكسجين", "ثاني أكسيد الكربون", "الهيليوم"], 1),
    ("كم شهرًا في السنة؟", ["10", "11", "12"], 2),
    ("ما أقرب نجم إلى الأرض؟", ["الشمس", "الشعرى", "النسر"], 0),
    ("ما عاصمة مصر؟", ["القاهرة", "الإسكندرية", "الأقصر"], 0),
    ("كم دقيقة في الساعة؟", ["30", "60", "100"], 1),
    ("ما الحيوان المعروف بسفينة الصحراء؟", ["الحصان", "الجمل", "الفيل"], 1),
    ("كم يساوي 15 + 27؟", ["32", "42", "52"], 1),
    ("ما أكبر قارة من حيث المساحة؟", ["آسيا", "أوروبا", "أفريقيا"], 0),
    ("ما عاصمة الأردن؟", ["عمّان", "إربد", "العقبة"], 0),
    ("ما العضو الذي يضخ الدم؟", ["الرئة", "القلب", "الكبد"], 1),
    ("كم عدد حروف اللغة الإنجليزية؟", ["24", "26", "28"], 1),
    ("ما عاصمة فرنسا؟", ["باريس", "ليون", "نيس"], 0),
    ("كم يساوي 100 ÷ 4؟", ["20", "25", "40"], 1),
    ("ما أكبر كوكب في المجموعة الشمسية؟", ["الأرض", "المشتري", "عطارد"], 1),
    ("ما لون السماء الصافية غالبًا نهارًا؟", ["أزرق", "أخضر", "أحمر"], 0),
    ("كم ضلعًا للمربع؟", ["3", "4", "5"], 1),
    ("ما عاصمة الإمارات؟", ["دبي", "أبوظبي", "الشارقة"], 1),
    ("ما الجهاز المستخدم لقياس الحرارة؟", ["ميزان الحرارة", "المسطرة", "الميزان"], 0),
    ("كم يساوي 12 × 12؟", ["124", "144", "132"], 1),
    ("أي من هذه الحيوانات ثديي؟", ["الدلفين", "التمساح", "النسر"], 0),
    ("ما عاصمة إيطاليا؟", ["روما", "ميلانو", "البندقية"], 0),
    ("كم ثانية في الدقيقة؟", ["30", "60", "90"], 1),
    ("ما أكبر عضو في جسم الإنسان؟", ["القلب", "الجلد", "الكبد"], 1),
]


class TriviaView(discord.ui.View):
    def __init__(self, guild_id, question, options, correct_index, players):
        super().__init__(timeout=GAME_DURATION)
        self.guild_id = guild_id
        self.question = question
        self.options = options
        self.correct_index = correct_index
        self.players = players
        self.answered = set()
        self.winners = []
        self.message = None

        for index, option in enumerate(options):
            button = discord.ui.Button(
                label=option,
                style=discord.ButtonStyle.primary,
            )
            button.callback = self.make_callback(index)
            self.add_item(button)

    def make_callback(self, index):
        async def callback(interaction):
            uid = interaction.user.id

            if uid not in self.players:
                await interaction.response.send_message(
                    "انضم إلى اللعبة أولًا.",
                    ephemeral=True,
                )
                return

            if uid in self.answered:
                await interaction.response.send_message(
                    "لقد أجبت بالفعل.",
                    ephemeral=True,
                )
                return

            self.answered.add(uid)

            if index == self.correct_index:
                self.winners.append(uid)
                add_points(
                    self.guild_id,
                    uid,
                    WIN_POINTS,
                )
                result = "إجابة صحيحة! حصلت على النقاط."
            else:
                result = "إجابة غير صحيحة."

            await interaction.response.send_message(
                result,
                ephemeral=True,
            )

            if len(self.answered) == len(self.players):
                await self.finish(interaction.channel)

        return callback

    async def finish(self, channel):
        for child in self.children:
            child.disabled = True

        if self.winners:
            winners_text = "\n".join(
                f"🏆 <@{uid}>" for uid in self.winners
            )
        else:
            winners_text = "لم توجد إجابات صحيحة."

        await channel.send(
            embed=embed(
                "🧠 انتهى التحدي",
                f"الإجابة الصحيحة: **{self.options[self.correct_index]}**\n"
                f"{winners_text}",
            )
        )
        self.stop()


# ============================================================
# MEMORY GAME
# ============================================================

class MemoryView(discord.ui.View):
    def __init__(self, owner_id, guild_id, sequence):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.sequence = sequence
        self.answered = False

    @discord.ui.button(label="ابدأ الاختبار", style=discord.ButtonStyle.primary)
    async def test(self, interaction, button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "هذه اللعبة ليست لك.",
                ephemeral=True,
            )
            return

        modal = MemoryModal(self)
        await interaction.response.send_modal(modal)


class MemoryModal(discord.ui.Modal, title="اختبار الذاكرة"):
    answer = discord.ui.TextInput(
        label="اكتب الرموز بالترتيب",
        placeholder="مثال: 🍎 🚗 ⭐",
        max_length=200,
    )

    def __init__(self, view):
        super().__init__()
        self.game_view = view

    async def on_submit(self, interaction):
        view = self.game_view

        if view.answered:
            await interaction.response.send_message(
                "انتهت الجولة.",
                ephemeral=True,
            )
            return

        view.answered = True
        actual = normalize(" ".join(self.answer.value.split()))
        expected = normalize(" ".join(view.sequence))

        if actual == expected:
            add_points(view.guild_id, view.owner_id, WIN_POINTS)
            result = f"✅ صحيح! حصلت على {WIN_POINTS} نقاط."
        else:
            result = (
                "❌ ترتيب غير صحيح.\n"
                f"الترتيب الصحيح: {' '.join(view.sequence)}"
            )

        await interaction.response.send_message(result)
        view.stop()


# ============================================================
# GAME COMMANDS
# ============================================================

@bot.command(name="العاب", aliases=["ألعاب", "games"])
@commands.guild_only()
async def games_list(ctx):
    lines = [
        "**👥 ألعاب جماعية**",
        "1. `+مافيا`",
        "2. `+روليت`",
        "3. `+اكس او @اللاعب`",
        "4. `+حجر ورقة مقص @اللاعب`",
        "5. `+الكراسي الموسيقية`",
        "6. `+الغميضة`",
        "7. `+معلومات`",
        "8. `+خمن الرسمة`",
        "9. `+خمن الكلمة`",
        "10. `+أسرع كاتب`",
        "11. `+فك الايموجي`",
        "12. `+خمن الدولة`",
        "13. `+الرقم السري`",
        "14. `+اكتشف الكذب`",
        "15. `+المحقق`",
        "16. `+تحدي الانماط`",
        "17. `+سلسلة الكلمات`",
        "18. `+تحدي الذاكرة`",
        "19. `+بطولة التحديات`",
        "20. `+البحث عن الكنز`",
        "",
        "**🧍 ألعاب فردية**",
        "21. `+ترتيب البطاقات`",
        "22. `+اكمل التسلسل`",
        "23. `+البحث عن الكلمات`",
        "24. `+الرياضيات`",
        "25. `+سرعة الاستجابة`",
        "26. `+رتب الحروف`",
        "27. `+اكتشف الاختلاف`",
        "28. `+خمن اللون`",
        "29. `+اكتشف النمط`",
        "30. `+حروف الكلمة`",
        "",
        "**النقاط:** 10 للفوز و2 للمشاركة.",
        "تبدأ الألعاب الجماعية بزر الانضمام ثم بدء اللعبة.",
    ]

    await ctx.send(
        embed=embed(
            "🎮 قائمة ألعاب CRYSTAL",
            "\n".join(lines),
        )
    )


@bot.command(name="نقاط")
@commands.guild_only()
async def points_command(ctx, member: discord.Member = None):
    member = member or ctx.author
    points = get_points(ctx.guild.id, member.id)

    await ctx.reply(
        embed=embed(
            "🏆 نقاط اللاعب",
            f"**اللاعب:** {member.mention}\n"
            f"**النقاط:** {points}",
        )
    )


@bot.command(name="توب", aliases=["leaderboard", "top"])
@commands.guild_only()
async def leaderboard(ctx):
    prefix = f"{ctx.guild.id}:"
    scores = []

    for key, value in DATA["scores"].items():
        if key.startswith(prefix):
            try:
                uid = int(key.split(":", 1)[1])
                scores.append((uid, value))
            except ValueError:
                continue

    scores.sort(key=lambda item: item[1], reverse=True)

    if not scores:
        await ctx.reply("لا توجد نقاط مسجلة بعد.")
        return

    lines = []
    for index, (uid, points) in enumerate(scores[:10], 1):
        lines.append(f"**{index}.** <@{uid}> — **{points}** نقطة")

    await ctx.reply(
        embed=embed("🏆 أفضل اللاعبين", "\n".join(lines))
    )


# ============================================================
# GAME STARTERS
# ============================================================

@bot.command(name="مافيا")
@commands.guild_only()
async def mafia_command(ctx):
    game = MafiaView()

    if not await register_game(ctx, game):
        return

    game.message = await ctx.send(
        embed=embed(
            "🕵️ لعبة المافيا",
            "انضموا إلى اللعبة.\n"
            "4–9 لاعبين: مافيا واحدة.\n"
            "10–30 لاعبًا: مافيا اثنتان.\n"
            "الأدوار تُرسل على الخاص إن كانت الرسائل متاحة.",
        ),
        view=game,
    )


@bot.command(name="روليت", aliases=["روليت الاسماء"])
@commands.guild_only()
async def roulette_command(ctx):
    game = RouletteView()

    if not await register_game(ctx, game):
        return

    game.message = await ctx.send(
        embed=embed(
            "🎡 روليت التحديات",
            "الحد الأقصى **50 لاعبًا**.\n"
            "انضموا، ثم اضغطوا بدء اللعبة.\n"
            "الاختيار يحدد تحديًا خفيفًا دون مراهنات.",
        ),
        view=game,
    )


@bot.command(name="اكس او", aliases=["xo"])
@commands.guild_only()
async def xo_command(ctx, opponent: discord.Member):
    if opponent.bot or opponent.id == ctx.author.id:
        await ctx.reply("اختر لاعبًا آخر.")
        return

    key = game_key(ctx)
    if key in ACTIVE_GAMES:
        await ctx.reply("توجد لعبة أخرى جارية في هذه القناة.")
        return

    view = XOView(ctx.author, opponent)
    ACTIVE_GAMES[key] = view

    await ctx.send(
        embed=embed(
            "❌ XO",
            f"{ctx.author.mention} ضد {opponent.mention}\n"
            f"دور {ctx.author.mention}",
        ),
        view=view,
    )


@bot.command(name="حجر ورقة مقص", aliases=["rps"])
@commands.guild_only()
async def rps_command(ctx, opponent: discord.Member):
    if opponent.bot or opponent.id == ctx.author.id:
        await ctx.reply("اختر لاعبًا آخر.")
        return

    view = RPSView(ctx.author, opponent)

    await ctx.send(
        embed=embed(
            "✊ حجر ورقة مقص",
            f"{ctx.author.mention} ضد {opponent.mention}\n"
            "اختيارات اللاعبين سرية.",
        ),
        view=view,
    )


async def start_word_game(ctx, category):
    key = game_key(ctx)

    if key in ACTIVE_GAMES:
        await ctx.reply("توجد لعبة جارية في هذه القناة.")
        return

    word, hint = fresh_question(category)

    view = WordGuessView(
        ctx.author.id,
        ctx.guild.id,
        word,
        hint,
    )

    ACTIVE_GAMES[key] = view

    await ctx.send(
        embed=embed(
            "🔤 خمن الكلمة",
            f"{hint}\n\n"
            f"لديك **{GAME_DURATION} ثانية** للإجابة.",
        ),
        view=view,
    )

    await asyncio.sleep(GAME_DURATION)

    if not view.answered:
        view.answered = True
        for child in view.children:
            child.disabled = True

        await ctx.send(
            f"⏰ انتهى الوقت! الكلمة كانت **{word}**."
        )

    await unregister_game(ctx)


@bot.command(name="خمن الكلمة")
@commands.guild_only()
async def word_command(ctx):
    await start_word_game(ctx, "objects")


@bot.command(name="خمن الدولة")
@commands.guild_only()
async def country_command(ctx):
    await start_word_game(ctx, "countries")


@bot.command(name="خمن اللون")
@commands.guild_only()
async def color_command(ctx):
    await start_word_game(ctx, "colors")


@bot.command(name="حروف الكلمة")
@commands.guild_only()
async def letters_command(ctx):
    await start_word_game(ctx, "animals")


@bot.command(name="معلومات", aliases=["تحدي المعلومات"])
@commands.guild_only()
async def trivia_command(ctx):
    key = game_key(ctx)

    if key in ACTIVE_GAMES:
        await ctx.reply("توجد لعبة جارية في هذه القناة.")
        return

    question, options, correct_index = random.choice(TRIVIA)
    players = {ctx.author.id}

    view = TriviaView(
        ctx.guild.id,
        question,
        options,
        correct_index,
        players,
    )

    ACTIVE_GAMES[key] = view

    await ctx.send(
        embed=embed(
            "🧠 تحدي المعلومات",
            f"{question}\n\n"
            "اختر الإجابة الصحيحة من الأزرار.",
        ),
        view=view,
    )

    await asyncio.sleep(GAME_DURATION)

    if not view.is_finished():
        await ctx.send(
            f"انتهى الوقت. الإجابة الصحيحة: **{options[correct_index]}**"
        )

    await unregister_game(ctx)


@bot.command(name="تحدي الذاكرة")
@commands.guild_only()
async def memory_command(ctx):
    symbols = [
        "🍎", "🚗", "⭐", "🌙", "🐬", "🎈", "🌵", "🎸",
        "⚽", "📚", "🌈", "🦋", "🍉", "🧩", "🚀", "🏀",
        "🎨", "🐢", "🌻", "🛶", "🎯", "🦉", "🪁", "🍇",
        "🧸", "🪴", "🎺", "🛴", "🍋", "🐳", "🪐", "🧁",
    ]

    sequence = random.sample(symbols, 5)
    view = MemoryView(ctx.author.id, ctx.guild.id, sequence)

    await ctx.send(
        embed=embed(
            "🧠 تحدي الذاكرة",
            "احفظ الرموز التالية بالترتيب:\n\n"
            f"{' '.join(sequence)}\n\n"
            "سيتم إخفاؤها بعد 7 ثوانٍ.",
        ),
        view=view,
    )

    await asyncio.sleep(7)

    try:
        await ctx.send(
            embed=embed(
                "🧠 انتهى وقت الحفظ",
                "اضغط زر الاختبار ثم اكتب الرموز بالترتيب.",
            ),
            view=view,
        )
    except discord.HTTPException:
        pass


@bot.command(name="الرياضيات")
@commands.guild_only()
async def math_command(ctx):
    a = random.randint(2, 30)
    b = random.randint(2, 30)
    operation = random.choice(["+", "-", "*"])

    if operation == "+":
        answer = a + b
    elif operation == "-":
        if b > a:
            a, b = b, a
        answer = a - b
    else:
        answer = a * b

    await send_numeric_challenge(ctx, f"{a} {operation} {b}", answer)


@bot.command(name="الرقم السري")
@commands.guild_only()
async def number_command(ctx):
    answer = random.randint(10, 99)
    await send_numeric_challenge(
        ctx,
        "خمن عددًا من رقمين",
        answer,
        numeric=True,
    )


@bot.command(name="اكمل التسلسل")
@commands.guild_only()
async def sequence_command(ctx):
    start = random.randint(1, 20)
    step = random.randint(2, 9)
    sequence = [start + i * step for i in range(4)]
    answer = sequence[-1] + step

    await send_numeric_challenge(
        ctx,
        f"أكمل التسلسل: {sequence[0]}, {sequence[1]}, "
        f"{sequence[2]}, {sequence[3]}, ؟",
        answer,
        numeric=True,
    )


async def send_numeric_challenge(ctx, question, answer, numeric=False):
    key = game_key(ctx)

    if key in ACTIVE_GAMES:
        await ctx.reply("توجد لعبة جارية في هذه القناة.")
        return

    view = NumericGuessView(
        ctx.author.id,
        ctx.guild.id,
        answer,
        numeric,
    )
    ACTIVE_GAMES[key] = view

    await ctx.send(
        embed=embed(
            "🧩 تحدي جديد",
            f"{question}\n\n"
            f"لديك {GAME_DURATION} ثانية للإجابة.",
        ),
        view=view,
    )

    await asyncio.sleep(GAME_DURATION)

    if not view.answered:
        view.answered = True
        await ctx.send(f"⏰ انتهى الوقت! الإجابة: **{answer}**")

    await unregister_game(ctx)


class NumericGuessView(discord.ui.View):
    def __init__(self, owner_id, guild_id, answer, numeric=False):
        super().__init__(timeout=GAME_DURATION)
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.answer = answer
        self.numeric = numeric
        self.answered = False

    @discord.ui.button(label="إرسال الإجابة", style=discord.ButtonStyle.success)
    async def answer_button(self, interaction, button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "هذه الجولة ليست لك.",
                ephemeral=True,
            )
            return

        if self.answered:
            await interaction.response.send_message(
                "انتهت الجولة.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(NumericModal(self))


class NumericModal(discord.ui.Modal, title="إجابتك"):
    answer = discord.ui.TextInput(
        label="الإجابة",
        placeholder="اكتب الإجابة",
        max_length=30,
    )

    def __init__(self, game_view):
        super().__init__()
        self.game_view = game_view

    async def on_submit(self, interaction):
        view = self.game_view
        view.answered = True

        try:
            correct = int(self.answer.value.strip()) == int(view.answer)
        except ValueError:
            correct = False

        if correct:
            add_points(view.guild_id, view.owner_id, WIN_POINTS)
            result = f"✅ إجابة صحيحة! حصلت على {WIN_POINTS} نقاط."
        else:
            result = f"❌ الإجابة الصحيحة: {view.answer}"

        await interaction.response.send_message(result)
        view.stop()


# ============================================================
# IMAGE GAME
# ============================================================

@bot.command(name="خمن الرسمة")
@commands.guild_only()
async def drawing_command(ctx):
    key = game_key(ctx)

    if key in ACTIVE_GAMES:
        await ctx.reply("توجد لعبة جارية في هذه القناة.")
        return

    word = fresh_word("objects")
    image_file = puzzle_image(word)

    if image_file is None:
        await ctx.reply(
            "تحتاج اللعبة إلى Pillow. أضف `Pillow` إلى requirements.txt."
        )
        return

    file = discord.File(image_file, filename="crystal_puzzle.png")
    view = WordGuessView(
        ctx.author.id,
        ctx.guild.id,
        word,
        "ما الشيء الذي تمثله الرسمة؟",
    )

    ACTIVE_GAMES[key] = view

    await ctx.send(
        embed=embed(
            "🎨 خمن الرسمة",
            "خمن الشيء الظاهر في الصورة.\n"
            "كل جولة تنشئ رسمة جديدة.",
        ),
        file=file,
        view=view,
    )

    await asyncio.sleep(GAME_DURATION)

    if not view.answered:
        view.answered = True
        await ctx.send(f"⏰ انتهى الوقت! الإجابة: **{word}**")

    await unregister_game(ctx)


# ============================================================
# OTHER GAME COMMANDS
# ============================================================

@bot.command(name="أسرع كاتب", aliases=["اسرع كاتب"])
@commands.guild_only()
async def typing_command(ctx):
    phrases = [
        "العلم نور",
        "الصدق منجاة",
        "الوقت ثمين",
        "التعاون قوة",
        "القراءة غذاء العقل",
        "النجاح يحتاج صبرًا",
        "الإبداع يبدأ بفكرة",
        "التعلم رحلة مستمرة",
        "العمل المتقن يثمر",
        "الاحترام أساس التعامل",
        "الصبر مفتاح الفرج",
        "المعرفة تبني المستقبل",
        "التخطيط طريق الإنجاز",
        "التركيز يساعد على النجاح",
        "الكلمة الطيبة أثر جميل",
        "التفكير يصنع الفرق",
        "التجربة تعلم الإنسان",
        "الإتقان دليل التميز",
        "المثابرة تقرب الهدف",
        "التعاون يحقق الإنجاز",
    ]

    phrase = random.choice(phrases)

    await ctx.send(
        embed=embed(
            "⌨️ أسرع كاتب",
            f"اكتب العبارة التالية كما هي:\n\n**{phrase}**\n\n"
            f"المدة: {GAME_DURATION} ثانية.",
        )
    )

    def check(message):
        return (
            message.channel.id == ctx.channel.id
            and message.author != bot.user
            and normalize(message.content) == normalize(phrase)
        )

    try:
        message = await bot.wait_for(
            "message",
            timeout=GAME_DURATION,
            check=check,
        )
        add_points(ctx.guild.id, message.author.id, WIN_POINTS)
        await ctx.send(
            f"🏆 أسرع كاتب: {message.author.mention} "
            f"وحصل على {WIN_POINTS} نقاط."
        )
    except asyncio.TimeoutError:
        await ctx.send("⏰ انتهى الوقت دون إجابة صحيحة.")


@bot.command(name="رتب الحروف")
@commands.guild_only()
async def scramble_command(ctx):
    word = fresh_word("animals")
    letters = list(word.replace(" ", ""))
    scrambled = letters[:]

    for _ in range(10):
        random.shuffle(scrambled)
        if "".join(scrambled) != "".join(letters):
            break

    await ctx.send(
        embed=embed(
            "🔀 رتب الحروف",
            f"الكلمة: **{' '.join(scrambled)}**\n"
            "اكتب الكلمة الصحيحة خلال 30 ثانية.",
        )
    )

    def check(message):
        return (
            message.channel.id == ctx.channel.id
            and message.author != bot.user
            and normalize(message.content.replace(" ", "")) == normalize(word.replace(" ", ""))
        )

    try:
        message = await bot.wait_for(
            "message",
            timeout=GAME_DURATION,
            check=check,
        )
        add_points(ctx.guild.id, message.author.id, WIN_POINTS)
        await ctx.send(f"✅ أحسنت {message.author.mention}!")
    except asyncio.TimeoutError:
        await ctx.send(f"⏰ انتهى الوقت. الكلمة: **{word}**")


@bot.command(name="فك الايموجي", aliases=["فك الإيموجي"])
@commands.guild_only()
async def emoji_command(ctx):
    puzzles = [
        ("🐪🌵☀️", "الصحراء"),
        ("🌧️☂️", "المطر"),
        ("🌙⭐", "الليل"),
        ("📚✏️🏫", "المدرسة"),
        ("🍎🍌🍇", "فواكه"),
        ("🚗🛣️", "الطريق"),
        ("🌊🏖️", "الشاطئ"),
        ("🧑‍🍳🍲", "الطبخ"),
        ("🪥🦷", "فرشاة الأسنان"),
        ("✈️🧳", "السفر"),
        ("🐝🍯", "العسل"),
        ("🌱💧☀️", "النبات"),
        ("📷🖼️", "التصوير"),
        ("🧊🥤", "مشروب بارد"),
        ("🧹🏠", "تنظيف المنزل"),
        ("🎂🎉", "عيد الميلاد"),
        ("🐟🌊", "سمكة"),
        ("🚲🪖", "ركوب الدراجة"),
        ("🌳🍃", "شجرة"),
        ("🔑🚪", "مفتاح الباب"),
        ("🛏️🌙", "النوم"),
        ("🧑‍🚒🔥", "رجل الإطفاء"),
        ("📦🚚", "التوصيل"),
        ("🌻🐝", "زهرة"),
        ("🥛🐄", "الحليب"),
    ]

    puzzle, answer = random.choice(puzzles)

    await ctx.send(
        embed=embed(
            "😂 فك الإيموجي",
            f"ماذا تعني هذه الرموز؟\n\n{puzzle}\n\n"
            f"لديك {GAME_DURATION} ثانية.",
        )
    )

    def check(message):
        return (
            message.channel.id == ctx.channel.id
            and message.author != bot.user
            and normalize(message.content) == normalize(answer)
        )

    try:
        message = await bot.wait_for(
            "message",
            timeout=GAME_DURATION,
            check=check,
        )
        add_points(ctx.guild.id, message.author.id, WIN_POINTS)
        await ctx.send(f"🏆 إجابة صحيحة يا {message.author.mention}!")
    except asyncio.TimeoutError:
        await ctx.send(f"⏰ الإجابة: **{answer}**")


@bot.command(name="سلسلة الكلمات")
@commands.guild_only()
async def chain_command(ctx):
    first = fresh_word("animals")
    last_letter = first[-1]
    await ctx.send(
        embed=embed(
            "💬 سلسلة الكلمات",
            f"الكلمة الأولى: **{first}**\n"
            f"اكتب كلمة تبدأ بحرف **{last_letter}**.\n"
            "تستمر السلسلة 30 ثانية.",
        )
    )

    current_letter = last_letter
    used = {normalize(first)}
    scores = defaultdict(int)
    end_time = time.monotonic() + GAME_DURATION

    while time.monotonic() < end_time:
        try:
            message = await bot.wait_for(
                "message",
                timeout=max(0.1, end_time - time.monotonic()),
                check=lambda m: (
                    m.channel.id == ctx.channel.id
                    and not m.author.bot
                ),
            )
        except asyncio.TimeoutError:
            break

        word = message.content.strip()

        if not re.fullmatch(r"[\u0600-\u06FF]+", word):
            continue

        key = normalize(word)

        if key in used or not key.startswith(current_letter):
            continue

        used.add(key)
        current_letter = word[-1]
        scores[message.author.id] += 1

        await ctx.send(
            f"✅ {message.author.mention}: **{word}** "
            f"— الحرف التالي **{current_letter}**"
        )

    if scores:
        winner = max(scores, key=scores.get)
        add_points(ctx.guild.id, winner, WIN_POINTS)
        await ctx.send(
            f"🏆 الفائز: {user_mention(winner)} "
            f"بعدد **{scores[winner]}** كلمات."
        )
    else:
        await ctx.send("انتهت الجولة دون كلمات صحيحة.")


@bot.command(name="سرعة الاستجابة")
@commands.guild_only()
async def reaction_command(ctx):
    await ctx.send("استعد... انتظر ظهور الإشارة.")
    await asyncio.sleep(random.uniform(2, 5))

    start = time.perf_counter()
    message = await ctx.send("🟢 اضغط بإرسال `!` الآن!")

    def check(m):
        return (
            m.channel.id == ctx.channel.id
            and not m.author.bot
            and m.content.strip() == "!"
        )

    try:
        response = await bot.wait_for(
            "message",
            timeout=15,
            check=check,
        )
        elapsed = time.perf_counter() - start
        add_points(ctx.guild.id, response.author.id, WIN_POINTS)
        await ctx.send(
            f"⚡ {response.author.mention} استجاب خلال "
            f"**{elapsed:.3f} ثانية**!"
        )
    except asyncio.TimeoutError:
        await ctx.send("انتهى الوقت.")


@bot.command(name="البحث عن الكلمات")
@commands.guild_only()
async def wordsearch_command(ctx):
    words = random.sample(WORD_BANKS["animals"], 3)
    letters = [list(word.replace(" ", "")[:5].ljust(5, "X")) for word in words]
    rows = [" ".join(row) for row in letters]

    await ctx.send(
        embed=embed(
            "🔠 البحث عن الكلمات",
            "ابحث عن أسماء ثلاثة حيوانات في الشبكة:\n\n"
            + "\n".join(f"`{row}`" for row in rows)
            + "\n\nاكتب أسماء الحيوانات مفصولة بمسافة.",
        )
    )

    answers = {normalize(w) for w in words}

    def check(message):
        if message.channel.id != ctx.channel.id or message.author.bot:
            return False
        provided = {
            normalize(part)
            for part in message.content.split()
        }
        return answers.issubset(provided)

    try:
        message = await bot.wait_for(
            "message",
            timeout=GAME_DURATION,
            check=check,
        )
        add_points(ctx.guild.id, message.author.id, WIN_POINTS)
        await ctx.send(f"🏆 ممتاز يا {message.author.mention}!")
    except asyncio.TimeoutError:
        await ctx.send(
            "انتهى الوقت. الكلمات المطلوبة: " + "، ".join(words)
        )


@bot.command(name="اكتشف النمط", aliases=["تحدي الانماط"])
@commands.guild_only()
async def pattern_command(ctx):
    start = random.randint(1, 10)
    step = random.randint(2, 8)
    seq = [start + i * step for i in range(4)]
    answer = seq[-1] + step

    await send_numeric_challenge(
        ctx,
        "اكتشف النمط: " + "، ".join(map(str, seq)) + "، ؟",
        answer,
        numeric=True,
    )


@bot.command(name="ترتيب البطاقات")
@commands.guild_only()
async def cards_command(ctx):
    values = random.sample(range(1, 100), 5)
    scrambled = values[:]
    random.shuffle(scrambled)

    await ctx.send(
        embed=embed(
            "🧩 ترتيب البطاقات",
            "رتب الأرقام تصاعديًا واكتبها مفصولة بمسافات:\n\n"
            + " • ".join(map(str, scrambled)),
        )
    )

    expected = " ".join(map(str, sorted(values)))

    def check(message):
        return (
            message.channel.id == ctx.channel.id
            and not message.author.bot
            and re.sub(r"\s+", " ", message.content.strip()) == expected
        )

    try:
        message = await bot.wait_for(
            "message",
            timeout=GAME_DURATION,
            check=check,
        )
        add_points(ctx.guild.id, message.author.id, WIN_POINTS)
        await ctx.send(f"🏆 أحسنت {message.author.mention}!")
    except asyncio.TimeoutError:
        await ctx.send(f"الإجابة الصحيحة: **{expected}**")


# ============================================================
# STUB GAME COMMANDS — UNIQUE ROUND DATA
# ============================================================

@bot.command(name="الكراسي الموسيقية")
@commands.guild_only()
async def chairs_command(ctx):
    await ctx.send(
        embed=embed(
            "🎵 الكراسي الموسيقية",
            "انضموا عبر `+روليت` لتحدي جماعي سريع، "
            "أو استخدموا بطولة التحديات للمنافسة بالنقاط.",
        )
    )


@bot.command(name="الغميضة")
@commands.guild_only()
async def hide_command(ctx):
    players = random.sample(WORD_BANKS["places"], 3)
    await ctx.send(
        embed=embed(
            "🫣 الغميضة",
            "اختر المكان الذي تعتقد أن اللاعب المختبئ فيه:\n"
            + "\n".join(f"{i}. {p}" for i, p in enumerate(players, 1)),
        )
    )


@bot.command(name="اكتشف الكذب")
@commands.guild_only()
async def lie_command(ctx):
    rounds = [
        [
            "الشمس نجم.",
            "المثلث له أربعة أضلاع.",
            "الأرض كوكب.",
        ],
        [
            "الماء يتكون من الهيدروجين والأكسجين.",
            "الأسبوع فيه سبعة أيام.",
            "الشمس تدور حول الأرض مرة كل يوم.",
        ],
        [
            "القمر تابع طبيعي للأرض.",
            "الإنسان لديه قلب.",
            "الصوت ينتقل في الفراغ مثل الضوء.",
        ],
    ]

    statements = random.choice(rounds)
    wrong_index = next(
        (
            i for i, statement in enumerate(statements)
            if statement in {
                "المثلث له أربعة أضلاع.",
                "الشمس تدور حول الأرض مرة كل يوم.",
                "الصوت ينتقل في الفراغ مثل الضوء.",
            }
        ),
        0,
    )

    await ctx.send(
        embed=embed(
            "🤥 اكتشف العبارة الخاطئة",
            "\n".join(
                f"{i + 1}. {statement}"
                for i, statement in enumerate(statements)
            )
            + "\n\nاكتب رقم العبارة الخاطئة.",
        )
    )

    def check(message):
        return (
            message.channel.id == ctx.channel.id
            and not message.author.bot
            and message.content.strip() in {"1", "2", "3"}
        )

    try:
        response = await bot.wait_for(
            "message",
            timeout=GAME_DURATION,
            check=check,
        )
        if int(response.content) - 1 == wrong_index:
            add_points(ctx.guild.id, response.author.id, WIN_POINTS)
            await ctx.send(f"✅ صحيح يا {response.author.mention}!")
        else:
            await ctx.send(
                f"❌ العبارة الخاطئة رقم {wrong_index + 1}."
            )
    except asyncio.TimeoutError:
        await ctx.send("انتهى الوقت.")


@bot.command(name="المحقق")
@commands.guild_only()
async def detective_command(ctx):
    cases = [
        ("اختفى كتاب من المكتبة. كان ثلاثة أشخاص في المكان.", [
            "أحمد: كنت أقرأ في الغرفة.",
            "سارة: كنت أرتب الرفوف.",
            "خالد: كنت في الخارج.",
        ]),
        ("وجدت آثار أقدام قرب الباب المغلق.", [
            "ليلى: وصلت قبل الجميع.",
            "مازن: كنت أحمل صندوقًا.",
            "نور: لم أدخل الغرفة.",
        ]),
        ("اختفت قطعة من لوحة الأحجية.", [
            "ريم: كنت أبحث عن القلم.",
            "عمر: كنت أراجع التعليمات.",
            "فهد: كنت أرتب الطاولة.",
        ]),
    ]

    case, clues = random.choice(cases)

    await ctx.send(
        embed=embed(
            "🔎 قضية المحقق",
            f"{case}\n\n" + "\n".join(clues)
            + "\n\nاكتب استنتاجك في رسالة.",
        )
    )


@bot.command(name="بطولة التحديات")
@commands.guild_only()
async def tournament_command(ctx):
    await ctx.send(
        embed=embed(
            "🏆 بطولة التحديات",
            "ابدؤوا التحديات التالية بالتتابع:\n"
            "• `+معلومات`\n"
            "• `+رتب الحروف`\n"
            "• `+سرعة الاستجابة`\n"
            "• `+تحدي الذاكرة`\n\n"
            "تُحسب النقاط لكل لاعب من نتائج الألعاب.",
        )
    )


@bot.command(name="البحث عن الكنز")
@commands.guild_only()
async def treasure_command(ctx):
    clues = [
        ("أبحث عن شيء يفتح الأبواب، ما هو؟", "مفتاح"),
        ("أبحث عن مكان يحتوي الكتب، ما هو؟", "مكتبة"),
        ("أبحث عن شيء يخبرك بالوقت، ما هو؟", "ساعة"),
        ("أبحث عن شيء يضيء الغرفة، ما هو؟", "مصباح"),
        ("أبحث عن شيء يحميك من المطر، ما هو؟", "مظلة"),
        ("أبحث عن وسيلة تنقلك على عجلتين، ما هي؟", "دراجة"),
        ("أبحث عن شيء تكتب به، ما هو؟", "قلم"),
        ("أبحث عن شيء تحفظ فيه الطعام باردًا، ما هو؟", "ثلاجة"),
        ("أبحث عن مكان تقلع منه الطائرات، ما هو؟", "مطار"),
        ("أبحث عن شيء يعرض الصور المتحركة، ما هو؟", "تلفاز"),
    ]

    clue, answer = random.choice(clues)

    await ctx.send(
        embed=embed(
            "🗺️ البحث عن الكنز",
            clue + "\n\nلديك 30 ثانية للوصول إلى الإجابة.",
        )
    )

    def check(message):
        return (
            message.channel.id == ctx.channel.id
            and not message.author.bot
            and normalize(message.content) == normalize(answer)
        )

    try:
        response = await bot.wait_for(
            "message",
            timeout=GAME_DURATION,
            check=check,
        )
        add_points(ctx.guild.id, response.author.id, WIN_POINTS)
        await ctx.send(f"🏆 وجد الكنز {response.author.mention}!")
    except asyncio.TimeoutError:
        await ctx.send(f"انتهى الوقت. الإجابة: **{answer}**")


@bot.command(name="اكتشف الاختلاف")
@commands.guild_only()
async def difference_command(ctx):
    symbols = ["🔵", "🟢", "🟡", "🔴", "🟣", "🟠"]
    target = random.choice(symbols)
    grid = [random.choice(symbols) for _ in range(20)]
    index = random.randrange(len(grid))
    grid[index] = target

    other = random.choice([symbol for symbol in symbols if symbol != target])
    grid[index] = other

    rows = [
        " ".join(grid[i:i + 5])
        for i in range(0, len(grid), 5)
    ]

    await ctx.send(
        embed=embed(
            "👀 اكتشف الرمز المختلف",
            "\n".join(rows)
            + "\n\nاكتب الرمز المختلف كما يظهر.",
        )
    )

    def check(message):
        return (
            message.channel.id == ctx.channel.id
            and not message.author.bot
            and message.content.strip() == other
        )

    try:
        response = await bot.wait_for(
            "message",
            timeout=GAME_DURATION,
            check=check,
        )
        add_points(ctx.guild.id, response.author.id, WIN_POINTS)
        await ctx.send(f"🏆 أحسنت {response.author.mention}!")
    except asyncio.TimeoutError:
        await ctx.send(f"الرمز المختلف هو {other}")


@bot.command(name="تحدي الانماط")
@commands.guild_only()
async def pattern_alias_command(ctx):
    await pattern_command(ctx)


# ============================================================
# GLOBAL ERROR HANDLING
# ============================================================

@bot.event
async def on_ready():
    log.info("Logged in as %s (%s)", bot.user, bot.user.id)
    log.info("CRYSTAL Games Bot is ready.")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(
            f"❌ ينقصك خيار. اكتب `+العاب` لعرض الألعاب."
        )
        return

    if isinstance(error, commands.BadArgument):
        await ctx.reply("❌ تأكد من كتابة الأمر والعضو بشكل صحيح.")
        return

    if isinstance(error, commands.NoPrivateMessage):
        await ctx.reply("هذا الأمر يعمل داخل السيرفر فقط.")
        return

    log.exception(
        "Command error in %s",
        getattr(ctx.command, "name", "unknown"),
        exc_info=error,
    )

    try:
        await ctx.reply("❌ حدث خطأ أثناء تنفيذ اللعبة.")
    except discord.HTTPException:
        pass


# ============================================================
# STARTUP
# ============================================================

async def main():
    if not TOKEN:
        raise RuntimeError(
            "DISCORD_TOKEN is missing. Add it in the hosting environment."
        )

    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    asyncio.run(main())
