import json
import aiosqlite
from config import DATABASE_PATH


async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                tokens TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS oauth_states (
                state TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Clean up expired states older than 10 minutes
        await db.execute("""
            DELETE FROM oauth_states
            WHERE created_at < datetime('now', '-10 minutes')
        """)
        await db.commit()


async def save_tokens(user_id: int, tokens: dict):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO users (user_id, tokens, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)""",
            (user_id, json.dumps(tokens)),
        )
        await db.commit()


async def get_tokens(user_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT tokens FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return json.loads(row[0]) if row else None


async def delete_tokens(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()


async def save_oauth_state(state: str, user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO oauth_states (state, user_id) VALUES (?, ?)",
            (state, user_id),
        )
        await db.commit()


async def get_user_id_by_state(state: str) -> int | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM oauth_states WHERE state = ?", (state,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def delete_oauth_state(state: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
        await db.commit()
