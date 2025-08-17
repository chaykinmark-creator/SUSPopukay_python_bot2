import os
import asyncio
import threading

import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput

from flask import Flask

# ========= Flask keep-alive =========
app = Flask(__name__)

@app.get("/")
def home():
    return "OK"

def run_http():
    port = int(os.getenv("PORT", "10000"))  # Render прокидывает PORT
    app.run(host="0.0.0.0", port=port)

# Запустим веб-сервер в фоне
threading.Thread(target=run_http, daemon=True).start()
# ====================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# === ТВОИ КОНСТАНТЫ ===
GUILD_ID = 1399535321200464066
CATEGORY_ID = 1399771689352433735
APPLICATION_CHANNEL_ID = 1399535321200464066
LOG_CHANNEL_ID = 1399783688400670830
DISCORDSRV_CONSOLE_CHANNEL_ID = 1399825640135594265
GUEST_ROLE_NAME = "Гость"
PLAYER_ROLE_NAME = "Игрок"
STAFF_ROLE_NAME = "Заявка-мен"

# !!! Больше НИКАКИХ жёстких токенов в коде !!!
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise SystemExit("❌ Переменная окружения DISCORD_TOKEN не задана.")

COMMAND_FILE_PATH = "commands.txt"  # если оставляешь файловый способ

class ApplicationModal(Modal, title="Заявка на сервер"):
    nickname = TextInput(label="Ваш ник в Minecraft", required=True)
    age = TextInput(label="Сколько вам лет?", required=True)
    found = TextInput(label="Как узнали о проекте?", required=True)
    plans = TextInput(label="Чем планируете заниматься на сервере?", required=True)
    rules = TextInput(label="Прочитали ли вы правила?", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            discord.utils.get(guild.roles, name=STAFF_ROLE_NAME): discord.PermissionOverwrite(read_messages=True)
        }
        category = discord.utils.get(guild.categories, id=CATEGORY_ID)
        channel = await guild.create_text_channel(f"заявка-{member.name}", overwrites=overwrites, category=category)

        embed = discord.Embed(title="Новая заявка", color=discord.Color.green())
        embed.add_field(name="Ник", value=self.nickname.value, inline=False)
        embed.add_field(name="Возраст", value=self.age.value, inline=False)
        embed.add_field(name="Как узнал", value=self.found.value, inline=False)
        embed.add_field(name="Планы", value=self.plans.value, inline=False)
        embed.add_field(name="Прочёл правила", value=self.rules.value, inline=False)

        view = TicketActionView(member, self.nickname.value)
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message("Заявка создана!", ephemeral=True)

class TicketActionView(View):
    def __init__(self, member=None, nickname=None):
        super().__init__(timeout=None)
        self.member = member
        self.nickname = nickname

    @discord.ui.button(label="✅ Принять", style=discord.ButtonStyle.success, custom_id="accept_button")
    async def accept(self, interaction: discord.Interaction, button: Button):
        if not any(role.name == STAFF_ROLE_NAME for role in interaction.user.roles):
            await interaction.response.send_message("❌ У вас нет прав для обработки заявок.", ephemeral=True)
            return
        try:
            guest = discord.utils.get(interaction.guild.roles, name=GUEST_ROLE_NAME)
            player = discord.utils.get(interaction.guild.roles, name=PLAYER_ROLE_NAME)
            if guest in self.member.roles:
                await self.member.remove_roles(guest)
            await self.member.add_roles(player)
            await self.member.edit(nick=self.nickname)

            # Вариант А: файл (как у тебя)
            try:
                with open(COMMAND_FILE_PATH, "a", encoding="utf-8") as f:
                    f.write(f"whitelist add {self.nickname}\n")
            except Exception as e:
                print(f"[WARN] Не удалось записать в файл команд: {e}")

            # Вариант Б: отправить в канал консоли DiscordSRV (рекомендую)
            console_ch = interaction.guild.get_channel(DISCORDSRV_CONSOLE_CHANNEL_ID)
            if console_ch is not None:
                await console_ch.send(f"whitelist add {self.nickname}")

            await interaction.channel.delete()
            log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"✅ Заявка от {self.member.mention} принята модератором {interaction.user.mention}.")
        except Exception as e:
            await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.danger, custom_id="reject_button")
    async def reject(self, interaction: discord.Interaction, button: Button):
        if not any(role.name == STAFF_ROLE_NAME for role in interaction.user.roles):
            await interaction.response.send_message("❌ У вас нет прав для обработки заявок.", ephemeral=True)
            return
        try:
            await self.member.send("❌ Ваша заявка была отклонена.")
        except:
            pass
        await interaction.channel.delete()
        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"❌ Заявка от {self.member.mention} была отклонена модератором {interaction.user.mention}.")

class ApplicationButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Подать заявку", style=discord.ButtonStyle.primary, custom_id="apply_button")
    async def apply(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ApplicationModal())

@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")
    bot.add_view(TicketActionView())
    bot.add_view(ApplicationButtonView())
    channel = bot.get_channel(APPLICATION_CHANNEL_ID)

    async for msg in channel.history(limit=50):
        if msg.author == bot.user and msg.components:
            return

    await channel.send(
        "**Заявка на сервер**\n"
        "SUSPopukay — приватный политический Minecraft сервер с крутыми модами на оружие и технику.\n\n"
        "Чтобы попасть на сервер, нажмите кнопку ниже:\n\n"
        "Заявки рассматриваются до 24 часов. Удачи!",
        view=ApplicationButtonView()
    )

async def main():
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
