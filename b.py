import os

import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import logging
import asyncio
import sqlite3
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Конфигурация бота
BOT_TOKEN = os.getenv('BOT_TOKEN') # Замените на токен вашего бота
SETTINGS_CHANNEL_ID = os.getenv('SETTINGS_CHANNEL_ID')
ROLE_ID = os.getenv('ROLE_ID')

# Названия кнопок и их описания
BUTTONS = {
    "add_slot": {"emoji": "➕", "description": "Добавить 1 слот в вашу комнату"},
    "remove_slot": {"emoji": "➖", "description": "Убрать 1 слот с вашей комнаты"},
    "lock_channel": {"emoji": "🔒", "description": "Разрешить/Запретить вход пользователям в вашу комнату"},
    "toggle_voice": {"emoji": "🔊", "description": "Забрать/Выдать возможность говорить в вашей комнате"},
    "kick_user": {"emoji": "👢", "description": "Исключить пользователя из вашей комнаты"},
    "change_bitrate": {"emoji": "📶", "description": "Изменить битрейт вашей комнаты"},
    "set_slots": {"emoji": "#️⃣", "description": "Установить количество слотов в комнате"},
    "transfer_ownership": {"emoji": "👑", "description": "Передать право владения комнатой"},
    "rename_channel": {"emoji": "✏️", "description": "Сменить название вашей комнаты"},
    "manage_permissions": {"emoji": "🛂", "description": "Выдать/Забрать доступ пользователю в вашу комнату"}
}

# Константы для создания каналов
CREATE_CHANNEL_ID = 1355632485567823872
AFK_CHANNEL_ID = 1303396230214451231
VOICE_CHANNELS_CATEGORY_ID = 1301639945647292486

# Разрешенные битрейты
ALLOWED_BITRATES = [64000, 96000, 128000]

# --- Database setup ---
conn = None
cursor = None

def connect_db():
    global conn, cursor
    conn = sqlite3.connect("channels.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels (
        channel_id INTEGER PRIMARY KEY,
        owner_id INTEGER NOT NULL
    )''')
    conn.commit()

def set_channel_owner(channel_id: int, owner_id: int):
    cursor.execute("INSERT OR REPLACE INTO channels (channel_id, owner_id) VALUES (?, ?)", (channel_id, owner_id))
    conn.commit()

def get_channel_owner(channel_id: int):
    cursor.execute("SELECT owner_id FROM channels WHERE channel_id = ?", (channel_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def transfer_channel_ownership(channel_id: int, new_owner_id: int):
    if get_channel_owner(channel_id) is not None:
        cursor.execute("UPDATE channels SET owner_id = ? WHERE channel_id = ?", (new_owner_id, channel_id))
        conn.commit()

def close_db():
    global conn
    if conn:
        conn.close()


# --- Discord Bot ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)


class ChannelSettingsView(View):
    def __init__(self):
        super().__init__(timeout=None)
        for custom_id, button in BUTTONS.items():
            self.add_item(Button(label="", emoji=button["emoji"], custom_id=custom_id))


# --- Modals ---
class BaseModal(Modal):
    def __init__(self, voice_channel: discord.VoiceChannel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.voice_channel = voice_channel

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logging.error(f"Modal error: {error}", exc_info=True)
        await interaction.response.send_message("Произошла ошибка. Попробуйте позже.", ephemeral=True)


class RenameChannelModal(BaseModal):
    def __init__(self, voice_channel: discord.VoiceChannel):
        super().__init__(voice_channel, title="Переименовать канал")
        self.new_name_input = TextInput(label="Новое название канала", placeholder="Введите новое название",
                                        required=True, default=voice_channel.name)
        self.add_item(self.new_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.new_name_input.value.strip()

        if not (1 <= len(new_name) <= 100):
            await interaction.response.send_message("Название должно быть от 1 до 100 символов.", ephemeral=True)
            return

        try:
            await self.voice_channel.edit(name=new_name)
            await interaction.response.send_message(f"Название канала изменено на **{new_name}**.", ephemeral=True)
            logging.info(f"Название канала успешно изменено на {new_name}")
        except discord.Forbidden:
            await interaction.response.send_message("У меня нет прав на изменение названия.", ephemeral=True)
            logging.error("Нет прав на изменение названия")
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Ошибка при изменении названия: {e}", ephemeral=True)
            logging.error(f"Ошибка при изменении названия: {e}")


class ChangeBitrateModal(BaseModal):
    def __init__(self, voice_channel: discord.VoiceChannel):
        super().__init__(voice_channel, title="Изменить битрейт канала")
        bitrate_options = "\n".join([f"{bitrate // 1000} kbps" for bitrate in ALLOWED_BITRATES])
        self.new_bitrate_input = TextInput(label="Новый битрейт (kbps)", placeholder=f"Доступные: {bitrate_options}",
                                           required=True)
        self.add_item(self.new_bitrate_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_bitrate_kbps = int(self.new_bitrate_input.value)
            new_bitrate = new_bitrate_kbps * 1000

            if new_bitrate not in ALLOWED_BITRATES:
                await interaction.response.send_message(f"Неверный битрейт. Доступные: "
                                                        f"{', '.join([str(b // 1000) for b in ALLOWED_BITRATES])} kbps",
                                                        ephemeral=True)
                return

            await self.voice_channel.edit(bitrate=new_bitrate)
            await interaction.response.send_message(f"Битрейт канала изменен на {new_bitrate_kbps} kbps.",
                                                    ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Пожалуйста, введите числовое значение для битрейта.",
                                                    ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("У меня нет прав на изменение битрейта канала.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Ошибка при изменении битрейта: {e}", ephemeral=True)


class SetSlotsModal(BaseModal):
    def __init__(self, voice_channel: discord.VoiceChannel):
        super().__init__(voice_channel, title="Установить количество слотов")
        self.new_slots_input = TextInput(label="Новое количество слотов", placeholder="Введите количество слотов",
                                         required=True)
        self.add_item(self.new_slots_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_slots = int(self.new_slots_input.value)
            if not (0 <= new_slots <= 99):
                await interaction.response.send_message("Количество слотов должно быть между 0 и 99.", ephemeral=True)
                return

            await self.voice_channel.edit(user_limit=new_slots)
            await interaction.response.send_message(f"Количество слотов установлено на {new_slots}.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Пожалуйста, введите числовое значение для количества слотов.",
                                                    ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("У меня нет прав на изменение количества слотов в канале.",
                                                    ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Ошибка при изменении количества слотов: {e}", ephemeral=True)


class TransferOwnershipModal(BaseModal):
    def __init__(self, voice_channel: discord.VoiceChannel):
        super().__init__(voice_channel, title="Передать право владения")
        self.user_input = TextInput(label="ID или @пользователь", placeholder="Введите ID или @упоминание",
                                    required=True)
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Получаем ID нового владельца
            new_owner_id = int(self.user_input.value.strip("<@!>"))
            new_owner = await interaction.guild.fetch_member(new_owner_id)
        except Exception:
            await interaction.response.send_message("Неверный формат ID пользователя.", ephemeral=True)
            return

        # Проверка владельца канала
        current_owner_id = get_channel_owner(self.voice_channel.id)
        if current_owner_id is None:
            await interaction.response.send_message("Ошибка: канал не зарегистрирован в базе данных.", ephemeral=True)
            return

        if current_owner_id != interaction.user.id:
            await interaction.response.send_message("Вы не владелец этого канала.", ephemeral=True)
            return

        # Обновляем владельца в базе данных
        transfer_channel_ownership(self.voice_channel.id, new_owner_id)

        # Назначаем новые права новому владельцу
        perms = discord.PermissionOverwrite(manage_channels=True)
        await self.voice_channel.set_permissions(new_owner, overwrite=perms)

        # Убираем старые права у предыдущего владельца
        old_owner = await interaction.guild.fetch_member(current_owner_id)
        await self.voice_channel.set_permissions(old_owner, overwrite=None)

        await interaction.response.send_message(f"Владение каналом передано {new_owner.mention}.", ephemeral=True)
        logging.info(f"Владение каналом {self.voice_channel.id} передано {new_owner_id}")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logging.error(f"TransferOwnershipModal error: {error}", exc_info=True)
        await interaction.response.send_message("Произошла ошибка при передаче владения каналом.", ephemeral=True)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    connect_db()
    bot.add_view(ChannelSettingsView())
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

@bot.event
async def on_disconnect():
    close_db()

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data["custom_id"]
        await handle_button_click(interaction, custom_id)

async def handle_button_click(interaction: discord.Interaction, custom_id: str):
    user = interaction.user
    voice_channel = user.voice.channel if user.voice else None

    if not voice_channel:
        await interaction.response.send_message("Вы не находитесь в голосовом канале.", ephemeral=True)
        return

    channel_owner_id = get_channel_owner(voice_channel.id)
    if channel_owner_id is None:
        await interaction.response.send_message("Канал не зарегистрирован. Пожалуйста, создайте канал заново.",
                                                ephemeral=True)
        return

    if channel_owner_id != user.id:
        await interaction.response.send_message("Вы не владелец этого канала.", ephemeral=True)
        return

    modals = {
        "rename_channel": RenameChannelModal,
        "change_bitrate": ChangeBitrateModal,
        "set_slots": SetSlotsModal,
        "transfer_ownership": TransferOwnershipModal
    }

    if custom_id in modals:
        modal_class = modals[custom_id]
        modal = modal_class(voice_channel)
        await interaction.response.send_modal(modal)
        return

    if custom_id == "add_slot":
        new_limit = min(voice_channel.user_limit + 1, 99)
        await voice_channel.edit(user_limit=new_limit)
        await interaction.response.send_message(f"Добавлен 1 слот. Теперь слотов: {new_limit}", ephemeral=True)
        return

    elif custom_id == "remove_slot":
        new_limit = max(voice_channel.user_limit - 1, 0)
        await voice_channel.edit(user_limit=new_limit)
        await interaction.response.send_message(f"Убран 1 слот. Теперь слотов: {new_limit}", ephemeral=True)
        return

    elif custom_id == "lock_channel":
        perms = voice_channel.overwrites_for(interaction.guild.default_role)
        perms.connect = not perms.connect if perms.connect is not None else False
        await voice_channel.set_permissions(interaction.guild.default_role, overwrite=perms)
        status = "закрыт" if not perms.connect else "открыт"
        await interaction.response.send_message(f"Канал теперь {status} для всех пользователей.", ephemeral=True)
        return

    elif custom_id in ["toggle_voice", "manage_permissions"]:
        await handle_user_permissions(interaction, voice_channel, custom_id)

    else:
        await interaction.response.send_message("Неизвестная команда.", ephemeral=True)


async def handle_user_permissions(interaction: discord.Interaction, voice_channel: discord.VoiceChannel,
                                  custom_id: str):
    user = interaction.user

    await interaction.response.send_message("Укажите ID или упомяните пользователя для выполнения действия.",
                                            ephemeral=True)

    def check(msg):
        return msg.author == user and msg.channel == interaction.channel

    try:
        msg = await bot.wait_for("message", check=check, timeout=60.0)
        try:
            await msg.delete()
        except discord.NotFound:
            logging.warning("Сообщение не найдено или уже удалено.")

        if msg.mentions:
            mentioned_user = msg.mentions[0]
        else:
            try:
                mentioned_user = await interaction.guild.fetch_member(int(msg.content))
            except ValueError:
                await interaction.followup.send("Неверный ID пользователя.", ephemeral=True)
                return

        if not mentioned_user:
            await interaction.followup.send("Не удалось найти указанного пользователя.", ephemeral=True)
            return

        if custom_id == "toggle_voice":
            if mentioned_user.voice is None or mentioned_user.voice.channel != voice_channel:
                await interaction.followup.send(f"{mentioned_user.mention} не в этом голосовом канале.",
                                                ephemeral=True)
                return

            if mentioned_user.voice.mute:
                await mentioned_user.edit(mute=False)
                await interaction.followup.send(f"Серверный мут для {mentioned_user.mention} снят.", ephemeral=True)
            else:
                await mentioned_user.edit(mute=True)
                await interaction.followup.send(f"Серверный мут для {mentioned_user.mention} установлен.",
                                                ephemeral=True)

        elif custom_id == "manage_permissions":
            overwrites = voice_channel.overwrites_for(mentioned_user)
            connect_status = overwrites.connect if overwrites.connect is not None else True
            overwrites.connect = not connect_status
            await voice_channel.set_permissions(mentioned_user, overwrite=overwrites)
            status = "разрешен" if not overwrites.connect else "запрещен"
            await interaction.followup.send(f"Вход для {mentioned_user.mention} теперь {status}.", ephemeral=True)

    except TimeoutError:
        await interaction.followup.send("Время ожидания истекло. Попробуйте снова.", ephemeral=True)
    except Exception as e:
        logging.error(f"Error in handle_user_permissions: {e}", exc_info=True)
        await interaction.followup.send("Произошла ошибка. Попробуйте позже.", ephemeral=True)


@bot.event
async def on_voice_state_update(member, before, after):
    # Проверяем права на управление каналами у бота
    if not member.guild.me.guild_permissions.manage_channels:
        logging.warning("У бота нет прав на управление каналами.")
        return

    # Проверка, если пользователь заходит в канал "Создать канал"
    if after.channel and after.channel.id == CREATE_CHANNEL_ID:
        logging.info(f"{member.name} подключился к каналу 'Создать канал'")
        category = after.channel.category
        if category is not None:
            # Проверяем, существует ли уже канал с таким именем
            existing_channel = discord.utils.get(category.voice_channels, name=f"{member.display_name}")
            if existing_channel is None:
                new_channel = await category.create_voice_channel(name=f"{member.display_name}")
                await member.move_to(new_channel)
                logging.info(f"Создан новый канал: {new_channel.name} для {member.name}")
                set_channel_owner(new_channel.id, member.id)
                logging.info(f"Канал {new_channel.name} зарегистрирован в базе данных.")
            else:
                await member.move_to(existing_channel)  # Перемещаем пользователя в существующий канал
                logging.info(f"Перемещен в существующий канал: {existing_channel.name} для {member.name}")

    # Удаляем пустые каналы, кроме канала "Создать канал"
    if (before.channel and len(before.channel.members) == 0 and
        before.channel.id not in {CREATE_CHANNEL_ID, AFK_CHANNEL_ID}):
        await check_and_delete_channel(before.channel)

    # Проверка, если пользователь покидает голосовой канал
    elif after.channel is None and before.channel is not None:
        await check_and_delete_channel(before.channel)

    # Проверка, если пользователь перемещается между каналами
    elif after.channel is not None and before.channel is not None and before.channel != after.channel:
        await check_and_delete_channel(before.channel)

async def check_and_delete_channel(channel):
    category = discord.utils.get(channel.guild.categories, id=VOICE_CHANNELS_CATEGORY_ID)
    if (channel.category == category and len(channel.members) == 0
        and channel.id not in {CREATE_CHANNEL_ID, AFK_CHANNEL_ID}):
        await delete_channel(channel)

async def delete_channel(channel):
    # Проверка, что канал не является AFK или каналом "Создать канал"
    if channel.id not in {AFK_CHANNEL_ID, CREATE_CHANNEL_ID}:
        try:
            await channel.delete()
            logging.info(f"Удален канал: {channel.name}")
            cursor.execute("DELETE FROM channels WHERE channel_id = ?", (channel.id,))
            conn.commit()
            logging.info(f"Запись канала {channel.id} удалена из базы данных.")
        except discord.Forbidden:
            logging.warning(f"Не удалось удалить канал: {channel.name}. Недостаточно прав.")
        except discord.HTTPException as e:
            logging.error(f"Ошибка при удалении канала: {channel.name}. Ошибка: {e}")
    else:
        logging.info(f"Канал {channel.name} не будет удален.")


@bot.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, id=ROLE_ID)

    if role:
        try:
            await member.add_roles(role)
            logging.info(f"Роль {role.name} выдана пользователю {member.name}")
        except discord.Forbidden:
            logging.warning(f"Не удалось выдать роль {role.name} пользователю {member.name}. Недостаточно прав.")
        except discord.HTTPException as e:
            logging.error(f"Ошибка при выдаче роли {role.name}: {e}")
    else:
        logging.error(f"Роль с ID {ROLE_ID} не найдена на сервере.")

# Запуск бота
bot.run(BOT_TOKEN)
