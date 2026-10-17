"""
journal.py — Journal append-only des recommandations et suivi du CLV (SQLite).

Composants ⑤ et ⑥ de l'architecture :
- Journalise chaque recommandation (probabilité sharp, cote offerte, book, EV, mise Kelly)
- Permet l'enregistrement des cotes de clôture pour le calcul du CLV (Closing Line Value)
- Calcule les métriques de synthèse (nombre de signaux, EV moyen, CLV moyen)
"""
from __future__ import annotations
import datetime
import json
import os
import sqlite3
from typing import Dict, List, Optional, Any

try:
    from feeds import norm_team_key
except ImportError:
    try:
        from src.feeds import norm_team_key
    except ImportError:
        import re
        def norm_team_key(s: str) -> str:
            s = str(s or "").lower().strip()
            s = re.sub(r'\bst\b', 'saint', s)
            s = re.sub(r'\butd\b', 'united', s)
            s = re.sub(r'\bman\b', 'manchester', s)
            s = re.sub(r'\bsg\b', 'saint germain', s)
            s = re.sub(r'\b(fc|cf|osc|rc|as|ac|ss|rb|fsv|sc|us|ogc|vfl|bvb|afc)\b', '', s)
            s = re.sub(r'[^a-z0-9]', '', s)
            return s

DB_PATH_DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "journal.db")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DB_PATH_DEFAULT
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection):
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                event_id TEXT,
                league TEXT,
                match TEXT NOT NULL,
                kickoff TEXT,
                selection TEXT NOT NULL,
                prob_fair REAL NOT NULL,
                odds_offered REAL NOT NULL,
                bookmaker TEXT NOT NULL,
                sharp_ref TEXT,
                sharp_margin REAL,
                ev REAL NOT NULL,
                kelly_stake_pct REAL DEFAULT 0.0,
                closing_odds REAL,
                clv REAL,
                settled_result TEXT,
                pnl REAL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_recs_batch ON recommendations(batch_id);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_recs_match ON recommendations(match, selection);
        """)


def log_recommendations(rows: List[Dict[str, Any]], batch_id: Optional[str] = None, db_path: Optional[str] = None) -> int:
    """Enregistre un lot de sélections dans le journal."""
    if not rows:
        return 0
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    bid = batch_id or f"batch_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    conn = get_connection(db_path)
    inserted = 0
    try:
        with conn:
            for r in rows:
                if str(r.get("book") or "") == "Score Officiel":
                    continue
                if r.get("status") == "FINISHED":
                    # Si le match est terminé, on met à jour le résultat dans le journal au lieu de dupliquer
                    conn.execute("""
                        UPDATE recommendations
                        SET settled_result = ?
                        WHERE match = ? AND selection = ? AND settled_result IS NULL
                    """, (r.get("outcome"), str(r.get("match") or ""), str(r.get("sel") or "")))
                    continue
                conn.execute("""
                    INSERT INTO recommendations (
                        batch_id, event_id, league, match, kickoff, selection,
                        prob_fair, odds_offered, bookmaker, sharp_ref, sharp_margin,
                        ev, kelly_stake_pct, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    bid,
                    str(r.get("event_id") or ""),
                    str(r.get("league") or ""),
                    str(r.get("match") or ""),
                    str(r.get("kickoff") or ""),
                    str(r.get("sel") or ""),
                    float(r.get("prob") or 0.0),
                    float(r.get("price") or 0.0),
                    str(r.get("book") or ""),
                    str(r.get("sharp") or ""),
                    float(r.get("sharp_margin") or 0.0),
                    float(r.get("ev") or 0.0),
                    float(r.get("kelly_quarter") or 0.0),
                    now
                ))
                inserted += 1
    finally:
        conn.close()
    return inserted


def get_prematch_by_pair(db_path: Optional[str] = None) -> Dict[tuple, Dict[str, Dict[str, Any]]]:
    """
    Retourne les dernières évaluations pré-match authentiques enregistrées dans le journal,
    indexées par (norm_home, norm_away) et par sélection.
    Ignore strictement les pseudos-cotes 'Score Officiel'.
    """
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute("""
                SELECT match, kickoff, selection, prob_fair, odds_offered, bookmaker,
                       sharp_ref, sharp_margin, ev, kelly_stake_pct, league, event_id, created_at
                FROM recommendations
                WHERE bookmaker != 'Score Officiel'
                ORDER BY id DESC
            """)
            recs = cursor.fetchall()
            result: Dict[tuple, Dict[str, Dict[str, Any]]] = {}
            for r in recs:
                m = r["match"] or ""
                parts = m.split(" - ")
                if len(parts) >= 2:
                    h = norm_team_key(parts[0])
                    a = norm_team_key(parts[1])
                    pair = (h, a)
                    if pair not in result:
                        result[pair] = {}
                    sel = r["selection"]
                    if sel not in result[pair]:
                        result[pair][sel] = dict(r)
            return result
    finally:
        conn.close()


def update_closing_odds(match: str, selection: str, closing_odds: float, db_path: Optional[str] = None) -> int:
    """
    Met à jour la cote de clôture et calcule le CLV :
    CLV = (cote_prise / cote_cloture) - 1.0
    """
    if closing_odds <= 1.0:
        return 0
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute("""
                SELECT id, odds_offered FROM recommendations
                WHERE match = ? AND selection = ? AND closing_odds IS NULL
            """, (match, selection))
            records = cursor.fetchall()
            for rec in records:
                taken = rec["odds_offered"]
                clv = (taken / closing_odds) - 1.0
                conn.execute("""
                    UPDATE recommendations
                    SET closing_odds = ?, clv = ?
                    WHERE id = ?
                """, (closing_odds, clv, rec["id"]))
            return len(records)
    finally:
        conn.close()


def get_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Calcule des statistiques globales sur le journal."""
    conn = get_connection(db_path)
    try:
        with conn:
            total = conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
            if total == 0:
                return {
                    "total_signals": 0,
                    "positive_ev_count": 0,
                    "negative_ev_count": 0,
                    "avg_ev": 0.0,
                    "avg_prob": 0.0,
                    "avg_clv": None,
                    "clv_tracked_count": 0
                }
            pos_ev = conn.execute("SELECT COUNT(*) FROM recommendations WHERE ev > 0").fetchone()[0]
            avg_ev = conn.execute("SELECT AVG(ev) FROM recommendations").fetchone()[0] or 0.0
            avg_prob = conn.execute("SELECT AVG(prob_fair) FROM recommendations").fetchone()[0] or 0.0
            clv_data = conn.execute("SELECT COUNT(*), AVG(clv) FROM recommendations WHERE clv IS NOT NULL").fetchone()
            clv_count = clv_data[0]
            avg_clv = clv_data[1] if clv_count > 0 else None

            return {
                "total_signals": total,
                "positive_ev_count": pos_ev,
                "negative_ev_count": total - pos_ev,
                "avg_ev": round(avg_ev, 4),
                "avg_prob": round(avg_prob, 4),
                "avg_clv": round(avg_clv, 4) if avg_clv is not None else None,
                "clv_tracked_count": clv_count
            }
    finally:
        conn.close()


def get_recent_recommendations(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute("""
                SELECT * FROM recommendations
                ORDER BY id DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "stats":
        print(json.dumps(get_stats(), indent=2))
    elif cmd == "list":
        for r in get_recent_recommendations(20):
            print(f"[{r['created_at'][:19]}] {r['match']} | {r['selection']} @ {r['odds_offered']} ({r['bookmaker']}) | Chance: {r['prob_fair']:.1%} | EV: {r['ev']:+.1%}")
