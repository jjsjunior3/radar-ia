"""Progresso local do protótipo; não confundir com histórico editorial."""
import math
import sqlite3
from pathlib import Path
from datetime import datetime, timezone


class ProgressStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS progress (episode_id TEXT PRIMARY KEY, position REAL NOT NULL, heard INTEGER NOT NULL, updated_at TEXT NOT NULL)')

    def connection(self):
        return sqlite3.connect(self.path)

    def all(self):
        with self.connection() as db:
            db.row_factory = sqlite3.Row
            return {r['episode_id']: dict(position=r['position'], heard=bool(r['heard']), updated_at=r['updated_at']) for r in db.execute('SELECT * FROM progress')}

    def save(self, episode_id, duration, *, position=None, heard=None):
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError('Duração inválida')
        if position is not None and (type(position) not in (float,int) or not math.isfinite(position) or not 0 <= position <= duration):
            raise ValueError('Posição inválida')
        if heard is not None and type(heard) is not bool:
            raise ValueError('Marcação inválida')
        with self.connection() as db:
            row = db.execute('SELECT position, heard FROM progress WHERE episode_id=?',(episode_id,)).fetchone()
            previous_position, previous_heard = row if row else (0.0,0)
            new_position = position if position is not None else previous_position
            # Marcação manual tem prioridade. Desmarcar preserva a posição.
            new_heard = heard if heard is not None else bool(previous_heard or (previous_position < .95*duration <= new_position))
            stamp = datetime.now(timezone.utc).isoformat()
            db.execute('INSERT INTO progress VALUES (?,?,?,?) ON CONFLICT(episode_id) DO UPDATE SET position=excluded.position, heard=excluded.heard, updated_at=excluded.updated_at',
                       (episode_id,new_position,int(new_heard),stamp))
        return dict(position=new_position,heard=bool(new_heard),updated_at=stamp)
