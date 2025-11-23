#!/usr/bin/env python3
"""
Simple CLI Gym MVP for Master:
- store user 1RMs
- generate 5-day split with suggested loads
- simple deadlift rebuild progression integrated
- log workouts (append-only)
"""

import sqlite3
import os
from datetime import date, datetime, timedelta
import math

DB = "gym.db"

# ----------------------
# Helpers
# ----------------------
def round_plate(x, plate=1.25):
    # round to nearest plate increment
    return round(x / plate) * plate

def pct(orm, p):
    return round_plate(orm * p)

# ----------------------
# DB init
# ----------------------
def init_db():
    create = not os.path.exists(DB)
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    if create:
        cur.executescript("""
        CREATE TABLE user_stats (
            id INTEGER PRIMARY KEY,
            name TEXT,
            bodyweight REAL,
            bench_1rm REAL,
            deadlift_1rm REAL,
            squat_1rm REAL,
            last_updated TEXT
        );
        CREATE TABLE workouts (
            id INTEGER PRIMARY KEY,
            wdate TEXT,
            program_day TEXT
        );
        CREATE TABLE sets (
            id INTEGER PRIMARY KEY,
            workout_id INTEGER,
            exercise TEXT,
            weight REAL,
            reps INTEGER,
            note TEXT
        );
        """)
        # insert a default user (edit later)
        cur.execute("INSERT INTO user_stats (name, bodyweight, bench_1rm, deadlift_1rm, squat_1rm, last_updated) VALUES (?, ?, ?, ?, ?, ?)",
                    ("Master", 60.5, 55.0, 120.0, 90.0, datetime.utcnow().isoformat()))
        conn.commit()
    return conn

# ----------------------
# Program generator
# ----------------------
SPLIT = [
    ("Day 1 - Push (Heavy Chest)", [
        ("Bench Press (wide grip) - heavy", lambda s: ("5x3-5", pct(s['bench_1rm'], 0.82))),
        ("Incline DB Press", lambda s: ("4x8", 16.0)),  # user target as starting DB
        ("Weighted Dips", lambda s: ("3x5-8", None)),
        ("Machine Chest Press", lambda s: ("3x10", None)),
        ("Cable Flyes", lambda s: ("3x12", None)),
        ("Light Tricep Pushdown", lambda s: ("2x15", 20.0)),
    ]),
    ("Day 2 - Pull (Strength + Deadlift rebuild)", [
        # Deadlift progression depends on 'week' number which we pass; handled in generator
        ("Deadlift (conventional) - phased", None),
        ("Bent Over Row", lambda s: ("4x6", pct(s['deadlift_1rm'], 0.45))),
        ("Weighted Pull-Ups", lambda s: ("4x5", None)),
        ("Lat Pulldown", lambda s: ("3x8", None)),
        ("Cable Row", lambda s: ("3x10", None)),
        ("Face Pulls", lambda s: ("3x15", None)),
        ("Hammer Curls", lambda s: ("3x10", 16.0)),
    ]),
    ("Day 3 - Legs (Power)", [
        ("Squat", lambda s: ("5x5", pct(s['squat_1m'], 0.75) if 'squat_1m' in s else pct(s.get('squat_1rm',90), 0.75))),
        ("Leg Press", lambda s: ("4x10", 95.0)),
        ("RDL (light)", lambda s: ("3x8-10", pct(s['deadlift_1m'] if 'deadlift_1m' in s else s['deadlift_1rm'], 0.35))),
        ("Leg Extension", lambda s: ("3x12", None)),
        ("Hamstring Curl", lambda s: ("3x12", None)),
        ("Calves", lambda s: ("3x15-20", None)),
    ]),
    ("Day 4 - Push (Volume)", [
        ("Bench Press - volume", lambda s: ("4x8", pct(s['bench_1rm'], 0.62))),
        ("Incline Smith Press", lambda s: ("4x10", None)),
        ("Chest Dips (bw)", lambda s: ("3x10-12", None)),
        ("Lateral Raises", lambda s: ("4x15", None)),
        ("Overhead Press", lambda s: ("3x6", pct(s['bench_1rm'], 0.4))),
        ("High-Low Cable Flyes", lambda s: ("3x12", None)),
        ("Rope Tricep Ext", lambda s: ("3x12", None)),
    ]),
    ("Day 5 - Pull (Volume)", [
        ("Pull-Ups (strict)", lambda s: ("3x8", None)),
        ("Seated Row", lambda s: ("4x12", None)),
        ("Single Arm Lat Pulldown", lambda s: ("3x10", None)),
        ("Chest-Supported DB Row", lambda s: ("3x12", None)),
        ("Rear Delt Machine", lambda s: ("3x15", None)),
        ("Barbell Curls", lambda s: ("3x10", None)),
        ("Concentration Curls", lambda s: ("2x12", None)),
    ]),
]

def get_user_stats(conn):
    cur = conn.cursor()
    cur.execute("SELECT name, bodyweight, bench_1rm, deadlift_1rm, squat_1rm FROM user_stats LIMIT 1")
    row = cur.fetchone()
    return {'name': row[0], 'bodyweight': row[1], 'bench_1rm': row[2], 'deadlift_1rm': row[3], 'squat_1rm': row[4]}

def deadlift_week_weight(week, s):
    # simple mapping from our plan (week 1..8)
    base = s['deadlift_1rm']
    if week <= 1:
        return ("RDL 3x10", round_plate(base*0.25))
    if week == 2:
        return ("DL 4x5 light", round_plate(base*0.35))
    if week == 3:
        return ("DL 3x3", round_plate(base*0.55))
    if week == 4:
        return ("DL 3x2", round_plate(base*0.75))
    if week == 5:
        return ("DL 3x3 heavier", round_plate(base*0.65))
    if week == 6:
        return ("DL 3x2 heavier", round_plate(base*0.8))
    if week >= 7:
        return ("DL 1-3RM test day (controlled)", round_plate(base*0.9))

def generate_week(conn, week=1):
    s = get_user_stats(conn)
    print(f"\nPROGRAM WEEK {week} — User: {s['name']} (bw {s['bodyweight']}kg)")
    for day_title, exercises in SPLIT:
        print(f"\n{day_title}")
        for ex in exercises:
            if ex[0].startswith("Deadlift"):
                label, w = deadlift_week_weight(week, s)
                print(f"  - {label} @ {w} kg")
            else:
                fn = ex[1]
                if fn is None:
                    print(f"  - {ex[0]} — programmer left placeholder")
                else:
                    reps, w = fn(s)
                    if w:
                        print(f"  - {ex[0]} — {reps} @ {w} kg")
                    else:
                        print(f"  - {ex[0]} — {reps}")

# ----------------------
# Logging workout
# ----------------------
def log_set(conn, workout_date, program_day, exercise, weight, reps, note=""):
    cur = conn.cursor()
    cur.execute("INSERT INTO workouts (wdate, program_day) VALUES (?, ?)", (workout_date, program_day))
    wid = cur.lastrowid
    cur.execute("INSERT INTO sets (workout_id, exercise, weight, reps, note) VALUES (?, ?, ?, ?, ?)",
                (wid, exercise, weight, reps, note))
    conn.commit()
    print(f"Logged workout {workout_date} / {program_day} : {exercise} {weight}x{reps}")

# ----------------------
# CLI
# ----------------------
def main():
    conn = init_db()
    print("=== MASTER: GYM MVP ===")
    while True:
        print("\nOptions:")
        print("1) Show Week Plan (default week 1)")
        print("2) Show specific week (1-8)")
        print("3) Quick log set")
        print("4) Exit")
        choice = input("> ").strip()
        if choice == "1":
            generate_week(conn, week=1)
        elif choice == "2":
            wk = int(input("Week #: ").strip() or "1")
            generate_week(conn, week=wk)
        elif choice == "3":
            d = input("Date (YYYY-MM-DD) [today]: ").strip() or date.today().isoformat()
            day = input("Program day (e.g. Day 1 - Push): ").strip()
            ex = input("Exercise: ").strip()
            w = float(input("Weight (kg): ").strip())
            r = int(input("Reps: ").strip())
            note = input("note: ").strip()
            log_set(conn, d, day, ex, w, r, note)
        elif choice == "4":
            print("Later, warrior.")
            break
        else:
            print("Pick 1-4.")

if __name__ == "__main__":
    main()
