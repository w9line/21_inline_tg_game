import sqlite3
import json
from typing import Dict, Any, Optional

class Database:
    def __init__(self, db_path: str = 'games.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS games (
                    game_id TEXT PRIMARY KEY,
                    chat_id INTEGER,
                    creator_id INTEGER,
                    state TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_balances (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 200,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT UNIQUE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id INTEGER PRIMARY KEY,
                    total_wins INTEGER DEFAULT 0,
                    max_bet INTEGER DEFAULT 0,
                    max_consecutive_wins INTEGER DEFAULT 0,
                    current_consecutive_wins INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS giveaways (
                    id TEXT PRIMARY KEY,
                    creator_id INTEGER,
                    limit_count INTEGER,
                    amount INTEGER,
                    joined_users TEXT,  -- JSON list of user_ids
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def save_game(self, game_id: str, chat_id: int, creator_id: int, state: Dict[str, Any]):
        """Save or update a game state."""
        state_json = json.dumps(state)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO games (game_id, chat_id, creator_id, state, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (game_id, chat_id, creator_id, state_json))
            conn.commit()

    def load_game(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Load a game state by game_id."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT state FROM games WHERE game_id = ?', (game_id,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
        return None

    def delete_game(self, game_id: str):
        """Delete a game from the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM games WHERE game_id = ?', (game_id,))
            conn.commit()

    def get_games_by_chat(self, chat_id: int) -> list:
        """Get all active games in a chat."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT game_id FROM games WHERE chat_id = ?', (chat_id,))
            return [row[0] for row in cursor.fetchall()]

    def cleanup_old_games(self, days: int = 7):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                DELETE FROM games WHERE updated_at < datetime('now', '-{} days')
            '''.format(days))
            conn.commit()

    def get_user_balance(self, user_id: int) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT balance FROM user_balances WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            if row:
                return row[0]
            else:
                conn.execute('INSERT INTO user_balances (user_id, balance) VALUES (?, ?)', (user_id, 200))
                conn.commit()
                return 200

    def save_user_balance(self, user_id: int, balance: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO user_balances (user_id, balance, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, balance))
            conn.commit()

    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT total_wins, max_bet, max_consecutive_wins, current_consecutive_wins FROM user_stats WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'total_wins': row[0],
                    'max_bet': row[1],
                    'max_consecutive_wins': row[2],
                    'current_consecutive_wins': row[3]
                }
            else:
                conn.execute('INSERT INTO user_stats (user_id) VALUES (?)', (user_id,))
                conn.commit()
                return {
                    'total_wins': 0,
                    'max_bet': 0,
                    'max_consecutive_wins': 0,
                    'current_consecutive_wins': 0
                }

    def save_user_stats(self, user_id: int, total_wins: int, max_bet: int, max_consecutive_wins: int, current_consecutive_wins: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO user_stats (user_id, total_wins, max_bet, max_consecutive_wins, current_consecutive_wins, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, total_wins, max_bet, max_consecutive_wins, current_consecutive_wins))
            conn.commit()

    def save_username(self, user_id: int, username: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO users (user_id, username, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, username))
            conn.commit()

    def save_giveaway(self, giveaway_id: str, creator_id: int, limit: int, amount: int, joined_users: list):
        joined_json = json.dumps(joined_users)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO giveaways (id, creator_id, limit_count, amount, joined_users, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (giveaway_id, creator_id, limit, amount, joined_json))
            conn.commit()

    def load_giveaway(self, giveaway_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT creator_id, limit_count, amount, joined_users, status FROM giveaways WHERE id = ?', (giveaway_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'creator_id': row[0],
                    'limit': row[1],
                    'amount': row[2],
                    'joined_users': json.loads(row[3]),
                    'status': row[4]
                }
        return None

    def update_giveaway_status(self, giveaway_id: str, status: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('UPDATE giveaways SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (status, giveaway_id))
            conn.commit()
