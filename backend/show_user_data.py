from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def default_db_path() -> Path:
    here = Path(__file__).resolve().parent
    primary = here / "wellness_platform.db"
    fallback = here.parent / "wellness_platform.db"
    if primary.exists():
        return primary
    return fallback


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def find_user(conn: sqlite3.Connection, email: str | None, user_id: str | None) -> dict[str, Any] | None:
    cur = conn.cursor()
    if user_id:
        cur.execute(
            """
            SELECT id, name, email, is_active, created_at, updated_at, last_login_at
            FROM users
            WHERE id = ?
            LIMIT 1
            """,
            (user_id,),
        )
        return row_to_dict(cur.fetchone())
    if email:
        cur.execute(
            """
            SELECT id, name, email, is_active, created_at, updated_at, last_login_at
            FROM users
            WHERE lower(email) = lower(?)
            LIMIT 1
            """,
            (email,),
        )
        return row_to_dict(cur.fetchone())
    return None


def list_recent_users(conn: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, email, is_active, created_at, last_login_at
        FROM users
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return rows_to_dicts(cur.fetchall())


def query_count(conn: sqlite3.Connection, table: str, user_id: str) -> int:
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    return int(row["c"]) if row else 0


def get_user_payload(conn: sqlite3.Connection, user: dict[str, Any], limit: int) -> dict[str, Any]:
    user_id = user["id"]
    cur = conn.cursor()

    cur.execute(
        """
        SELECT age, gender, height_cm, weight_kg, bmi, food_preference, diet_pattern,
               pre_existing_conditions, fitness_goal, created_at, updated_at
        FROM profiles
        WHERE user_id = ?
        LIMIT 1
        """,
        (user_id,),
    )
    profile = row_to_dict(cur.fetchone())

    cur.execute(
        """
        SELECT log_date, sleep_hours, daily_steps, heart_rate, calories_burned,
               stress_level, water_intake, exercise_minutes, created_at, updated_at
        FROM daily_logs
        WHERE user_id = ?
        ORDER BY log_date DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    daily_logs = rows_to_dicts(cur.fetchall())

    cur.execute(
        """
        SELECT log_date, meal_type, food_name, calories, protein_g, carbs_g, fats_g, fiber_g, notes, created_at
        FROM food_logs
        WHERE user_id = ?
        ORDER BY log_date DESC, id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    food_logs = rows_to_dicts(cur.fetchall())

    cur.execute(
        """
        SELECT id, source, created_at, log_date, wellness_score, wellness_category, risk_level
        FROM predictions
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    predictions = rows_to_dicts(cur.fetchall())

    cur.execute(
        """
        SELECT token_jti, created_at, expires_at, revoked_at
        FROM user_sessions
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    sessions = rows_to_dicts(cur.fetchall())

    return {
        "user": user,
        "counts": {
            "daily_logs": query_count(conn, "daily_logs", user_id),
            "food_logs": query_count(conn, "food_logs", user_id),
            "predictions": query_count(conn, "predictions", user_id),
            "sessions": query_count(conn, "user_sessions", user_id),
        },
        "profile": profile,
        "daily_logs": daily_logs,
        "food_logs": food_logs,
        "predictions": predictions,
        "sessions": sessions,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show user data from wellness_platform.db")
    parser.add_argument("--db", type=Path, default=default_db_path(), help="Path to SQLite DB file")
    parser.add_argument("--email", type=str, default=None, help="User email")
    parser.add_argument("--user-id", type=str, default=None, help="User ID (UUID)")
    parser.add_argument("--limit", type=int, default=10, help="Rows per section (daily logs, food logs, etc.)")
    parser.add_argument(
        "--list-users",
        action="store_true",
        help="List recent users instead of loading one user's full payload",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}")

    with get_connection(args.db) as conn:
        if args.list_users or (not args.email and not args.user_id):
            payload = {"database": str(args.db), "recent_users": list_recent_users(conn, limit=max(args.limit, 1))}
            print(json.dumps(payload, indent=2, default=str))
            return

        user = find_user(conn, email=args.email, user_id=args.user_id)
        if user is None:
            lookup = f"user_id={args.user_id}" if args.user_id else f"email={args.email}"
            raise SystemExit(f"No user found for {lookup}")

        payload = {
            "database": str(args.db),
            "payload": get_user_payload(conn, user=user, limit=max(args.limit, 1)),
        }
        print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
