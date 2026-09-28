import sqlite3
from pathlib import Path

SCHEMA = '''
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS world_state (
  id INTEGER PRIMARY KEY CHECK (id=1),
  world_time TEXT NOT NULL,
  location_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entities (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  name TEXT NOT NULL,
  location_id TEXT,
  data_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS inventory (
  owner_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK(quantity >= 0),
  PRIMARY KEY(owner_id, item_id)
);
CREATE TABLE IF NOT EXISTS money (
  owner_id TEXT PRIMARY KEY,
  silver INTEGER NOT NULL CHECK(silver >= 0)
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_time TEXT NOT NULL,
  event_type TEXT NOT NULL,
  actor_id TEXT,
  target_id TEXT,
  data_json TEXT NOT NULL DEFAULT '{}'
);
'''

class Database:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def execute(self, sql, params=()):
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def query(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def close(self):
        self.conn.close()
