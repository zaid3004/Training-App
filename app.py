#!/usr/bin/env python3
"""
FILE: app.py
Gym Tracker Web App - Flask Backend
Run: python app.py
Access: http://localhost:5000 (or your local IP:5000 for phone access)
"""

from flask import Flask, render_template, request, jsonify
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
DB = "gym.db"

# ----------------------
# Helpers
# ----------------------
def round_plate(x, plate=1.25):
    return round(x / plate) * plate

def pct(orm, p):
    return round_plate(orm * p)

# ----------------------
# DB init
# ----------------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

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
        CREATE TABLE travel_days (
            id INTEGER PRIMARY KEY,
            day_date TEXT UNIQUE,
            reason TEXT
        );
        """)
        cur.execute("INSERT INTO user_stats (name, bodyweight, bench_1rm, deadlift_1rm, squat_1rm, last_updated) VALUES (?, ?, ?, ?, ?, ?)",
                    ("Master", 60.5, 55.0, 120.0, 90.0, datetime.utcnow().isoformat()))
        conn.commit()
    conn.close()

# ----------------------
# Program generator
# ----------------------
SPLIT = [
    ("Day 1 - Push (Heavy Chest)", [
        ("Bench Press (wide grip) - heavy", lambda s: ("5x3-5", pct(s['bench_1rm'], 0.82))),
        ("Incline DB Press", lambda s: ("4x8", 16.0)),
        ("Weighted Dips", lambda s: ("3x5-8", None)),
        ("Machine Chest Press", lambda s: ("3x10", None)),
        ("Cable Flyes", lambda s: ("3x12", None)),
        ("Light Tricep Pushdown", lambda s: ("2x15", 20.0)),
    ]),
    ("Day 2 - Pull (Strength + Deadlift rebuild)", [
        ("Deadlift (conventional) - phased", None),
        ("Bent Over Row", lambda s: ("4x6", pct(s['deadlift_1rm'], 0.45))),
        ("Weighted Pull-Ups", lambda s: ("4x5", None)),
        ("Lat Pulldown", lambda s: ("3x8", None)),
        ("Cable Row", lambda s: ("3x10", None)),
        ("Face Pulls", lambda s: ("3x15", None)),
        ("Hammer Curls", lambda s: ("3x10", 16.0)),
    ]),
    ("Day 3 - Legs (Power)", [
        ("Squat", lambda s: ("5x5", pct(s['squat_1rm'], 0.75))),
        ("Leg Press", lambda s: ("4x10", 95.0)),
        ("RDL (light)", lambda s: ("3x8-10", pct(s['deadlift_1rm'], 0.35))),
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

def get_user_stats():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name, bodyweight, bench_1rm, deadlift_1rm, squat_1rm FROM user_stats LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return {'name': row[0], 'bodyweight': row[1], 'bench_1rm': row[2], 'deadlift_1rm': row[3], 'squat_1rm': row[4]}

def deadlift_week_weight(week, s):
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
        return ("DL 1-3RM test day", round_plate(base*0.9))

def generate_week_data(week=1):
    s = get_user_stats()
    week_plan = []
    for day_title, exercises in SPLIT:
        day_exercises = []
        for ex in exercises:
            if ex[0].startswith("Deadlift"):
                label, w = deadlift_week_weight(week, s)
                day_exercises.append({'name': label, 'sets': '', 'weight': w})
            else:
                fn = ex[1]
                if fn is None:
                    day_exercises.append({'name': ex[0], 'sets': '—', 'weight': None})
                else:
                    reps, w = fn(s)
                    day_exercises.append({'name': ex[0], 'sets': reps, 'weight': w})
        week_plan.append({'title': day_title, 'exercises': day_exercises})
    return {'week': week, 'user': s, 'days': week_plan}

# ----------------------
# Routes
# ----------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats')
def api_stats():
    return jsonify(get_user_stats())

@app.route('/api/update_stats', methods=['POST'])
def api_update_stats():
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""UPDATE user_stats SET 
                   name=?, bodyweight=?, bench_1rm=?, deadlift_1rm=?, squat_1rm=?, last_updated=?
                   WHERE id=1""",
                (data['name'], data['bodyweight'], data['bench_1rm'], 
                 data['deadlift_1rm'], data['squat_1rm'], datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/week/<int:week>')
def api_week(week):
    return jsonify(generate_week_data(week))

@app.route('/api/log_set', methods=['POST'])
def api_log_set():
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO workouts (wdate, program_day) VALUES (?, ?)", 
                (data['date'], data['program_day']))
    wid = cur.lastrowid
    cur.execute("INSERT INTO sets (workout_id, exercise, weight, reps, note) VALUES (?, ?, ?, ?, ?)",
                (wid, data['exercise'], data['weight'], data['reps'], data.get('note', '')))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/workout_history')
def api_workout_history():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""SELECT w.wdate, w.program_day, s.exercise, s.weight, s.reps, s.note 
                   FROM workouts w JOIN sets s ON w.id = s.workout_id 
                   ORDER BY w.wdate DESC LIMIT 50""")
    rows = cur.fetchall()
    conn.close()
    history = [{'date': r[0], 'day': r[1], 'exercise': r[2], 
                'weight': r[3], 'reps': r[4], 'note': r[5]} for r in rows]
    return jsonify(history)

@app.route('/api/travel_days')
def api_travel_days():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT day_date, reason FROM travel_days ORDER BY day_date")
    rows = cur.fetchall()
    conn.close()
    return jsonify([{'date': r[0], 'reason': r[1]} for r in rows])

@app.route('/api/add_travel_day', methods=['POST'])
def api_add_travel_day():
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO travel_days (day_date, reason) VALUES (?, ?)",
                    (data['date'], data['reason']))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return jsonify({'success': success})

@app.route('/api/delete_travel_day', methods=['POST'])
def api_delete_travel_day():
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM travel_days WHERE day_date=?", (data['date'],))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    init_db()
    # Change host to '0.0.0.0' to access from phone on same network
    app.run(host='0.0.0.0', port=8080, debug=True)