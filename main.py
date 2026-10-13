# ============================================================
# CRYSTAL STORE — MAIN.PY
# Discord Store Server Setup Bot
# Python 3.12+ | discord.py 2.7.1
# ============================================================

import os
import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands
from flask import Flask, jsonify
from threading import Thread

# ============================================================
# CONFIGURATION
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

SERVER_NAME = "𝗖𝗥𝗬𝗦𝗧𝗔𝗟 store"
CATEGORY_SUFFIX = "꡴"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("crystal-store")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="-", intents=intents)

# ============================================================
# WEB SERVER — RENDER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return f"{SERVER_NAME} is Online!"


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "bot": SERVER_NAME,
        "discord": bot.is_ready(),
    })


def run_web():
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)


# ============================================================
# STORE ROLES
# ============================================================

ROLE_DEFINITIONS = [
    ("👑・𝐎𝐖𝐍𝐄𝐑", discord.Permissions.all()),
    (
        "🛡️・𝐌𝐀𝐍𝐀𝐆𝐄𝐑",
        discord.Permissions(
            view_audit_log=True,
            manage_guild=True,
            manage_channels=True,
            manage_roles=True,
            manage_messages=True,
            kick_members=True,
            ban_members=True,
            moderate_members=True,
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        ),
    ),
    (
        "🔨・𝐌𝐎𝐃𝐄𝐑𝐀𝐓𝐎𝐑",
        discord.Permissions(
            view_audit_log=True,
            manage_messages=True,
            kick_members=True,
            moderate_members=True,
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        ),
    ),
    (
        "🎫・𝐒𝐔𝐏𝐏𝐎𝐑𝐓",
        discord.Permissions(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True,
        ),
    ),
    ("💎・𝐂𝐑𝐘𝐒𝐓𝐀𝐋", discord.Permissions.none()),
    ("💠・𝐍𝐈𝐓𝐑𝐎", discord.Permissions.none()),
    ("🚀・𝐁𝐎𝐎𝐒𝐓𝐄𝐑", discord.Permissions.none()),
    ("📺・𝐍𝐄𝐓𝐅𝐋𝐈𝐗", discord.Permissions.none()),
    ("💳・𝐂𝐑𝐄𝐃𝐈𝐓", discord.Permissions.none()),
    ("🎁・𝐆𝐈𝐅𝐓𝐒", discord.Permissions.none()),
    ("📦・𝐎𝐑𝐃𝐄𝐑𝐒", discord.Permissions.none()),
    ("🛍️・𝐂𝐔𝐒𝐓𝐎𝐌𝐄𝐑", discord.Permissions.none()),
    ("⭐・𝐕𝐈𝐏", discord.Permissions.none()),
    ("👤・𝐌𝐄𝐌𝐁𝐄𝐑", discord.Permissions.none()),
]

# ============================================================
# CATEGORY AND CHANNEL LAYOUT
# Every category name ends in ꡴
# ============================================================

CATEGORY_LAYOUT = {
    "『 CRYSTAL STORE ꡴ 』": [
        ("📢・announcements", "text"),
        ("📜・store-rules", "text"),
        ("💎・store-info", "text"),
        ("🛍️・shop", "text"),
        ("🎟️・open-ticket", "text"),
    ],
    "『 CRYSTAL PRODUCTS ꡴ 』": [
        ("📺・netflix", "text"),
        ("💎・nitro", "text"),
        ("🚀・boosts", "text"),
        ("📦・accounts", "text"),
        ("💳・credits", "text"),
        ("🎁・gifts", "text"),
        ("🛒・other-products", "text"),
    ],
    "『 CRYSTAL ORDERS ꡴ 』": [
        ("🧾・order-info", "text"),
        ("💰・payment-methods", "text"),
        ("📨・proof-of-payment", "text"),
        ("⭐・customer-reviews", "text"),
    ],
    "『 CRYSTAL COMMUNITY ꡴ 』": [
        ("💬・general-chat", "text"),
        ("🤖・bot-commands", "text"),
        ("📸・media", "text"),
        ("📊・suggestions", "text"),
    ],
    "『 CRYSTAL VOICE ꡴ 』": [
        ("🔊・general", "voice"),
        ("🎮・gaming", "voice"),
        ("💎・vip-room", "voice"),
        ("🎫・support-room", "voice"),
    ],
    "『 CRYSTAL STAFF ꡴ 』": [
        ("🔒・staff-chat", "text"),
        ("📋・staff-orders", "text"),
        ("🛡️・moderation-logs", "text"),
        ("📑・staff-notes", "text"),
    ],
}

# ============================================================
# EMBED COLORS
# ============================================================

CRYSTAL_COLOR = discord.Color.from_rgb(90, 200, 255)


def make_embed(title, description):
    embed = discord.Embed(
        title=title,
        description=description,
        color=CRYSTAL_COLOR,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text="𝗖𝗥𝗬𝗦𝗧𝗔𝗟 store")
    return embed


# ============================================================
# PERMISSION HELPERS
# ============================================================

def is_manager():
    async def predicate(ctx):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return False

        return (
            ctx.author.guild_permissions.administrator
            or ctx.author.guild_permissions.manage_guild
        )

    return commands.check(predicate)


# ============================================================
# SERVER SETUP
# ============================================================

async def get_or_create_role(guild, name, permissions):
    role = discord.utils.get(guild.roles, name=name)

    if role is None:
        role = await guild.create_role(
            name=name,
            permissions=permissions,
            reason="CRYSTAL STORE server setup",
        )

    return role


async def get_or_create_category(guild, name):
    category = discord.utils.get(guild.categories, name=name)

    if category is None:
        category = await guild.create_category(
            name=name,
            reason="CRYSTAL STORE server setup",
        )

    return category


async def get_or_create_channel(guild, category, channel_name, kind):
    existing = discord.utils.get(
        category.channels,
        name=channel_name,
    )

    if existing is not None:
        return existing

    if kind == "voice":
        return await guild.create_voice_channel(
            name=channel_name,
            category=category,
            reason="CRYSTAL STORE server setup",
        )

    return await guild.create_text_channel(
        name=channel_name,
        category=category,
        reason="CRYSTAL STORE server setup",
    )


@bot.command(name="setupstore")
@is_manager()
@commands.guild_only()
async def setup_store(ctx):
    """إنشاء رتب وأقسام وقنوات المتجر."""

    guild = ctx.guild

    status = await ctx.reply(
        embed=make_embed(
            "💎 CRYSTAL STORE",
            "جاري تجهيز الرتب والأقسام والقنوات...\n"
            "قد يستغرق هذا بعض الوقت.",
        )
    )

    created_roles = 0
    created_categories = 0
    created_channels = 0
    errors = []

    try:
        # Create roles.
        for name, permissions in ROLE_DEFINITIONS:
            try:
                before = discord.utils.get(guild.roles, name=name)
                await get_or_create_role(guild, name, permissions)

                if before is None:
                    created_roles += 1

                await asyncio.sleep(0.35)

            except discord.HTTPException as exc:
                errors.append(f"رتبة {name}: {exc}")

        # Create categories and channels.
        for category_name, channels in CATEGORY_LAYOUT.items():
            try:
                before = discord.utils.get(
                    guild.categories,
                    name=category_name,
                )

                category = await get_or_create_category(
                    guild,
                    category_name,
                )

                if before is None:
                    created_categories += 1

                for channel_name, kind in channels:
                    try:
                        before_channel = discord.utils.get(
                            category.channels,
                            name=channel_name,
                        )

                        await get_or_create_channel(
                            guild,
                            category,
                            channel_name,
                            kind,
                        )

                        if before_channel is None:
                            created_channels += 1

                        await asyncio.sleep(0.35)

                    except discord.HTTPException as exc:
                        errors.append(f"قناة {channel_name}: {exc}")

            except discord.HTTPException as exc:
                errors.append(f"قسم {category_name}: {exc}")

        result = make_embed(
            "✅ CRYSTAL STORE — اكتمل التجهيز",
            (
                f"**السيرفر:** {guild.name}\n"
                f"**الرتب الجديدة:** {created_roles}\n"
                f"**الأقسام الجديدة:** {created_categories}\n"
                f"**القنوات الجديدة:** {created_channels}\n\n"
                "تم الحفاظ على القنوات والرتب الموجودة."
            ),
        )

        if errors:
            result.add_field(
                name="⚠️ عناصر تعذر إنشاؤها",
                value="\n".join(errors)[:1000],
                inline=False,
            )

        await status.edit(embed=result)

    except Exception:
        log.exception("Store setup failed")
        await status.edit(
            embed=make_embed(
                "❌ حدث خطأ",
                "تعذر إكمال الإعداد. تحقق من صلاحيات البوت وسجلات التشغيل.",
            )
        )


# ============================================================
# STORE INFORMATION PANEL
# ============================================================

class StorePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🛍️ المنتجات",
        style=discord.ButtonStyle.primary,
        custom_id="crystal:products",
    )
    async def products(self, interaction, button):
        await interaction.response.send_message(
            embed=make_embed(
                "🛍️ CRYSTAL PRODUCTS",
                "تصفح أقسام المنتجات:\n\n"
                "📺 Netflix\n"
                "💎 Nitro\n"
                "🚀 Server Boosts\n"
                "💳 Credits\n"
                "🎁 Gifts\n"
                "📦 Other Products\n\n"
                "افتح تذكرة للاستفسار عن المنتجات والأسعار.",
            ),
            ephemeral=True,
        )

    @discord.ui.button(
        label="🎫 الدعم الفني",
        style=discord.ButtonStyle.success,
        custom_id="crystal:support",
    )
    async def support(self, interaction, button):
        await interaction.response.send_message(
            "افتح تذكرة من قناة **🎟️・open-ticket** للتواصل مع الدعم.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="📜 القوانين",
        style=discord.ButtonStyle.secondary,
        custom_id="crystal:rules",
    )
    async def rules(self, interaction, button):
        await interaction.response.send_message(
            embed=make_embed(
                "📜 قوانين CRYSTAL STORE",
                "1. الاحترام واجب للجميع.\n"
                "2. يمنع الاحتيال أو انتحال الشخصية.\n"
                "3. لا تكرر الطلبات أو الرسائل المزعجة.\n"
                "4. تحقق من تفاصيل المنتج قبل الشراء.\n"
                "5. لا ترسل بياناتك السرية أو كلمات مرورك.\n"
                "6. استخدم التذاكر الرسمية للدعم.",
            ),
            ephemeral=True,
        )


@bot.command(name="panel")
@is_manager()
@commands.guild_only()
async def send_panel(ctx):
    embed = make_embed(
        "💎 𝗖𝗥𝗬𝗦𝗧𝗔𝗟 store",
        "مرحباً بك في متجر CRYSTAL.\n\n"
        "🛍️ منتجات متنوعة\n"
        "🎫 دعم فني\n"
        "📦 متابعة الطلبات\n"
        "⭐ خدمة العملاء\n\n"
        "استخدم الأزرار أدناه للوصول إلى المعلومات.",
    )

    await ctx.send(embed=embed, view=StorePanel())


# ============================================================
# MEMBER JOIN
# ============================================================

@bot.event
async def on_member_join(member):
    role = discord.utils.get(
        member.guild.roles,
        name="👤・𝐌𝐄𝐌𝐁𝐄𝐑",
    )

    if role:
        try:
            await member.add_roles(
                role,
                reason="CRYSTAL STORE automatic member role",
            )
        except discord.HTTPException:
            log.exception("Could not assign member role")

    channel = discord.utils.get(
        member.guild.text_channels,
        name="📢・announcements",
    )

    if channel:
        embed = make_embed(
            "💎 عضو جديد في CRYSTAL STORE",
            f"أهلاً بك {member.mention}!\n"
            f"أنت العضو رقم **{member.guild.member_count}**.\n\n"
            "نتمنى لك تجربة ممتعة في متجرنا.",
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            log.exception("Could not send welcome message")


# ============================================================
# MEMBER LEAVE
# ============================================================

@bot.event
async def on_member_remove(member):
    channel = discord.utils.get(
        member.guild.text_channels,
        name="🛡️・moderation-logs",
    )

    if channel:
        try:
            await channel.send(
                embed=make_embed(
                    "👋 مغادرة عضو",
                    f"**العضو:** {member}\n"
                    f"**المعرف:** `{member.id}`",
                )
            )
        except discord.HTTPException:
            pass


# ============================================================
# MODERATION COMMANDS
# ============================================================

@bot.command(name="clear")
@is_manager()
@commands.guild_only()
async def clear_messages(ctx, amount: int = 10):
    if amount < 1 or amount > 100:
        await ctx.reply("حدد عدداً بين 1 و100.")
        return

    deleted = await ctx.channel.purge(
        limit=amount + 1,
        reason=f"Requested by {ctx.author}",
    )

    message = await ctx.send(
        embed=make_embed(
            "🧹 تم تنظيف الشات",
            f"تم حذف **{max(len(deleted) - 1, 0)}** رسالة.",
        )
    )

    await asyncio.sleep(5)

    try:
        await message.delete()
    except discord.HTTPException:
        pass


@bot.command(name="kick")
@is_manager()
@commands.guild_only()
async def kick_member(ctx, member: discord.Member, *, reason="بدون سبب"):
    if member == ctx.author or member == ctx.guild.owner:
        await ctx.reply("لا يمكنك طرد هذا العضو.")
        return

    if member.top_role >= ctx.author.top_role:
        await ctx.reply("رتبتك لا تسمح بطرد هذا العضو.")
        return

    await member.kick(reason=reason)

    await ctx.reply(
        embed=make_embed(
            "🔨 تم طرد العضو",
            f"**العضو:** {member}\n**السبب:** {reason}",
        )
    )


@bot.command(name="ban")
@is_manager()
@commands.guild_only()
async def ban_member(ctx, member: discord.Member, *, reason="بدون سبب"):
    if member == ctx.author or member == ctx.guild.owner:
        await ctx.reply("لا يمكنك حظر هذا العضو.")
        return

    if member.top_role >= ctx.author.top_role:
        await ctx.reply("رتبتك لا تسمح بحظر هذا العضو.")
        return

    await member.ban(reason=reason)

    await ctx.reply(
        embed=make_embed(
            "🔨 تم حظر العضو",
            f"**العضو:** {member}\n**السبب:** {reason}",
        )
    )


@bot.command(name="timeout")
@is_manager()
@commands.guild_only()
async def timeout_member(
    ctx,
    member: discord.Member,
    minutes: int = 10,
    *,
    reason="بدون سبب",
):
    if minutes < 1 or minutes > 40320:
        await ctx.reply("حدد مدة بين دقيقة و40320 دقيقة.")
        return

    if member == ctx.author or member == ctx.guild.owner:
        await ctx.reply("لا يمكنك تطبيق المهلة على هذا العضو.")
        return

    if member.top_role >= ctx.author.top_role:
        await ctx.reply("رتبتك لا تسمح بتطبيق المهلة.")
        return

    await member.timeout(
        discord.utils.utcnow() - discord.utils.utcnow()
        + __import__("datetime").timedelta(minutes=minutes),
        reason=reason,
    )

    await ctx.reply(
        embed=make_embed(
            "⏳ تم تقييد العضو",
            f"**العضو:** {member.mention}\n"
            f"**المدة:** {minutes} دقيقة\n"
            f"**السبب:** {reason}",
        )
    )


@bot.command(name="untimeout")
@is_manager()
@commands.guild_only()
async def untimeout_member(ctx, member: discord.Member):
    await member.timeout(None, reason=f"Requested by {ctx.author}")
    await ctx.reply(f"✅ تم فك التقييد عن {member.mention}.")


# ============================================================
# ROLE MANAGEMENT
# ============================================================

@bot.command(name="role")
@is_manager()
@commands.guild_only()
async def manage_role(ctx, member: discord.Member, *, role_name: str):
    role = discord.utils.get(ctx.guild.roles, name=role_name)

    if role is None:
        await ctx.reply("لم يتم العثور على الرتبة.")
        return

    if role >= ctx.author.top_role:
        await ctx.reply("رتبتك لا تسمح لك بإدارة هذه الرتبة.")
        return

    if role in member.roles:
        await member.remove_roles(role, reason=f"Requested by {ctx.author}")
        action = "إزالة"
    else:
        await member.add_roles(role, reason=f"Requested by {ctx.author}")
        action = "إضافة"

    await ctx.reply(
        embed=make_embed(
            "💎 إدارة الرتب",
            f"تم **{action}** رتبة {role.mention} من {member.mention}.",
        )
    )


# ============================================================
# BOT EVENTS
# ============================================================

@bot.event
async def on_ready():
    log.info("Logged in as %s (%s)", bot.user, bot.user.id)

    if not getattr(bot, "_views_registered", False):
        bot.add_view(StorePanel())
        bot._views_registered = True

    try:
        synced = await bot.tree.sync()
        log.info("Synced %s slash commands", len(synced))
    except discord.HTTPException:
        log.exception("Could not sync slash commands")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.CheckFailure):
        await ctx.reply("❌ هذا الأمر مخصص للإدارة.")
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(
            f"❌ هناك خيار ناقص.\nالاستخدام: `{ctx.prefix}{ctx.command}`"
        )
        return

    if isinstance(error, commands.BadArgument):
        await ctx.reply("❌ تأكد من كتابة البيانات بشكل صحيح.")
        return

    log.error("Command error: %s", error)

    try:
        await ctx.reply("❌ حدث خطأ أثناء تنفيذ الأمر.")
    except discord.HTTPException:
        pass


# ============================================================
# STARTUP
# ============================================================

async def main():
    if not TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN environment variable")

    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    asyncio.run(main())
