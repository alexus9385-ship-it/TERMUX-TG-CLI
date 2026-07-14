import asyncio
import os
import sys
import glob
import json
from datetime import datetime
from telethon import TelegramClient, events, functions, types, errors
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from colorama import Fore, init

# Инициализация
init(autoreset=True)
console = Console()
CONFIG_FILE = "config.json"

# Глобальное состояние приложения
state = {
    'client': None,
    'dialogs': [],
    'page_size': 10,
    'current_page': 0,
    'history_limit': 20,
    'config': {
        'api_id': None,
        'api_hash': None,
        'history_limit': 20,
        'page_size': 10
    }
}

# --- СИСТЕМНЫЕ ФУНКЦИИ ---

def clear_screen():
    """Очистка терминала"""
    os.system('cls' if os.name == 'nt' else 'clear')

def load_config():
    """Загрузка настроек"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            state['config'].update(data)
            state['history_limit'] = state['config'].get('history_limit', 20)
            state['page_size'] = state['config'].get('page_size', 10)

def save_config():
    """Сохранение настроек"""
    state['config']['history_limit'] = state['history_limit']
    state['config']['page_size'] = state['page_size']
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(state['config'], f, indent=4)

def get_status_icon(entity):
    """Иконка статуса пользователя"""
    if isinstance(entity, types.User):
        if isinstance(entity.status, types.UserStatusOnline):
            return "[bold green]● Online[/]"
        return "[grey50]○ Offline[/]"
    return "[cyan]Shared[/]"

async def get_msg_text(msg):
    """Форматирование медиа и текста сообщения"""
    m_type = ""
    if msg.photo: m_type = "[🎨 Фото] "
    elif msg.voice: m_type = "[🎤 Голос] "
    elif msg.video_note: m_type = "[🎥 Кружок] "
    elif msg.sticker: m_type = "[🖼 Стикер] "
    elif msg.document: m_type = f"[📄 Файл: {msg.file.name or '...'}] "
    
    txt = msg.text or ""
    if msg.reply_to:
        return f"[yellow]⤷[/] {m_type}{txt}"
    return f"{m_type}{txt}"

# --- ПРОФИЛИ И ПОИСК ---

async def view_profile(entity):
    """Просмотр профиля с возможностью написать (возвращает True если выбрано 'Написать')"""
    clear_screen()
    with console.status("[bold yellow]Загрузка профиля..."):
        try:
            if isinstance(entity, types.User):
                full = await state['client'](functions.users.GetFullUserRequest(entity))
                about = full.full_user.about or "Биография не заполнена"
                details = (
                    f"👤 [bold white]Имя:[/] {entity.first_name} {entity.last_name or ''}\n"
                    f"📧 [bold white]Username:[/] @{entity.username or 'нет'}\n"
                    f"🆔 [bold white]ID:[/] [cyan]{entity.id}[/]\n"
                    f"📱 [bold white]Телефон:[/] {getattr(entity, 'phone', 'скрыт')}\n"
                    f"📊 [bold white]Статус:[/] {get_status_icon(entity)}\n"
                    f"📝 [bold white]О себе:[/] [italic]{about}[/]"
                )
            else:
                try:
                    full = await state['client'](functions.channels.GetFullChannelRequest(entity))
                    about = full.full_chat.about or "Описание отсутствует"
                    participants = full.full_chat.participants_count
                except:
                    about = "Нет доступа"; participants = "?"
                
                details = (
                    f"📢 [bold white]Название:[/] {getattr(entity, 'title', '???')}\n"
                    f"📧 [bold white]Username:[/] @{getattr(entity, 'username', 'нет')}\n"
                    f"🆔 [bold white]ID:[/] [cyan]{entity.id}[/]\n"
                    f"👥 [bold white]Участников:[/] {participants}\n"
                    f"📝 [bold white]О канале:[/] [italic]{about}[/]"
                )
            
            console.print(Panel(details, title=" ПРОФИЛЬ 🤙 ", border_style="magenta", expand=False))
            console.print("\n[bold green]1[/] - Написать сообщение | [bold white]Enter[/] - Назад")
            choice = await asyncio.to_thread(input, "> ")
            return choice == "1"
        except Exception as e:
            console.print(f"[red]Ошибка профиля: {e}[/]"); await asyncio.sleep(2)
            return False

async def search_user():
    """Глобальный поиск"""
    clear_screen()
    console.print(Panel.fit("🔍 [bold cyan]ПОИСК[/]\nВведите @username, номер телефона или ID", border_style="cyan"))
    q = (await asyncio.to_thread(input, "Поиск > ")).strip()
    if not q: return
    try:
        with console.status("[bold yellow]Ищу..."):
            target = int(q) if q.replace('-', '').isdigit() else q
            entity = await state['client'].get_entity(target)
        if await view_profile(entity):
            await show_chat(entity)
    except Exception as e:
        console.print(f"[red]Не найдено: {e}[/]"); await asyncio.sleep(2)

# --- ЧАТ ---

async def show_chat(chat_entity):
    """Окно переписки"""
    chat_page = 0
    title = getattr(chat_entity, 'title', getattr(chat_entity, 'first_name', 'Чат'))
    
    @state['client'].on(events.NewMessage(chats=chat_entity))
    async def handler(event):
        if not event.out and chat_page == 0:
            s = await event.get_sender()
            t = await get_msg_text(event.message)
            console.print(f"[{datetime.now().strftime('%H:%M')}] [bold cyan]{getattr(s, 'first_name', 'U')}:[/] {t}")
            print(Fore.WHITE + "> ", end='', flush=True)

    while True:
        clear_screen()
        console.print(Panel(f"💬 [bold]{title}[/] | Стр: {chat_page + 1} | [dim]/P-Профиль /N-Старое BACK-Выход[/]", border_style="blue"))
        
        try:
            msgs = await state['client'].get_messages(chat_entity, limit=state['history_limit'], add_offset=chat_page*state['history_limit'])
            for m in reversed(msgs):
                sender = await m.get_sender()
                text = await get_msg_text(m)
                color = "green" if m.out else "cyan"
                console.print(f"[{m.date.strftime('%H:%M')}] [bold {color}]{getattr(sender, 'first_name', 'U')}:[/] {text}")
        except Exception as e:
            console.print(f"[red]Ошибка истории: {e}[/]")

        cmd = (await asyncio.to_thread(input, Fore.WHITE + "> ")).strip()
        if not cmd: continue
        
        up_cmd = cmd.upper()
        if up_cmd == "BACK":
            break
        elif up_cmd.startswith("/P"):
            if await view_profile(chat_entity):
                pass # Мы уже в этом чате
        elif up_cmd.startswith("/N"):
            parts = up_cmd.split()
            chat_page = int(parts[1]) - 1 if len(parts) > 1 and parts[1].isdigit() else chat_page + 1
        elif up_cmd.startswith("/B"):
            chat_page = max(0, chat_page - 1)
        else:
            try:
                if os.path.exists(cmd) and os.path.isfile(cmd):
                    await state['client'].send_file(chat_entity, cmd)
                else:
                    await state['client'].send_message(chat_entity, cmd)
                    chat_page = 0
            except Exception as e:
                if isinstance(e, errors.InputUserDeactivatedError):
                    console.print("[bold red]❌ Ошибка: Пользователь удален.[/]")
                else:
                    console.print(f"[bold red]❌ Ошибка отправки: {e}[/]")
                await asyncio.sleep(2)
    
    state['client'].remove_event_handler(handler)

# --- МЕНЕДЖЕРЫ ---

async def settings_menu():
    """Меню настроек"""
    while True:
        clear_screen()
        console.print(Panel(
            f"⚙️ [bold]НАСТРОЙКИ[/]\n\n"
            f"1. Лимит истории: [cyan]{state['history_limit']}[/]\n"
            f"2. Чатов на страницу: [cyan]{state['page_size']}[/]\n"
            f"0. Назад", border_style="yellow"
        ))
        choice = await asyncio.to_thread(input, "Выбор > ")
        if choice == "1":
            v = await asyncio.to_thread(input, "Число (10-100): ")
            if v.isdigit(): state['history_limit'] = int(v)
        elif choice == "2":
            v = await asyncio.to_thread(input, "Число (5-30): ")
            if v.isdigit(): state['page_size'] = int(v)
        elif choice == "0":
            save_config(); break

async def account_manager():
    """Выбор или добавление аккаунта"""
    while True:
        clear_screen()
        sessions = [os.path.basename(f).replace('.session', '') for f in glob.glob("*.session") if 'session_name' not in f]
        
        table = Table(title="ВАШИ АККАУНТЫ", expand=True)
        table.add_column("№", style="yellow", justify="center")
        table.add_column("Сессия (Номер)", style="white")

        for i, s in enumerate(sessions):
            table.add_row(str(i + 1), s)

        console.print(table)
        console.print("\n[bold green]ADD[/]-Добавить | [bold red]DEL [№][/]-Удалить | [bold red]Q[/]-Выход")
        
        c = (await asyncio.to_thread(input, "Выбор > ")).strip().upper()
        if c == "Q": sys.exit(0)
        elif c == "ADD":
            return await asyncio.to_thread(input, "Введите номер (+...): ")
        elif c.startswith("DEL "):
            try:
                idx = int(c.split()[1]) - 1
                os.remove(f"{sessions[idx]}.session")
                console.print("[green]Удалено.[/]"); await asyncio.sleep(1)
            except: pass
        elif c.isdigit() and 0 <= int(c)-1 < len(sessions):
            return sessions[int(c)-1]

async def chat_list_menu():
    """Таблица чатов"""
    with console.status("[bold yellow]Загрузка диалогов..."):
        state['dialogs'] = await state['client'].get_dialogs()
        
    while True:
        clear_screen()
        total = len(state['dialogs'])
        total_pages = (total - 1) // state['page_size'] + 1
        start = state['current_page'] * state['page_size']
        end = min(start + state['page_size'], total)

        table = Table(title=f"МОИ ЧАТЫ (Стр. {state['current_page']+1}/{total_pages})", expand=True)
        table.add_column("№", style="yellow", justify="center")
        table.add_column("Имя", style="white")
        table.add_column("Новые", justify="center")
        table.add_column("Статус", justify="right")
        
        for i in range(start, end):
            d = state['dialogs'][i]
            unread = f"[bold red]{d.unread_count}[/]" if d.unread_count > 0 else "0"
            table.add_row(str(i + 1), (d.name or "???")[:30], unread, get_status_icon(d.entity))

        console.print(table)
        console.print("\n[bold yellow]N[/]-след | [bold yellow]B[/]-пред | [bold cyan]P [№][/]-профиль | [bold red]BACK[/]-меню")
        
        cmd = (await asyncio.to_thread(input, "Выбор > ")).strip().upper()
        if cmd == "BACK": break
        elif cmd == "N" and (state['current_page'] + 1) < total_pages: state['current_page'] += 1
        elif cmd == "B" and state['current_page'] > 0: state['current_page'] -= 1
        elif cmd.startswith("P "):
            try:
                idx = int(cmd.split()[1]) - 1
                if await view_profile(state['dialogs'][idx].entity):
                    await show_chat(state['dialogs'][idx].entity)
            except: pass
        elif cmd.isdigit():
            idx = int(cmd) - 1
            if 0 <= idx < total: await show_chat(state['dialogs'][idx].entity)

# --- ГЛАВНЫЙ ЦИКЛ ---

async def main():
    load_config()
    
    if not state['config'].get('api_id'):
        clear_screen()
        console.print(Panel("ПЕРВИЧНАЯ НАСТРОЙКА API", border_style="yellow"))
        state['config']['api_id'] = int(await asyncio.to_thread(input, "Введите API ID: "))
        state['config']['api_hash'] = await asyncio.to_thread(input, "Введите API HASH: ")
        save_config()

    session_id = await account_manager()
    state['client'] = TelegramClient(session_id, int(state['config']['api_id']), state['config']['api_hash'])
    
    try:
        phone_p = session_id if '+' in session_id else lambda: input("Введите номер: ")
        await state['client'].start(phone=phone_p)
    except Exception as e:
        console.print(f"[red]Ошибка: {e}[/]"); await asyncio.sleep(2); return await main()

    while True:
        clear_screen()
        me = await state['client'].get_me()
        console.print(Panel.fit(
            f"📱 [bold cyan]TERMUX TELEGRAM CLI[/] | [green]@{me.username or me.first_name}[/]\n"
            "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            "1. [bold white]Список чатов[/]\n"
            "2. [bold yellow]Поиск людей[/]\n"
            "3. [bold white]Мой Профиль[/]\n"
            "4. [bold magenta]Настройки[/]\n"
            "5. [bold blue]Сменить аккаунт[/]\n"
            "0. [bold red]Выход[/]", padding=(1, 5), border_style="cyan"
        ))
        
        choice = await asyncio.to_thread(input, "Меню > ")
        if choice == "1": await chat_list_menu()
        elif choice == "2": await search_user()
        elif choice == "3":
            if await view_profile(me): await show_chat(me)
        elif choice == "4": await settings_menu()
        elif choice == "5":
            await state['client'].disconnect()
            state['dialogs'] = []
            return await main()
        elif choice == "0": break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)