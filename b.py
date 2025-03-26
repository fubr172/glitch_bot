import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import logging
import asyncio

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Конфигурация бота
BOT_TOKEN = "MTMwMTkyMjM4OTc4MDg2MTAyOQ.GPJnWW.6ew5eltuNa9sC07xeAE0BvN9YFn0DSec5M5s2Q"  # Замените на токен вашего бота
SETTINGS_CHANNEL_ID = 1345732564026916984

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
CREATE_CHANNEL_NAME = "Создать канал"
AFK_CHANNEL_NAME = "AFK"
VOICE_CHANNELS_CATEGORY_NAME = "Голосовые каналы"

# Разрешенные битрейты
ALLOWED_BITRATES = [64000, 96000, 128000, 256000, 384000]

class ChannelSettingsView(View):
    def __init__(self):
        super().__init__(timeout=None)
        for custom_id, button in BUTTONS.items():
            self.add_item(Button(label="", emoji=button["emoji"], custom_id=custom_id))

# Настройка намерений
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)



class RenameChannelModal(Modal):
    def __init__(self, voice_channel: discord.VoiceChannel):  # Ensure correct typehint
        super().__init__(title="Переименовать канал")
        self.voice_channel = voice_channel
        self.new_name_input = TextInput(label="Новое название канала", placeholder="Введите новое название",
                                        required=True, default=voice_channel.name)
        self.add_item(self.new_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.new_name_input.value.strip()
        logging.info(f"Попытка изменить название канала на: {new_name}")

        # Проверка длины названия
        if not (1 <= len(new_name) <= 100):
            await interaction.response.send_message("Название должно быть от 1 до 100 символов.", ephemeral=True)
            return

        try:
            # Проверка прав на изменение канала. Use voice_channel, not interaction.channel.
            permissions = self.voice_channel.permissions_for(interaction.guild.me)
            if not permissions.manage_channels:
                await interaction.response.send_message("У меня нет прав на изменение названия канала.", ephemeral=True)
                return

            # Пытаемся переименовать канал
            await self.voice_channel.edit(name=new_name)
            await interaction.response.send_message(f"Название канала изменено на **{new_name}**.", ephemeral=True)
            logging.info(f"Название канала успешно изменено на {new_name}")
        except discord.Forbidden:
            await interaction.response.send_message("У меня нет прав на изменение названия.", ephemeral=True)
            logging.error("Нет прав на изменение названия")
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Ошибка при изменении названия: {e}", ephemeral=True)
            logging.error(f"Ошибка при изменении названия: {e}")


class ChangeBitrateModal(Modal):
    def __init__(self, voice_channel):
        super().__init__(title="Изменить битрейт канала")
        self.voice_channel = voice_channel
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
            await interaction.response.send_message(f"Битрейт канала изменен на {new_bitrate_kbps} kbps.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Пожалуйста, введите числовое значение для битрейта.",
                                                    ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("У меня нет прав на изменение битрейта канала.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Ошибка при изменении битрейта: {e}", ephemeral=True)


class SetSlotsModal(Modal):
    def __init__(self, voice_channel):
        super().__init__(title="Установить количество слотов")
        self.voice_channel = voice_channel
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


class TransferOwnershipModal(Modal):
    def __init__(self, voice_channel):
        super().__init__(title="Передать право владения")
        self.voice_channel = voice_channel
        self.user_input = TextInput(label="Укажите ID или упомяните пользователя", placeholder="Введите ID или @упоминание пользователя", required=True)
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_input = self.user_input.value
        mentioned_user = None

        try:
            mentioned_user = await interaction.guild.fetch_member(int(user_input))
        except ValueError:
            mentioned_user = interaction.guild.get_member(int(user_input[2:-1]))  # Убираем <@ и >

        if not mentioned_user:
            await interaction.response.send_message("Не удалось найти указанного пользователя.", ephemeral=True)
            return

        perms = discord.PermissionOverwrite(manage_channels=True)
        await self.voice_channel.set_permissions(mentioned_user, overwrite=perms)
        await interaction.response.send_message(f"Владение каналом передано {mentioned_user.mention}.", ephemeral=True)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data["custom_id"]
        if custom_id in BUTTONS:
            await handle_button_click(interaction, custom_id)

async def handle_button_click(interaction: discord.Interaction, custom_id: str):
    user = interaction.user
    voice_channel = user.voice.channel if user.voice else None

    if not voice_channel:
        msg = await interaction.response.send_message("Вы не находитесь в голосовом канале.", ephemeral=True)
        await remove_message_after_delay(msg, 10)
        return

    if not voice_channel.permissions_for(interaction.guild.me).manage_channels:
        await voice_channel.set_permissions(interaction.guild.me, manage_channels=True, connect=True, speak=True)

    if not voice_channel.permissions_for(user).manage_channels:
        msg = await interaction.response.send_message("Вы не владелец этого канала.", ephemeral=True)
        await remove_message_after_delay(msg, 10)
        return

    modals = {
        "rename_channel": RenameChannelModal,
        "change_bitrate": ChangeBitrateModal,
        "set_slots": SetSlotsModal,
    }

    if custom_id in modals:
        modal = modals[custom_id](voice_channel)
        await interaction.response.send_modal(modal)
        return

    if custom_id == "add_slot":
        new_limit = min(voice_channel.user_limit + 1, 99)
        await voice_channel.edit(user_limit=new_limit)
        msg = await interaction.response.send_message(f"Добавлен 1 слот. Теперь слотов: {new_limit}", ephemeral=True)
        await remove_message_after_delay(msg, 10)
        return

    elif custom_id == "remove_slot":
        new_limit = max(voice_channel.user_limit - 1, 0)
        await voice_channel.edit(user_limit=new_limit)
        msg = await interaction.response.send_message(f"Убран 1 слот. Теперь слотов: {new_limit}", ephemeral=True)
        await remove_message_after_delay(msg, 10)
        return

    elif custom_id == "lock_channel":
        perms = voice_channel.overwrites_for(interaction.guild.default_role)
        perms.connect = not perms.connect if perms.connect is not None else False
        await voice_channel.set_permissions(interaction.guild.default_role, overwrite=perms)
        status = "закрыт" if not perms.connect else "открыт"
        msg = await interaction.response.send_message(f"Канал теперь {status} для всех пользователей.", ephemeral=True)
        await remove_message_after_delay(msg, 10)
        return

    if custom_id == "toggle_voice":
        mentioned_user = None
        msg = await interaction.response.send_message("Укажите ID или упомяните пользователя для выполнения действия.",
                                                ephemeral=True)
        await remove_message_after_delay(msg, 10)

        def check(msg):
            return msg.author == user and msg.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", check=check, timeout=60.0)
            await msg.delete()

            if msg.mentions:
                mentioned_user = msg.mentions[0]
            else:
                try:
                    mentioned_user = await interaction.guild.fetch_member(int(msg.content))
                except ValueError:
                    msg = await interaction.followup.send("Неверный ID пользователя.", ephemeral=True)
                    await remove_message_after_delay(msg, 10)
                    return

            if not mentioned_user:
                msg = await interaction.followup.send("Не удалось найти указанного пользователя.", ephemeral=True)
                await remove_message_after_delay(msg, 10)
                return

            if mentioned_user.voice.mute:
                await mentioned_user.edit(mute=False)
                msg = await interaction.followup.send(f"Серверный мут для {mentioned_user.mention} снят.", ephemeral=True)
                await remove_message_after_delay(msg, 10)
                return
            else:
                await mentioned_user.edit(mute=True)
                msg = await interaction.followup.send(f"Серверный мут для {mentioned_user.mention} установлен.",
                                                    ephemeral=True)
                await remove_message_after_delay(msg, 10)
                return

        except discord.NotFound:
            msg = await interaction.followup.send("Сообщение не найдено или уже удалено.", ephemeral=True)
            await remove_message_after_delay(msg, 10)
        except TimeoutError:
            msg = await interaction.followup.send("Время ожидания истекло. Попробуйте снова.", ephemeral=True)
            await remove_message_after_delay(msg, 10)

    elif custom_id == "manage_permissions":
        mentioned_user = None
        msg = await interaction.response.send_message("Укажите ID или упомяните пользователя для выполнения действия.",
                                                ephemeral=True)
        await remove_message_after_delay(msg, 10)

        def check(msg):
            return msg.author == user and msg.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", check=check, timeout=60.0)
            await msg.delete()

            if msg.mentions:
                mentioned_user = msg.mentions[0]
            else:
                try:
                    mentioned_user = await interaction.guild.fetch_member(int(msg.content))
                except ValueError:
                    msg = await interaction.followup.send("Неверный ID пользователя.", ephemeral=True)
                    await remove_message_after_delay(msg, 10)
                    return

            if not mentioned_user:
                msg = await interaction.followup.send("Не удалось найти указанного пользователя.", ephemeral=True)
                await remove_message_after_delay(msg, 10)
                return

            overwrites = voice_channel.overwrites_for(mentioned_user)
            overwrites.connect = not overwrites.connect if overwrites.connect is not None else True
            await voice_channel.set_permissions(mentioned_user, overwrite=overwrites)
            status = 'разрешён' if overwrites.connect else 'запрещён'
            msg = await interaction.followup.send(f"Доступ для {mentioned_user.mention} теперь {status}.", ephemeral=True)
            await remove_message_after_delay(msg, 10)
            return

        except discord.NotFound:
            msg = await interaction.followup.send("Сообщение не найдено или уже удалено.", ephemeral=True)
            await remove_message_after_delay(msg, 10)
            return

        except TimeoutError:
            msg = await interaction.followup.send("Время ожидания истекло. Попробуйте снова.", ephemeral=True)
            await remove_message_after_delay(msg, 10)
            return


async def remove_message_after_delay(msg, delay=5):
    """Удаляет сообщение через заданное количество секунд, если оно не соответствует списку разрешенных."""
    await asyncio.sleep(delay)

    allowed_phrases = [
        "Управление приватными каналами",
        "➕ - Добавить 1 слот в вашу комнату",
        "➖ - Убрать 1 слот с вашей комнаты",
        "🔒 - Разрешить/Запретить вход пользователям в вашу комнату",
        "🔊 - Забрать/Выдать возможность говорить в вашей комнате",
        "👢 - Исключить пользователя из вашей комнаты",
        "📶 - Изменить битрейт вашей комнаты",
        "#️⃣ - Установить количество слотов в комнате",
        "👑 - Передать право владения комнатой",
        "✏️ - Сменить название вашей комнаты",
        "🛂 - Выдать/Забрать доступ пользователю в вашу комнату"
    ]

    try:
        # Проверяем, что это сообщение и оно не соответствует разрешенным фразам
        if isinstance(msg, discord.Message):
            # Если сообщение не содержит фразы из allowed_phrases, оно будет удалено
            if not any(phrase in msg.content for phrase in allowed_phrases):
                await msg.delete()  # Удаляем сообщение
                logging.info(f"Сообщение от {msg.author} удалено: {msg.id} - Не разрешенное содержание.")
            else:
                logging.info(f"Сообщение не удалено: содержит разрешенную фразу или эмодзи: {msg.id}")
        else:
            logging.info(f"Сообщение не удалено: оно не является обычным или эмбед-сообщением: {msg.id}")
    except discord.NotFound:
        logging.warning(f"Сообщение не найдено для удаления: {msg.id}. Возможно, оно уже удалено.")
    except discord.Forbidden:
        logging.warning(f"У бота нет прав на удаление сообщения: {msg.id}. Проверьте права бота.")
    except discord.HTTPException as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")


@bot.event
async def on_voice_state_update(member, before, after):
    # Проверяем права на управление каналами у бота
    if not member.guild.me.guild_permissions.manage_channels:
        logging.warning("У бота нет прав на управление каналами.")
        return


    # Пользователь зашел в "Создать канал"
    if after.channel and after.channel.name == CREATE_CHANNEL_NAME:
        logging.info(f"{member.name} подключился к каналу 'Создать канал'")
        category = after.channel.category

        if category is not None:
            # Проверяем, есть ли уже канал для пользователя
            existing_channel = discord.utils.get(category.voice_channels, name=f"{member.display_name}")
            if existing_channel is None:
                new_channel = await category.create_voice_channel(name=f"{member.display_name}")

                # Устанавливаем права владельца (разрешаем только создателю управлять каналом)
                overwrites = {
                    member: discord.PermissionOverwrite(manage_channels=True, connect=True, speak=True),
                    member.guild.me: discord.PermissionOverwrite(manage_channels=True, connect=True, speak=True)  # Права бота
                }
                await new_channel.edit(overwrites=overwrites)

                await member.move_to(new_channel)
                logging.info(f"Создан новый канал: {new_channel.name} для {member.name}")
            else:
                await member.move_to(existing_channel)
                logging.info(f"Перемещен в существующий канал: {existing_channel.name} для {member.name}")

    # Проверка, если пользователь покинул канал и он пустой
    if before.channel and before.channel.name not in {CREATE_CHANNEL_NAME, AFK_CHANNEL_NAME}:
        await check_and_delete_channel(before.channel)

    if after.channel:
        # Если пользователь вошел в канал и был замучен, снимаем мут
        if before.channel != after.channel and before.channel is not None:
            perms = before.channel.overwrites_for(member)
            if perms.speak is False:
                perms.speak = True
                await before.channel.set_permissions(member, overwrite=perms)
                await member.send("Ваш мут был снят, так как вы покинули канал и вернулись.")
                logging.info(f"Мут снят с {member.name} в канале {before.channel.name}.")
        # Проверяем, если пользователь зашел в канал, и он был замучен
        if after.channel and before.channel != after.channel:
            perms = after.channel.overwrites_for(member)
            if perms.speak is False:
                perms.speak = True
                await after.channel.set_permissions(member, overwrite=perms)
                await member.send("Ваш мут был снят, так как вы вернулись в канал.")
                logging.info(f"Мут снят с {member.name} в канале {after.channel.name}.")

async def check_and_delete_channel(channel):
    category = discord.utils.get(channel.guild.categories, name=VOICE_CHANNELS_CATEGORY_NAME)
    if (channel.category == category and len(channel.members) == 0
        and channel.name not in {CREATE_CHANNEL_NAME, AFK_CHANNEL_NAME}):
        await delete_channel(channel)


async def delete_channel(channel):
    # Проверка, что канал не является AFK или каналом "Создать канал"
    if channel.name not in {AFK_CHANNEL_NAME, CREATE_CHANNEL_NAME}:
        try:
            await channel.delete()
            logging.info(f"Удален канал: {channel.name}")
        except discord.Forbidden:
            logging.warning(f"Не удалось удалить канал: {channel.name}. Недостаточно прав.")
        except discord.HTTPException as e:
            logging.error(f"Ошибка при удалении канала: {channel.name}. Ошибка: {e}")
    else:
        logging.info(f"Канал {channel.name} не будет удален.")


@bot.command()
async def clear_channel(ctx):
    """Очищает все ненужные сообщения в канале, кроме сообщений с кнопками и настройками."""
    if ctx.channel.id != SETTINGS_CHANNEL_ID:
        await ctx.send("Эта команда доступна только в канале настроек.")
        return

    # Проверяем права на удаление сообщений
    if not ctx.channel.permissions_for(ctx.guild.me).manage_messages:
        await ctx.send("У меня нет прав на удаление сообщений.")
        return

    # Удаляем все ненужные сообщения в канале
    async for msg in ctx.channel.history(limit=100):
        if not msg.embeds and not msg.components and msg.author != bot.user:
            try:
                await msg.delete()
                logging.info(f"Удалено сообщение от {msg.author}: {msg.content}")
            except discord.Forbidden:
                logging.warning(f"Нет прав на удаление сообщения: {msg.id}")
            except discord.NotFound:
                logging.warning("Сообщение не найдено для удаления.")
            except discord.HTTPException as e:
                logging.error(f"Ошибка при удалении сообщения: {e}")

    await ctx.send("Канал очищен от ненужных сообщений.")

@bot.event
async def on_message(message):
    """Удаляет сообщения с ephemeral=True."""
    if message.channel.id == SETTINGS_CHANNEL_ID:
        if not message.embeds and not message.components:
            try:
                await message.delete()
                logging.info(f"Сообщение от {message.author} удалено.")
            except discord.Forbidden:
                logging.warning("Нет прав на удаление сообщения.")
            except discord.NotFound:
                logging.warning("Сообщение уже удалено.")
            except discord.HTTPException as e:
                logging.error(f"Ошибка при удалении сообщения: {e}")
    else:
        await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")
    channel = bot.get_channel(SETTINGS_CHANNEL_ID)
    if channel:
        embed = discord.Embed(title="Управление приватными каналами")
        embed.description = "\n".join([f"{button['emoji']} - {button['description']}" for button in BUTTONS.values()])
        view = ChannelSettingsView()
        message = await channel.send(embed=embed, view=view)
        bot.add_view(view)

bot.run(BOT_TOKEN)