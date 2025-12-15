import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from game import GameManager, Game

logging.basicConfig(level=Config.LOG_LEVEL)
logger = logging.getLogger(__name__)
bot = Bot(token=Config.BOT_TOKEN)
dp = Dispatcher()
game_manager = GameManager()

import re
import asyncio

@dp.message()
async def admin_gift_handler(message: types.Message):
    if message.from_user.id != Config.ADMIN_ID:
        return

    text = message.text.strip()
    pattern = r'^@(\w+)\s+gifts\s+(\d+)\s+(\d+)$'
    match = re.match(pattern, text)
    if not match:
        await message.reply("Неверный формат команды. Используйте: @username gifts (кол-во) (сумма)")
        return

    username = match.group(1)
    count = int(match.group(2))
    amount = int(match.group(3))
    user_id = None
    async def find_user_id_by_username(username):
        import sqlite3
        conn = sqlite3.connect('games.db')
        cursor = conn.execute('SELECT user_id FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0]
        return None

    user_id = await asyncio.get_event_loop().run_in_executor(None, find_user_id_by_username, username)

    if not user_id:
        await message.reply(f"Пользователь @{username} не найден.")
        return

    total_gift = count * amount
    current_balance = game_manager.db.get_user_balance(user_id)
    new_balance = current_balance + total_gift
    game_manager.db.save_user_balance(user_id, new_balance)
    await message.reply(f"Подарок успешно выдан @{username}: {total_gift} 💰 (новый баланс: {new_balance} 💰)")

def format_game_message(game: Game) -> str:
    lines = ["===="]
    lines.append("21-sck")
    lines.append("")

    for i, player in enumerate(game.players):
        prefix = ""
        if game.status == 'betting' and i == game.current_betting_player_index:
            prefix = "> "
        elif i == game.current_player_index and game.status == 'playing':
            prefix = "> "
        elif i == game.current_player_index + 1 and game.status == 'playing':
            prefix = "^ "
        cards_str = ' '.join(str(card) for card in player.cards)
        if game.status == 'betting':
            lines.append(f"{prefix}@{player.username} — [{cards_str}] — {player.score} (Баланс: {player.balance} 💰, Ставка: {player.bet})")
        else:
            lines.append(f"{prefix}@{player.username} — [{cards_str}] — {player.score} (Ставка: {player.bet})")

    lines.append("")
    if game.status == 'playing':
        dealer_visible = str(game.dealer.cards[0]) if game.dealer.cards else "?"
        lines.append(f"Дилер — [{dealer_visible}] [?] — ??")
    elif game.status == 'betting':
        lines.append("Дилер — [?] [?] — ??")
    else:
        dealer_cards = ' '.join(str(card) for card in game.dealer.cards)
        lines.append(f"Дилер — [{dealer_cards}] — {game.dealer.score}")

    lines.append("")
    if game.status == 'betting':
        lines.append("(ставки принимаются)")
    else:
        lines.append(":3")
    lines.append("====")

    if game.status == 'finished':
        lines.insert(0, "ИГРА ЗАВЕРШЕНА!")
        winners = [p.username for p in game.players if p.status == 'win']
        if winners:
            lines.append(f"Победители: {', '.join(f'@{w}' for w in winners)}")
        else:
            lines.append(" Победитель: Дилер")

    return "\n".join(lines)

def create_join_keyboard(game: Game) -> InlineKeyboardMarkup:
    keyboard = []
    if game.status == 'waiting':
        keyboard.append([InlineKeyboardButton(text="Join", callback_data=f"join_{game.game_id}")])
        if len(game.players) >= 2:
            keyboard.append([InlineKeyboardButton(text="Start ▶", callback_data=f"start_{game.game_id}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_game_keyboard(game: Game) -> InlineKeyboardMarkup:
    keyboard = []
    if game.status == 'betting':
        current_player = game.players[game.current_betting_player_index] if game.current_betting_player_index < len(game.players) else None
        if current_player:
            bet = current_player.bet
            game_id = game.game_id
            keyboard.append([
                InlineKeyboardButton(text="x2", callback_data=f"bet_double_{game_id}"),
                InlineKeyboardButton(text="+10", callback_data=f"bet_plus10_{game_id}"),
                InlineKeyboardButton(text="Push", callback_data=f"bet_push_{game_id}"),
                InlineKeyboardButton(text="-10", callback_data=f"bet_minus10_{game_id}"),
                InlineKeyboardButton(text="//2", callback_data=f"bet_half_{game_id}"),
            ])
    elif game.status == 'playing':
        current_player = game.players[game.current_player_index] if game.current_player_index < len(game.players) else None
        if current_player and current_player.status == 'active':
            keyboard.append([
                InlineKeyboardButton(text="Hit 🔄", callback_data=f"hit_{game.game_id}"),
                InlineKeyboardButton(text="Stand ✋", callback_data=f"stand_{game.game_id}"),
                InlineKeyboardButton(text="Double 💰", callback_data=f"double_{game.game_id}")
            ])
    elif game.status == 'finished':
        keyboard.append([InlineKeyboardButton(text="Новая игра 🎮", callback_data=f"new_game_{game.game_id}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.inline_query()
async def inline_query_handler(inline_query: InlineQuery):
    query = inline_query.query.lower()
    if query == "create":
        game = game_manager.create_game(inline_query.from_user.id, 0)  
        game.add_player(inline_query.from_user.id, inline_query.from_user.username or "Unknown", game_manager.db)

        text = f"Комната \"21\" создана!\nСоздатель: @{inline_query.from_user.username}\nИгроков: {len(game.players)}/{Config.MAX_PLAYERS}\n"
        text += "================================="

        result = InlineQueryResultArticle(
            id=game.game_id,
            title="Создать игру в 21 очко",
            input_message_content=InputTextMessageContent(message_text=text),
            reply_markup=create_join_keyboard(game)
        )

        await inline_query.answer([result], cache_time=1)
    elif query == "profile":
        balance = game_manager.db.get_user_balance(inline_query.from_user.id)
        stats = game_manager.db.get_user_stats(inline_query.from_user.id)
        text = f"Ваш профиль:\nПобеды: {stats['total_wins']}\nДеньги: {balance} 💰\nМакс-ставка: {stats['max_bet']}\nМакс побед подряд: {stats['max_consecutive_wins']}"

        result = InlineQueryResultArticle(
            id="profile",
            title="Показать профиль",
            input_message_content=InputTextMessageContent(message_text=text)
        )

        await inline_query.answer([result], cache_time=1)
    elif query.startswith("gift"):
        if inline_query.from_user.id != Config.ADMIN_ID:
            await inline_query.answer([], cache_time=1)
            return

        parts = query.split()
        if len(parts) != 3:
            text = "Формат: gift limit amount"
            result = InlineQueryResultArticle(
                id="gift_help",
                title="Помощь по раздачам",
                input_message_content=InputTextMessageContent(message_text=text)
            )
            await inline_query.answer([result], cache_time=1)
            return

        _, limit_str, amount_str = parts
        try:
            limit = int(limit_str)
            amount = int(amount_str)
        except ValueError:
            text = "Лимит и сумма должны быть числами"
            result = InlineQueryResultArticle(
                id="gift_error",
                title="Ошибка",
                input_message_content=InputTextMessageContent(message_text=text)
            )
            await inline_query.answer([result], cache_time=1)
            return

        import uuid
        giveaway_id = str(uuid.uuid4())

        game_manager.db.save_giveaway(giveaway_id, inline_query.from_user.id, limit, amount, [])

        text = f"Раздача создана!\nЛимит участников: {limit}\nСумма каждому: {amount} 💰\nУчастников: 0/{limit}"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Присоединиться", callback_data=f"enter_giveaway_{giveaway_id}")]
        ])

        result = InlineQueryResultArticle(
            id=giveaway_id,
            title="Создать раздачу подарков",
            input_message_content=InputTextMessageContent(message_text=text),
            reply_markup=keyboard
        )

        await inline_query.answer([result], cache_time=1)
    else:
        await inline_query.answer([], cache_time=1)

@dp.callback_query(lambda c: c.data.startswith("new_game_"))
async def new_game_handler(callback: CallbackQuery):
    old_game_id = callback.data.split("_")[2]
    old_game = game_manager.get_game(old_game_id)
    if not old_game:
        await callback.answer("Предыдущая игра не найдена.")
        return

    new_game = game_manager.create_game(callback.from_user.id, old_game.chat_id)
    new_game.add_player(callback.from_user.id, callback.from_user.username or "Unknown", game_manager.db)
    game_manager.save_game(new_game)
    creator_player = next((p for p in new_game.players if p.user_id == new_game.creator_id), None)
    creator_username = creator_player.username if creator_player else (callback.from_user.username or "Unknown")

    text = f"Новая комната \"21\" создана!\nСоздатель: @{creator_username}\nИгроков: {len(new_game.players)}/{Config.MAX_PLAYERS}\n"
    text += "================================="

    try:
        if callback.inline_message_id:
            await bot.edit_message_text(text, inline_message_id=callback.inline_message_id, reply_markup=create_join_keyboard(new_game))
        else:
            await callback.message.edit_text(text, reply_markup=create_join_keyboard(new_game))
    except Exception as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise
    await callback.answer("Новая игра создана!")

@dp.callback_query(lambda c: c.data.startswith("join_"))
async def join_game_handler(callback: CallbackQuery):
    game_id = callback.data.split("_")[1]
    game = game_manager.get_game(game_id)
    if not game:
        await callback.answer("Игра не найдена.")
        return

    if game.chat_id == 0:
        if callback.inline_message_id:
            pass
        elif callback.message and callback.message.chat:
            game.chat_id = callback.message.chat.id
            game_manager.save_game(game)
        else:
            await callback.answer("Не удалось определить чат.")
            return

    if game.status != 'waiting':
        await callback.answer("Игра уже началась.")
        return

    success = game.add_player(callback.from_user.id, callback.from_user.username or "Unknown", game_manager.db)
    if not success:
        await callback.answer("Не удалось присоединиться...")
        return

    game_manager.save_game(game)

    text = f"Комната \"21\" создана!\nСоздатель: @{game.players[0].username}\nИгроков: {len(game.players)}/{Config.MAX_PLAYERS}\n"
    text += "================================="


    try:
        if callback.inline_message_id:
            await bot.edit_message_text(text, inline_message_id=callback.inline_message_id, reply_markup=create_join_keyboard(game))
        else:
            await callback.message.edit_text(text, reply_markup=create_join_keyboard(game))
    except Exception as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise
    await callback.answer("Вы присоединились к игре!")

@dp.callback_query(lambda c: c.data.startswith("start_"))
async def start_game_handler(callback: CallbackQuery):
    game_id = callback.data.split("_")[1]
    game = game_manager.get_game(game_id)
    if not game:
        await callback.answer("Игра не найдена.")
        return

    if callback.from_user.id != game.creator_id:
        await callback.answer("Только создатель может начать игру.")
        return

    if len(game.players) < 2:
        await callback.answer("Нужно минимум 2 игрока.")
        return

    success = game_manager.start_game(game_id)
    if not success:
        await callback.answer("Не удалось начать игру.")
        return

    text = format_game_message(game)
    try:
        if callback.inline_message_id:
            await bot.edit_message_text(text, inline_message_id=callback.inline_message_id, reply_markup=create_game_keyboard(game))
        else:
            await callback.message.edit_text(text, reply_markup=create_game_keyboard(game))
    except Exception as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise
    await callback.answer("Игра началась!")

@dp.callback_query(lambda c: c.data.startswith("hit_"))
async def hit_handler(callback: CallbackQuery):
    game_id = callback.data.split("_")[1]
    game = game_manager.get_game(game_id)
    if not game:
        await callback.answer("Игра не найдена.")
        return

    success = game.player_hit(callback.from_user.id)
    if not success:
        await callback.answer("Не ваш ход или игра не активна.")
        return

    if game.status == 'finished':
        game_manager.save_balances_after_game(game)
        game_manager.save_game(game)
        text = format_game_message(game)
        try:
            if callback.inline_message_id:
                await bot.edit_message_text(text, inline_message_id=callback.inline_message_id, reply_markup=create_game_keyboard(game))
            else:
                await callback.message.edit_text(text, reply_markup=create_game_keyboard(game))
        except Exception as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise
    else:
        game_manager.save_game(game)
        text = format_game_message(game)
        try:
            if callback.inline_message_id:
                await bot.edit_message_text(text, inline_message_id=callback.inline_message_id, reply_markup=create_game_keyboard(game))
            else:
                await callback.message.edit_text(text, reply_markup=create_game_keyboard(game))
        except Exception as e: 
            if "message is not modified" in str(e):
                pass
            else:
                raise

    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("double_"))
async def double_handler(callback: CallbackQuery):
    game_id = callback.data.split("_")[1]
    game = game_manager.get_game(game_id)
    if not game:
        await callback.answer("Игра не найдена.")
        return

    player = game._get_current_player()
    if player.user_id != callback.from_user.id:
        await callback.answer("Не ваш ход или игра не активна.")
        return

    if player.has_hit:
        await callback.answer("Нельзя удваивать ставку после взятия карты.")
        return

    new_bet = player.bet * 2
    if not player.adjust_bet(new_bet):
        await callback.answer("Недостаточно средств для удвоения ставки.")
        return

    player.add_card(game.deck.draw())
    player.status = 'stand'
    game._next_player()

    if game.status == 'finished':
        game_manager.save_balances_after_game(game)
        game_manager.save_game(game)
        text = format_game_message(game)
        try:
            if callback.inline_message_id:
                await bot.edit_message_text(text, inline_message_id=callback.inline_message_id, reply_markup=create_game_keyboard(game))
            else:
                await callback.message.edit_text(text, reply_markup=create_game_keyboard(game))
        except Exception as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise
    else:
        game_manager.save_game(game)
        text = format_game_message(game)
        try:
            if callback.inline_message_id:
                await bot.edit_message_text(text, inline_message_id=callback.inline_message_id, reply_markup=create_game_keyboard(game))
            else:
                await callback.message.edit_text(text, reply_markup=create_game_keyboard(game))
        except Exception as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise

    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("stand_"))
async def stand_handler(callback: CallbackQuery):
    game_id = callback.data.split("_")[1]
    game = game_manager.get_game(game_id)
    if not game:
        await callback.answer("Игра не найдена.")
        return

    success = game.player_stand(callback.from_user.id)
    if not success:
        await callback.answer("Не ваш ход или игра не активна.")
        return

    if game.status == 'finished':
        game_manager.save_balances_after_game(game)
        game_manager.save_game(game)
        text = format_game_message(game)
        try:
            if callback.inline_message_id:
                await bot.edit_message_text(text, inline_message_id=callback.inline_message_id, reply_markup=create_game_keyboard(game))
            else:
                await callback.message.edit_text(text, reply_markup=create_game_keyboard(game))
        except Exception as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise
    else:
        game_manager.save_game(game)
        text = format_game_message(game)
        try:
            if callback.inline_message_id:
                await bot.edit_message_text(text, inline_message_id=callback.inline_message_id, reply_markup=create_game_keyboard(game))
            else:
                await callback.message.edit_text(text, reply_markup=create_game_keyboard(game))
        except Exception as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise

    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("bet_"))
async def bet_handler(callback: CallbackQuery):
    parts = callback.data.split("_")
    action = parts[1]
    game_id = parts[2]
    game = game_manager.get_game(game_id)
    if not game:
        await callback.answer("Игра не найдена.")
        return

    if game.status != 'betting':
        await callback.answer("Ставки уже закрыты.")
        return

    current_player = game.players[game.current_betting_player_index] if game.current_betting_player_index < len(game.players) else None
    if not current_player or current_player.user_id != callback.from_user.id:
        await callback.answer("Не ваша очередь делать ставку.")
        return

    bet_changed = False
    if action == "double":
        new_bet = current_player.bet * 2
        if current_player.adjust_bet(new_bet):
            bet_changed = True
        else:
            await callback.answer("Недостаточно средств.")
            return
    elif action == "plus10":
        new_bet = current_player.bet + 10
        if current_player.adjust_bet(new_bet):
            bet_changed = True
        else:
            await callback.answer("Недостаточно средств.")
            return
    elif action == "push":
        game.current_betting_player_index += 1
        if game.current_betting_player_index >= len(game.players):
            game._deal_cards()
        bet_changed = True
    elif action == "minus10":
        new_bet = max(10, current_player.bet - 10)
        current_player.adjust_bet(new_bet)
        bet_changed = True
    elif action == "half":
        new_bet = max(10, current_player.bet // 2)
        current_player.adjust_bet(new_bet)
        bet_changed = True

    if bet_changed:
        game_manager.save_game(game)
        text = format_game_message(game)
        try:
            if callback.inline_message_id:
                await bot.edit_message_text(text, inline_message_id=callback.inline_message_id, reply_markup=create_game_keyboard(game))
            else:
                await callback.message.edit_text(text, reply_markup=create_game_keyboard(game))
        except Exception as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise

    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("enter_giveaway_"))
async def join_giveaway_handler(callback: CallbackQuery):
    giveaway_id = callback.data.split("_")[2]
    giveaway = game_manager.db.load_giveaway(giveaway_id)
    if not giveaway:
        await callback.answer("Раздача не найдена.")
        return

    if giveaway['status'] != 'active':
        await callback.answer("Раздача уже завершена.")
        return

    if callback.from_user.id in giveaway['joined_users']:
        await callback.answer("Вы уже присоединились.")
        return

    joined_users = giveaway['joined_users'] + [callback.from_user.id]
    game_manager.db.save_giveaway(giveaway_id, giveaway['creator_id'], giveaway['limit'], giveaway['amount'], joined_users)
    if len(joined_users) >= giveaway['limit']:
        for user_id in joined_users:
            current_balance = game_manager.db.get_user_balance(user_id)
            new_balance = current_balance + giveaway['amount']
            game_manager.db.save_user_balance(user_id, new_balance)

        game_manager.db.update_giveaway_status(giveaway_id, 'finished')

        text = f"Раздача завершена!\nЛимит участников: {giveaway['limit']}\nСумма каждому: {giveaway['amount']} 💰\nУчастников: {len(joined_users)}/{giveaway['limit']}\n\nВсе участники получили подарки!"
        keyboard = None 
    else:
        text = f"Раздача создана!\nЛимит участников: {giveaway['limit']}\nСумма каждому: {giveaway['amount']} 💰\nУчастников: {len(joined_users)}/{giveaway['limit']}"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Присоединиться", callback_data=f"enter_giveaway_{giveaway_id}")]
        ])

    try:
        if callback.inline_message_id:
            await bot.edit_message_text(text, inline_message_id=callback.inline_message_id, reply_markup=keyboard)
        else:
            await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise

    await callback.answer("Вы присоединились к раздаче!")

async def main():
    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    Config.validate()
    asyncio.run(main())
