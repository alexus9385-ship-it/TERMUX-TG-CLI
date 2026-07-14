import asyncio
import os
import sys
import glob
import json
import getpass
from datetime import datetime
from telethon import TelegramClient, events, functions, types, errors
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from colorama import Fore, init

# Инициализация
init(autoreset=True)
console = Console()

# --- ПУТИ ---
CONFIG_FILE = "config.json"
LANG_DIR = "LANG"
THEME_DIR = "THEMES"
DOWNLOAD_DIR = "DOWNLOADS"

for directory in [LANG_DIR, THEME_DIR, DOWNLOAD_DIR]:
    os.makedirs(directory, exist_ok=True)

# Глобальное состояние
state = {
    'client': None,
    'dialogs': [],
    'page_size': 10,
    'current_page': 0,
    'history_limit': 20,
    'last_msgs': [],
    'config': {
        'api_id': None,
        'api_hash': None,
        'history_limit': 20,
        'page_size': 10,
        'lang': 'RU',
        'theme': 'Classic'
    },
    'strings': {},
    'colors': {
        'primary': 'cyan',
        'secondary': 'green',
        'error': 'red',
        'panel': 'blue',
        'title': 'magenta'
    }
}

# --- СИСТЕМА ЛОКАЛИЗАЦИИ ---

def load_lang():
    lang_path = os.path.join(LANG_DIR, f"{state['config']['lang']}.json")
    if not os.path.exists(lang_path):
        # Дефолтный русский перевод
        default_strings = {
            "m_chats": "Список чатов",
            "m_search": "Поиск людей",
            "m_me": "Мой Профиль",
            "m_settings": "Настройки",
            "m_acc": "Сменить аккаунт",
            "m_exit": "Выход",
            "p_title": "ПРОФИЛЬ 🤙",
            "p_write": "1 - Написать",
            "p_block": "2 - Заблокировать",
            "p_back": "Enter - Назад",
            "c_header": "💬 [bold]{}[/] | Стр: {} | [dim]/P-Профиль /N-Старое BACK-Выход[/]",
            "c_cmds": "[dim]/r [№] ответ | /e [№] ред | /d [№] удал | /dl [№] скач[/]",
            "s_title": "⚙️ НАСТРОЙКИ CLI",
            "s_lang": "1. Язык (LANG): {}",
            "s_theme": "2. Тема (THEME): {}",
            "s_hist": "3. Лимит истории: {}",
            "s_page": "4. Чатов на страницу: {}",
            "s_back": "0. Сохранить и выйти"
        }
        with open(lang_path, 'w', encoding='utf-8') as f:
            json.dump(default_strings, f, ensure_ascii=False, indent=4)
    
    with open(lang_path, 'r', encoding='utf-8') as f:
        state['strings'] = json.load(f)

def _(key): 
    return state['strings'].get(key, key)

# --- СИСТЕМА ТЕМ ---

def load_theme():
    theme_path = os.path.join(THEME_DIR, f"{state['config']['theme']}.json")
    if not os.path.exists(theme_path):
        default_colors = {
            "primary": "cyan",
            "secondary": "green",
            "error": "red",
            "panel": "blue",
            "title": "magenta"
        }
        with open(theme_path, 'w', encoding='utf-8') as f:
            json.dump(default_colors, f, indent=4)
    
    with open(theme_path, 'r', encoding='utf-8') as f:
        state['colors'].update(json.load(f))

# --- КОНФИГУРАЦИЯ ---

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            state['config'].update(json.load(f))
    load_lang()
    load_theme()
    state['history_limit'] = state['config']['history_limit']
    state['page_size'] = state['config']['page_size']

def save_config():
    state['config']['history_limit'] = state['history_limit']
    state['config']['page_size'] = state['page_size']
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(state['config'], f, indent=4)

# --- УТИЛИТЫ ---

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_status_icon(entity):
    if isinstance(entity, types.User):
        if isinstance(entity.status, types.UserStatusOnline):
            return "[bold green]● Online[/]"
        return "[grey50]○ Offline[/]"
    return f"[{state['colors']['primary']}]Shared[/]"

async def get_msg_text(msg):
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

# --- ПРОФИЛЬ ---

async def view_profile(entity):
    clear_screen()
    with console.status("[bold yellow]Wait..."):
        try:
            if isinstance(entity, types.User):
                full = await state['client'](functions.users.GetFullUserRequest(entity))
                about = full.full_user.about or "---"
                details = (
                    f"👤 [bold white]Имя:[/] {entity.first_name}\n"
                    f"📧 [bold white]Username:[/] @{entity.username or 'нет'}\n"
                    f"🆔 [bold white]ID:[/] [cyan]{entity.id}[/]\n"
                    f"📊 [bold white]Статус:[/] {get_status_icon(entity)}\n"
                    f"📝 [bold white]О себе:[/] [italic]{about}[/]"
                )
            else:
                full = await state['client'](functions.channels.GetFullChannelRequest(entity))
                details = (
                    f"📢 [bold white]Название:[/] {getattr(entity, 'title', '???')}\n"
                    f"🆔 [bold white]ID:[/] [cyan]{entity.id}[/]\n"
                    f"👥 [bold white]Людей:[/] {getattr(full.full_chat, 'participants_count', '?')}\n"
                )

            console.print(Panel(details, title=f" {_( 'p_title' )} ", border_style=state['colors']['title'], expand=False))
            console.print(f"\n[bold green]{_('p_write')}[/] | [bold red]{_('p_block')}[/] | [bold white]{_('p_back')}[/]")
            
            choice = await asyncio.to_thread(input, "> ")
            if choice == "1": return True
            elif choice == "2" and isinstance(entity, types.User):
                await state['client'](functions.contacts.BlockRequest(id=entity))
                console.print("[red]Blocked[/]"); await asyncio.sleep(1)
            return False
        except Exception as e:
            console.print(f"[red]Error: {e}[/]"); await asyncio.sleep(2); return False

# --- ЧАТ ---

async def show_chat(chat_entity):
    chat_page = 0
    title = getattr(chat_entity, 'title', getattr(chat_entity, 'first_name', 'Чат'))
    
    @state['client'].on(events.NewMessage(chats=chat_entity))
    async def handler(event):
        if not event.out and chat_page == 0:
            s = await event.get_sender()
            t = await get_msg_text(event.message)
            console.print(f"\n[bold {state['colors']['primary']}]{getattr(s, 'first_name', 'U')}:[/] {t}")
            print(Fore.WHITE + "> ", end='', flush=True)

    while True:
        clear_screen()
        console.print(Panel(
            _("c_header").format(title, chat_page + 1) + "\n" + _("c_cmds"), 
            border_style=state['colors']['panel']
        ))
        
        try:
            msgs = await state['client'].get_messages(chat_entity, limit=state['history_limit'], add_offset=chat_page*state['history_limit'])
            state['last_msgs'] = list(msgs)
            for i, m in enumerate(reversed(msgs)):
                sender = await m.get_sender()
                color = state['colors']['secondary'] if m.out else state['colors']['primary']
                idx = len(msgs) - i
                console.print(f"[dim]{idx}.[/] [{m.date.strftime('%H:%M')}] [bold {color}]{getattr(sender, 'first_name', 'U')}:[/] {await get_msg_text(m)}")
        except Exception as e:
            console.print(f"[red]Error: {e}[/]")

        cmd = (await asyncio.to_thread(input, Fore.WHITE + "> ")).strip()
        if not cmd: continue
        if cmd.upper() == "BACK": break
        
        try:
            if cmd.startswith("/r "):
                p = cmd.split(maxsplit=2)
                await state['client'].send_message(chat_entity, p[2], reply_to=state['last_msgs'][int(p[1])-1])
            elif cmd.startswith("/e "):
                p = cmd.split(maxsplit=2)
                await state['client'].edit_message(chat_entity, state['last_msgs'][int(p[1])-1], p[2])
            elif cmd.startswith("/d "):
                await state['client'].delete_messages(chat_entity, [state['last_msgs'][int(cmd.split()[1])-1]])
            elif cmd.startswith("/dl "):
                msg = state['last_msgs'][int(cmd.split()[1])-1]
                if msg.media:
                    path = await state['client'].download_media(msg, file=DOWNLOAD_DIR)
                    console.print(f"[green]Saved: {path}[/]"); await asyncio.sleep(1)
            elif cmd.upper() == "/P": await view_profile(chat_entity)
            elif cmd.upper() == "/N": chat_page += 1
            elif cmd.upper() == "/B": chat_page = max(0, chat_page - 1)
            else:
                if os.path.exists(cmd): await state['client'].send_file(chat_entity, cmd)
                else: await state['client'].send_message(chat_entity, cmd); chat_page = 0
        except Exception as e:
            console.print(f"[red]Error: {e}[/]"); await asyncio.sleep(1)
    
    state['client'].remove_event_handler(handler)

# --- МЕНЮ НАСТРОЕК ---

async def settings_menu():
    while True:
        clear_screen()
        console.print(Panel(
            f"[bold]{_('s_title')}[/]\n\n"
            f"{_('s_lang').format(state['config']['lang'])}\n"
            f"{_('s_theme').format(state['config']['theme'])}\n"
            f"{_('s_hist').format(state['history_limit'])}\n"
            f"{_('s_page').format(state['page_size'])}\n"
            f"{_('s_back')}", border_style="yellow"
        ))
        choice = await asyncio.to_thread(input, "Choice > ")
        if choice == "1":
            new_l = await asyncio.to_thread(input, "Lang (RU/EN): ")
            state['config']['lang'] = new_l.upper(); load_lang()
        elif choice == "2":
            new_t = await asyncio.to_thread(input, "Theme Name: ")
            state['config']['theme'] = new_t; load_theme()
        elif choice == "3":
            v = await asyncio.to_thread(input, "Limit: ")
            if v.isdigit(): state['history_limit'] = int(v)
        elif choice == "4":
            v = await asyncio.to_thread(input, "Page: ")
            if v.isdigit(): state['page_size'] = int(v)
        elif choice == "0":
            save_config(); break

# --- АККАУНТЫ И ЧАТЫ ---

async def account_manager():
    while True:
        clear_screen()
        sessions = [os.path.basename(f).replace('.session', '') for f in glob.glob("*.session") if 'session_name' not in f]
        table = Table(title="ACCOUNTS", expand=True)
        table.add_column("№", style="yellow")
        table.add_column("Session")
        for i, s in enumerate(sessions): table.add_row(str(i + 1), s)
        console.print(table)
        console.print("\n[bold green]ADD[/] | [bold red]DEL [№][/] | [bold red]Q[/]-Exit")
        c = (await asyncio.to_thread(input, "> ")).strip().upper()
        if c == "Q": sys.exit(0)
        elif c == "ADD": return await asyncio.to_thread(input, "Phone: ")
        elif c.startswith("DEL "):
            try: os.remove(f"{sessions[int(c.split()[1])-1]}.session")
            except: pass
        elif c.isdigit() and 0 <= int(c)-1 < len(sessions): return sessions[int(c)-1]

async def chat_list_menu():
    while True:
        with console.status("[bold yellow]Sync..."):
            state['dialogs'] = await state['client'].get_dialogs()
        clear_screen()
        total_pages = (len(state['dialogs']) - 1) // state['page_size'] + 1
        start = state['current_page'] * state['page_size']
        end = min(start + state['page_size'], len(state['dialogs']))

        table = Table(title=f"{_('m_chats')} ({state['current_page']+1}/{total_pages})", expand=True)
        table.add_column("№", style="yellow")
        table.add_column("Name")
        table.add_column("Unread", justify="center")
        table.add_column("Status", justify="right")
        
        for i in range(start, end):
            d = state['dialogs'][i]
            unread = f"[bold red]{d.unread_count}[/]" if d.unread_count > 0 else "0"
            table.add_row(str(i + 1), (d.name or "???")[:30], unread, get_status_icon(d.entity))

        console.print(table)
        console.print("\n[bold yellow]N[/]-след | [bold yellow]B[/]-пред | [bold cyan]P [№][/]-профиль | [bold red]BACK[/]-меню")
        cmd = (await asyncio.to_thread(input, "Choice > ")).strip().upper()
        if cmd == "BACK": break
        elif cmd == "N" and (state['current_page'] + 1) < total_pages: state['current_page'] += 1
        elif cmd == "B" and state['current_page'] > 0: state['current_page'] -= 1
        elif cmd.startswith("P "):
            try:
                idx = int(cmd.split()[1]) - 1
                if await view_profile(state['dialogs'][idx].entity): await show_chat(state['dialogs'][idx].entity)
            except: pass
        elif cmd.isdigit():
            try: await show_chat(state['dialogs'][int(cmd)-1].entity)
            except: pass

async def main():
    load_config()
    if not state['config'].get('api_id'):
        state['config']['api_id'] = int(input("API ID: "))
        state['config']['api_hash'] = input("API HASH: ")
        save_config()

    session_id = await account_manager()
    state['client'] = TelegramClient(session_id, int(state['config']['api_id']), state['config']['api_hash'])
    
    await state['client'].start(
        phone=lambda: session_id if '+' in session_id else input("Phone: "),
        password=lambda: getpass.getpass("2FA Password: ")
    )

    while True:
        clear_screen()
        me = await state['client'].get_me()
        console.print(Panel.fit(
            f"📱 [bold cyan]TERMUX TG CLI[/] | [green]@{me.username or me.first_name}[/]\n"
            "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"1. {_('m_chats')} | 2. {_('m_search')}\n"
            f"3. {_('m_me')} | 4. {_('m_settings')}\n"
            f"5. {_('m_acc')} | 0. {_('m_exit')}", padding=(1, 5), border_style=state['colors']['panel']
        ))
        
        choice = (await asyncio.to_thread(input, "> ")).strip()
        if choice == "1": await chat_list_menu()
        elif choice == "2":
            q = await asyncio.to_thread(input, "Search: ")
            try:
                ent = await state['client'].get_entity(int(q) if q.strip('-').isdigit() else q)
                if await view_profile(ent): await show_chat(ent)
            except: console.print("[red]Not found[/]"); await asyncio.sleep(1)
        elif choice == "3":
            if await view_profile(me): await show_chat(me)
        elif choice == "4": await settings_menu()
        elif choice == "5":
            await state['client'].disconnect(); return await main()
        elif choice == "0": break

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: sys.exit(0)