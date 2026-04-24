import sqlite3
import json
import os
from typing import List, Dict, Any

class SQLiteStore:
    def __init__(self, db_path: str = "data/meeting_notes.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS meetings (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    date TEXT,
                    transcript TEXT,
                    metadata TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS summaries (
                    meeting_id TEXT PRIMARY KEY,
                    executive_summary TEXT,
                    bullet_highlights TEXT,
                    decisions TEXT,
                    risks_blockers TEXT,
                    FOREIGN KEY (meeting_id) REFERENCES meetings (id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS action_items (
                    id TEXT PRIMARY KEY,
                    meeting_id TEXT,
                    task TEXT,
                    owner TEXT,
                    deadline TEXT,
                    status TEXT,
                    FOREIGN KEY (meeting_id) REFERENCES meetings (id)
                )
            ''')
            conn.commit()

    def save_meeting(self, meeting_dict: Dict[str, Any]):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO meetings (id, title, date, transcript, metadata) VALUES (?, ?, ?, ?, ?)',
                (meeting_dict['id'], meeting_dict.get('title', 'Untitled'), str(meeting_dict.get('date', '')),
                 meeting_dict.get('transcript', ''), json.dumps(meeting_dict.get('metadata', {})))
            )
            conn.commit()

    def save_summary(self, summary_dict: Dict[str, Any]):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT OR REPLACE INTO summaries 
                   (meeting_id, executive_summary, bullet_highlights, decisions, risks_blockers) 
                   VALUES (?, ?, ?, ?, ?)''',
                (summary_dict['meeting_id'], summary_dict.get('executive_summary', ''),
                 json.dumps(summary_dict.get('bullet_highlights', [])),
                 json.dumps(summary_dict.get('decisions', [])),
                 json.dumps(summary_dict.get('risks_blockers', [])))
            )
            for item in summary_dict.get('action_items', []):
                if isinstance(item, dict):
                    cursor.execute(
                        '''INSERT OR REPLACE INTO action_items 
                           (id, meeting_id, task, owner, deadline, status) 
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (item['id'], item['meeting_id'], item['task'], item.get('owner', ''), item.get('deadline', ''), item.get('status', 'Pending'))
                    )
            conn.commit()

    def get_all_meetings(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, title, date FROM meetings')
            rows = cursor.fetchall()
            return [{'id': row[0], 'title': row[1], 'date': row[2]} for row in rows]

    def get_meeting(self, meeting_id: str) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM meetings WHERE id = ?', (meeting_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_summary(self, meeting_id: str) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM summaries WHERE meeting_id = ?', (meeting_id,))
            summary_row = cursor.fetchone()
            
            cursor.execute('SELECT * FROM action_items WHERE meeting_id = ?', (meeting_id,))
            action_items = [dict(r) for r in cursor.fetchall()]
            
            if summary_row:
                res = dict(summary_row)
                res['action_items'] = action_items
                res['bullet_highlights'] = json.loads(res['bullet_highlights']) if res['bullet_highlights'] else []
                res['decisions'] = json.loads(res['decisions']) if res['decisions'] else []
                res['risks_blockers'] = json.loads(res['risks_blockers']) if res['risks_blockers'] else []
                return res
            return None
