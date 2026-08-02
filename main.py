import asyncio
import logging
import os
import sys
from os import getenv

import httpx
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

# Bot token can be obtained via https://t.me/BotFather
load_dotenv()
TOKEN = getenv("BOT_TOKEN")
API_URL = getenv("API_URL", "http://localhost:8000")
BOT_API_KEY = getenv("BOT_API_KEY")


# All handlers should be attached to the Router (or Dispatcher)

dp = Dispatcher()

TODO_STATES = {"draft", "todo", "doing", "done", "trash"}


@dp.message(Command("list"))
@dp.message(Command("todos"))
async def command_list_todos_handler(message: Message) -> None:
    """List todos using /list or /todos."""
    if not message.from_user:
        await message.answer("Não foi possível obter o ID do usuário.")
        return

    telegram_id = message.from_user.id

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{API_URL}/todos/",
                params={"telegram_id": telegram_id},
                headers={"X-Bot-Api-Key": BOT_API_KEY},
            )
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logging.error(f"Erro ao buscar tarefas: {e}")
        await message.answer("Ocorreu um erro ao buscar a lista de tarefas.")
        return

    todos = data if isinstance(data, list) else data.get("todos", [])
    if not todos:
        await message.answer("Nenhum TODO encontrado.")
        return

    todo_list = []
    for todo in todos:
        todo_list.append(
            f"#{todo['id']} | {todo['title']} | {todo['description']} | {todo['state']}"
        )

    await message.answer("TODOS:\n" + "\n".join(todo_list))


@dp.message(Command('users'))
async def command_list_users_handler(message: Message) -> None:
    if not message.from_user:
        await message.answer("Não foi possível obter o ID do usuário.")
        return

    telegram_id = message.from_user.id

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{API_URL}/users/",
                params={"offset": 0, "limit": 100, "telegram_id": telegram_id},
                headers={"X-Bot-Api-Key": BOT_API_KEY},
            )
            response.raise_for_status()
            data = response.json()
        await message.answer(f'{data}')
    except Exception as e:
        logging.error(f"Erro ao listar usuários: {e}")
        await message.answer("Ocorreu um erro ao listar os usuários.")


@dp.message(Command("todo"))
@dp.message(Command("addtodo"))
async def command_add_todo_handler(message: Message) -> None:
    """Create a new todo using /todo or /addtodo."""
    if not message.from_user:
        await message.answer("Não foi possível obter o ID do usuário.")
        return

    telegram_id = message.from_user.id

    if not message.text:
        await message.answer("Use: /todo Titulo | Descricao | state")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Use: /todo Titulo | Descricao | state\n"
            "States: draft, todo, doing, done, trash"
        )
        return

    raw_fields = [field.strip() for field in parts[1].split("|")]
    if len(raw_fields) != 3 or not all(raw_fields):
        await message.answer(
            "Formato esperado: /todo Titulo | Descricao | state\n"
            "Exemplo: /todo Estudar FastAPI | Criar comando no bot | doing"
        )
        return

    title, description, state = raw_fields
    state = state.lower()
    if state not in TODO_STATES:
        await message.answer(
            "State invalido. Use um destes: draft, todo, doing, done, trash"
        )
        return

    payload = {
        "title": title,
        "description": description,
        "state": state,
        "user_id": telegram_id,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{API_URL}/todos/",
                json=payload,
                headers={"X-Bot-Api-Key": BOT_API_KEY},
            )
            response.raise_for_status()
            data = response.json()

        await message.answer(
            "TODO criado com sucesso.\n"
            f"Titulo: {html.bold(data['title'])}\n"
            f"Descricao: {data['description']}\n"
            f"State: {data['state']}\n"
        )
    except Exception as e:
        logging.error(f"Erro ao criar TODO: {e}")
        await message.answer("Ocorreu um erro ao criar o TODO.")


@dp.message(Command("todo_edit"))
async def command_edit_todo_handler(message: Message) -> None:
    """Update a todo using /todo_edit."""
    if not message.from_user:
        await message.answer("Não foi possível obter o ID do usuário.")
        return

    telegram_id = message.from_user.id

    if not message.text:
        await message.answer(
            "Use: /todo_edit <id> | <title|null> | <description|null> | <state|null>"
        )
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Formato esperado: /todo_edit <id> | <title|null> | <description|null> | <state|null>\n"
            "Exemplo: /todo_edit 12 | Novo titulo | null | doing"
        )
        return

    raw_fields = [field.strip() for field in parts[1].split("|")]
    if len(raw_fields) != 4 or not raw_fields[0].isdigit():
        await message.answer(
            "Formato esperado: /todo_edit <id> | <title|null> | <description|null> | <state|null>\n"
            "Exemplo: /todo_edit 12 | Novo titulo | null | doing"
        )
        return

    todo_id = int(raw_fields[0])
    title_raw, description_raw, state_raw = raw_fields[1:]

    payload: dict[str, object] = {
        "telegram_id": telegram_id,
    }
    if title_raw.lower() != "null":
        payload["title"] = title_raw
    if description_raw.lower() != "null":
        payload["description"] = description_raw
    if state_raw.lower() != "null":
        state = state_raw.lower()
        if state not in TODO_STATES:
            await message.answer(
                "State invalido. Use um destes: draft, todo, doing, done, trash"
            )
            return
        payload["state"] = state

    if len(payload) <= 1:
        await message.answer(
            "Envie pelo menos um campo para atualizar.\n"
            "Formato: /todo_edit <id> | <title|null> | <description|null> | <state|null>"
        )
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.patch(
                f"{API_URL}/todos/{todo_id}",
                json=payload,
                params={"telegram_id": telegram_id},
                headers={"X-Bot-Api-Key": BOT_API_KEY},
            )
            response.raise_for_status()
            data = response.json()

        await message.answer(
            "TODO atualizado com sucesso.\n"
            f"ID: {data['id']}\n"
            f"Titulo: {html.bold(data['title'])}\n"
            f"Descricao: {data['description']}\n"
            f"State: {data['state']}"
        )
    except Exception as e:
        logging.error(f"Erro ao editar TODO: {e}")
        await message.answer("Ocorreu um erro ao atualizar o TODO.")


@dp.message(Command("todo_delete"))
async def command_delete_todo_handler(message: Message) -> None:
    """Delete a todo using /todo_delete."""
    if not message.from_user:
        await message.answer("Não foi possível obter o ID do usuário.")
        return

    telegram_id = message.from_user.id

    if not message.text:
        await message.answer("Use: /todo_delete <id>")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer(
            "Formato esperado: /todo_delete <id>\n"
            "Exemplo: /todo_delete 12"
        )
        return

    todo_id = int(parts[1].strip())

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(
                f"{API_URL}/todos/{todo_id}",
                params={"telegram_id": telegram_id},
                headers={"X-Bot-Api-Key": BOT_API_KEY},
            )
            response.raise_for_status()
            data = response.json()

        await message.answer(data.get("message", f"TODO {todo_id} apagado com sucesso."))
    except Exception as e:
        logging.error(f"Erro ao apagar TODO: {e}")
        await message.answer("Ocorreu um erro ao apagar o TODO.")


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/start` command and registers the user in the API.
    """
    user = message.from_user
    if user is None:
        await message.answer("Hello!")
        return

    telegram_id = user.id
    username_val = user.full_name or user.username or f"User_{user.id}"
    email_handle = (user.username or user.first_name or f"user_{user.id}").lower().replace(" ", "_")
    email_val = f"{email_handle}@teste.com"

    payload = {
        "id": user.id,
        "username": username_val,
        "email": email_val,
        "password": "teste@12345",
        "telegram_id": telegram_id,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{API_URL}/users/",
                json=payload,
                params={"telegram_id": telegram_id},
                headers={"X-Bot-Api-Key": BOT_API_KEY},
            )
            response.raise_for_status()
            data = response.json()
            await message.answer(
                f"Olá, {html.bold(user.full_name)}! Seu usuário foi criado com sucesso.\n"
                f"ID: {data.get('id')}\n"
                f"Username: {data.get('username')}\n"
                f"Email: {data.get('email')}"
            )
    except httpx.HTTPStatusError:
        # Se o usuário já existir ou retornar erro de status, saudamos o usuário
        await message.answer(f"Olá, {html.bold(user.full_name)}! Bem-vindo(a) de volta!")
    except Exception as e:
        logging.error(f"Erro ao criar usuário na API: {e}")
        await message.answer(f"Olá, {html.bold(user.full_name)}!")


@dp.message(Command('help'))
async def command_help_handler(message: Message) -> None:
    """
    This handler receives messages with `/help` command
    """
    await message.answer(
        "Comandos disponiveis:\n"
        "/todo Titulo | Descricao | state\n"
        "/addtodo Titulo | Descricao | state\n"
        "/list [offset] [limit]\n"
        "/todos [offset] [limit]\n"
        "/todo_edit ID | Titulo ou null | Descricao ou null | State ou null\n"
        "/todo_delete ID\n"
        "\n"
        "Formatos esperados:\n"
        "Criar: /todo Estudar FastAPI | Criar comando no bot | doing\n"
        "Editar: /todo_edit 12 | Novo titulo | null | done\n"
        "Apagar: /todo_delete 12\n"
        "Listar: /todos 0 100\n"
        "States: draft, todo, doing, done, trash"
    )


@dp.message()
async def echo_handler(message: Message) -> None:
    """
    Captura o ID do usuário (message.from_user.id) e o texto da mensagem,
    enviando os dados para a API (POST /messages).
    """
    if not message.from_user:
        await message.answer("Não foi possível obter os dados do usuário.")
        return

    telegram_id = message.from_user.id

    payload = {
        "user_id": message.from_user.id,
        "text": message.text or "",
        "telegram_id": telegram_id,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{API_URL}/messages",
                json=payload,
                params={"telegram_id": telegram_id},
                headers={"X-Bot-Api-Key": BOT_API_KEY},
            )
            response.raise_for_status()
            data = response.json()

        reply = data.get("reply", "Mensagem processada pela API.")
        await message.answer(reply)
    except Exception as e:
        logging.error(f"Erro ao comunicar com a API: {e}")
        await message.answer("Ocorreu um erro ao comunicar com a API.")


async def main() -> None:
    if TOKEN is None:
        raise RuntimeError("BOT_TOKEN is not set")
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # And the run events dispatching
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
