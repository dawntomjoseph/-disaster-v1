from flask import Flask, jsonify, request, redirect
from utils.db import get_db, init_db
from config import OPENWEATHER_API_KEY
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from datetime import datetime, timedelta, timezone
from model.predict import predict_flood as model_predict
from config import OPENWEATHER_API_KEY
import json
import os


app = Flask(__name__, static_folder='.', static_url_path='')

# ----------------- ADMIN CREDENTIALS (HARDCODED) -----------------

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"


# ----------------- HELPERS -----------------

def sanitize_account(row_dict):
    if not row_dict:
        return row_dict
    row_dict.pop('password', None)
    return row_dict


def get_openweather_api_key():
    return os.environ.get('OPENWEATHER_API_KEY', OPENWEATHER_API_KEY)


def fetch_rain_forecast(lat, lon, api_key):
    query = urlencode({
        'lat': lat,
        'lon': lon,
        'appid': api_key,
        'units': 'metric'
    })
    url = f'https://api.openweathermap.org/data/2.5/forecast?{query}'

    try:
        with urlopen(url, timeout=12) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        response_body = ''
        try:
            response_body = exc.read().decode('utf-8')
            response_json = json.loads(response_body)
            message = response_json.get('message')
            if message:
                raise Exception(f'OpenWeatherMap error {exc.code}: {message}')
        except Exception:
            pass
        raise Exception(f'OpenWeatherMap error {exc.code}: unauthorized or invalid API key')

    now = datetime.now(timezone.utc)
    next_24h = now + timedelta(hours=24)

    total_24h = 0.0
    next_slot_mm = 0.0
    next_slot_time = None

    for idx, entry in enumerate(payload.get('list', [])):
        entry_time = datetime.fromtimestamp(entry.get('dt', 0), tz=timezone.utc)
        rain_mm = float((entry.get('rain') or {}).get('3h', 0.0) or 0.0)

        if idx == 0:
            next_slot_mm = rain_mm
            next_slot_time = entry.get('dt_txt')

        if now <= entry_time <= next_24h:
            total_24h += rain_mm

    return {
        'rainfall_next_3h_mm': round(next_slot_mm, 2),
        'rainfall_next_24h_mm': round(total_24h, 2),
        'next_forecast_time': next_slot_time
    }
def store_rainfall_history(taluk_id, rainfall_mm):
    """
    Stores rainfall value into rainfall_history table
    """

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO rainfall_history (taluk_id, date, rainfall_mm)
        VALUES (?, datetime('now'), ?)
    """, (taluk_id, rainfall_mm))

    conn.commit()
def get_past_rainfall(taluk_id, hours):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT SUM(rainfall_mm) as total
        FROM rainfall_history
        WHERE taluk_id = ?
        AND datetime(date) >= datetime('now', ?)
    """, (taluk_id, f'-{hours} hours'))

    result = cur.fetchone()
    return result["total"] or 0.0

@app.route('/api/predict_flood', methods=['POST'])
def predict_flood():

    data = request.get_json() or {}
    taluk_name = data.get("taluk")

    if not taluk_name:
        return jsonify({"error": "Taluk required"}), 400

    conn = get_db()
    cur = conn.cursor()

    # -----------------------------
    # 1. Get taluk details
    # -----------------------------
    cur.execute("""
    SELECT id, latitude, longitude, elevation
    FROM taluk WHERE name=?
    """, (taluk_name,))

    row = cur.fetchone()

    if not row:
        return jsonify({"error": "Taluk not found"}), 404

    taluk_id = row["id"]
    lat = row["latitude"]
    lon = row["longitude"]
    elevation = row["elevation"] or 0

    # -----------------------------
    # 2. Fetch rainfall from API
    # -----------------------------
    weather = fetch_rain_forecast(
        lat,
        lon,
        OPENWEATHER_API_KEY
    )
    store_rainfall_history(
    taluk_id,
    weather["rainfall_next_3h_mm"]
    )

    # compute accumulated rainfall from history
    rain_today = get_past_rainfall(taluk_id, 24)
    rain_3day = get_past_rainfall(taluk_id, 72)
    rain_7day = get_past_rainfall(taluk_id, 168)

    # -----------------------------
    # 3. Call ML Model
    # -----------------------------
    prediction = model_predict(
        rain_today,
        rain_3day,
        rain_7day,
        elevation
    )
    # Get resources
    cur.execute("SELECT * FROM resources WHERE taluk_id=?", (taluk_id,))
    res = cur.fetchone()
    resources = dict(res) if res else {}

    # population already stored in taluk table
    cur.execute("SELECT population FROM taluk WHERE id=?", (taluk_id,))
    pop_row = cur.fetchone()
    population = pop_row["population"] or 0

    if prediction == 1 or prediction == "HIGH":
        risk_level = "HIGH"
    elif prediction == 0.5 or prediction == "MEDIUM":
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"
    ai_suggestions = generate_ai_suggestions(
    risk_level,
    population,
    resources
    )
    return jsonify({
    "prediction": prediction,
    "risk_level": risk_level,
    "rain_today": rain_today,
    "rain_3day": rain_3day,
    "rain_7day": rain_7day,
    "elevation": elevation,
    "ai_suggestions": ai_suggestions
    })
    """return jsonify({
        "prediction": prediction,
        "rain_today": rain_today,
        "rain_3day": rain_3day,
        "rain_7day": rain_7day,
        "elevation": elevation,
    })"""
# ----------------- RULE BASED AI -----------------

def generate_ai_suggestions(risk_level, population, resources):
    suggestions = []

    boats = resources.get("boats", 0)
    vehicles = resources.get("rescue_vehicles", 0)
    camps = resources.get("relief_camps", 0)

    # ---------- HIGH RISK ----------
    if risk_level == "HIGH":
        suggestions.append("High flood risk detected. Activate emergency response team.")

        if population > 50000 and boats < 10:
            suggestions.append("Rescue boats may be insufficient for the population.")

        if vehicles < 5:
            suggestions.append("Increase rescue vehicle readiness.")

        if camps < 3:
            suggestions.append("Prepare additional relief camps immediately.")

        suggestions.append("Send early warning notifications to residents.")
        suggestions.append("Coordinate with nearby taluks for backup resources.")

    # ---------- MEDIUM RISK ----------
    elif risk_level == "MEDIUM":
        suggestions.append("Moderate flood risk detected. Monitor rainfall continuously.")

        if boats < 5:
            suggestions.append("Keep additional rescue boats on standby.")

        suggestions.append("Check volunteer availability.")
        suggestions.append("Inspect drainage and evacuation routes.")

    # ---------- LOW RISK ----------
    else:
        suggestions.append("Conditions are safe. No immediate action required.")
        suggestions.append("Continue routine monitoring.")

    return suggestions
# ----------------- BASIC ROUTES -----------------

@app.route('/')
def index():
    return redirect('/homepage/index.html')


@app.route('/init_db')
def initdb_route():
    init_db()
    return 'Database initialized', 200

# ----------------- ADMIN API -----------------

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json() or {}

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Missing credentials'}), 400

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return jsonify({
            'status': 'success',
            'admin': {
                'username': ADMIN_USERNAME
            }
        }), 200

    return jsonify({'error': 'Invalid admin credentials'}), 401


# ----------------- TALUK APIs -----------------

@app.route('/api/taluk')
def get_taluk():
    name = request.args.get('name')
    conn = get_db()
    cur = conn.cursor()

    if not name:
        cur.execute('SELECT * FROM taluk')
        return jsonify({'taluks': [dict(r) for r in cur.fetchall()]})

    cur.execute('SELECT * FROM taluk WHERE name = ?', (name,))
    taluk = cur.fetchone()
    if not taluk:
        return jsonify({'error': 'Taluk not found'}), 404

    taluk = sanitize_account(dict(taluk))

    cur.execute('SELECT * FROM taluk_contact WHERE taluk_id = ?', (taluk['id'],))
    taluk['contact'] = dict(cur.fetchone() or {})

    cur.execute('SELECT * FROM volunteers WHERE taluk_id = ?', (taluk['id'],))
    taluk['volunteers'] = [dict(r) for r in cur.fetchall()]

    cur.execute('SELECT * FROM resources WHERE taluk_id = ?', (taluk['id'],))
    taluk['resources'] = [dict(r) for r in cur.fetchall()]

    return jsonify({'taluk': taluk})


@app.route('/api/taluk/register', methods=['POST'])
def register_taluk():
    data = request.get_json() or {}

    if not data.get('name') or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute('SELECT id FROM taluk WHERE username = ?', (data['username'],))
    if cur.fetchone():
        return jsonify({'error': 'Username already exists'}), 409

    cur.execute(
        'INSERT INTO taluk(name, district, population, username, password, elevation, latitude, longitude) VALUES(?,?,?,?,?,?,?,?)',
        (
            data['name'],
            data.get('district'),
            data.get('population'),
            data['username'],
            data['password'],
            data.get('elevation'),
            data.get('latitude'),
            data.get('longitude')
        )
    )
    conn.commit()

    cur.execute('SELECT * FROM taluk WHERE username = ?', (data['username'],))
    return jsonify({'taluk': sanitize_account(dict(cur.fetchone()))})


@app.route('/api/taluk/login', methods=['POST'])
def login_taluk():
    data = request.get_json() or {}

    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM taluk WHERE username = ? AND password = ?',
                (data.get('username'), data.get('password')))
    taluk = cur.fetchone()

    if not taluk:
        return jsonify({'error': 'Invalid credentials'}), 401

    return jsonify({'taluk': sanitize_account(dict(taluk))})


@app.route('/api/taluk/contact', methods=['POST'])
def upsert_taluk_contact():
    data = request.get_json() or {}

    taluk_name = data.get('name')
    if not taluk_name:
        return jsonify({'error': 'Missing taluk name'}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute('SELECT id FROM taluk WHERE name = ?', (taluk_name,))
    taluk = cur.fetchone()
    if not taluk:
        return jsonify({'error': 'Taluk not found'}), 404

    officer_name = data.get('officerName')
    phone = data.get('phone')
    email = data.get('email')

    cur.execute('SELECT id FROM taluk_contact WHERE taluk_id = ?', (taluk['id'],))
    existing = cur.fetchone()

    if existing:
        cur.execute(
            'UPDATE taluk_contact SET officer_name = ?, phone = ?, email = ? WHERE taluk_id = ?',
            (officer_name, phone, email, taluk['id'])
        )
    else:
        cur.execute(
            'INSERT INTO taluk_contact(taluk_id, officer_name, phone, email) VALUES(?,?,?,?)',
            (taluk['id'], officer_name, phone, email)
        )

    conn.commit()
    return jsonify({'status': 'ok'})


@app.route('/api/weather/rainfall', methods=['GET'])
def get_rainfall_forecast():
    api_key = get_openweather_api_key()
    if not api_key:
        return jsonify({'error': 'OpenWeatherMap API key is not configured'}), 500

    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT id, name, latitude, longitude FROM taluk')
    taluks = [dict(r) for r in cur.fetchall()]

    forecasts = []
    for taluk in taluks:
        lat = taluk.get('latitude')
        lon = taluk.get('longitude')

        if lat is None or lon is None:
            forecasts.append({
                'taluk_id': taluk['id'],
                'taluk_name': taluk['name'],
                'error': 'Missing latitude/longitude'
            })
            continue

        try:
            weather = fetch_rain_forecast(lat, lon, api_key)
            forecasts.append({
                'taluk_id': taluk['id'],
                'taluk_name': taluk['name'],
                'latitude': lat,
                'longitude': lon,
                **weather
            })
        except Exception as exc:
            forecasts.append({
                'taluk_id': taluk['id'],
                'taluk_name': taluk['name'],
                'latitude': lat,
                'longitude': lon,
                'error': str(exc)
            })

    return jsonify({'rainfall': forecasts})



# ----------------- RESOURCES -----------------

@app.route('/api/resources', methods=['GET'])
def get_resources():
    taluk_name = request.args.get('talukName')
    if not taluk_name:
        return jsonify({'error': 'Missing talukName'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT id FROM taluk WHERE name = ?', (taluk_name,))
    row = cur.fetchone()
    if not row:
        return jsonify({'error': 'Taluk not found'}), 404

    cur.execute('SELECT * FROM resources WHERE taluk_id = ?', (row['id'],))
    return jsonify({'resources': dict(cur.fetchone() or {})})


@app.route('/api/resources', methods=['POST'])
def upsert_resources():
    data = request.get_json() or {}
    if not data.get('talukName'):
        return jsonify({'error': 'Missing talukName'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT id FROM taluk WHERE name = ?', (data['talukName'],))
    taluk = cur.fetchone()
    if not taluk:
        return jsonify({'error': 'Taluk not found'}), 404

    cur.execute('SELECT id FROM resources WHERE taluk_id = ?', (taluk['id'],))
    if cur.fetchone():
        cur.execute(
            'UPDATE resources SET boats=?, rescue_vehicles=?, relief_camps=? WHERE taluk_id=?',
            (data.get('boats'), data.get('rescueVehicles'),
             data.get('reliefCamps'), taluk['id'])
        )
    else:
        cur.execute(
            'INSERT INTO resources(taluk_id, boats, rescue_vehicles, relief_camps) VALUES(?,?,?,?)',
            (taluk['id'], data.get('boats'),
             data.get('rescueVehicles'), data.get('reliefCamps'))
        )

    conn.commit()
    return jsonify({'status': 'updated'})


# ----------------- VOLUNTEERS -----------------

@app.route('/api/volunteer/register', methods=['POST'])
def register_volunteer():
    data = request.get_json() or {}

    if not all([data.get('firstName'), data.get('lastName'),
                data.get('username'), data.get('password')]):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute('SELECT id FROM volunteers WHERE username = ?', (data['username'],))
    if cur.fetchone():
        return jsonify({'error': 'Username already exists'}), 409

    cur.execute(
        'INSERT INTO volunteers(name, phone, username, password, taluk_id, availability) VALUES(?,?,?,?,?,?)',
        (f"{data['firstName']} {data['lastName']}",
         data.get('phone'), data['username'], data['password'],
         None, data.get('availability'))
    )
    conn.commit()

    cur.execute('SELECT * FROM volunteers WHERE username = ?', (data['username'],))
    return jsonify({'volunteer': sanitize_account(dict(cur.fetchone()))})


@app.route('/api/volunteer/login', methods=['POST'])
def login_volunteer():
    data = request.get_json() or {}

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        'SELECT * FROM volunteers WHERE username = ? AND password = ?',
        (data.get('username'), data.get('password'))
    )
    vol = cur.fetchone()

    if not vol:
        return jsonify({'error': 'Invalid credentials'}), 401

    return jsonify({'volunteer': sanitize_account(dict(vol))})


@app.route('/api/volunteer/<int:volunteer_id>')
def get_volunteer_profile(volunteer_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute('SELECT * FROM volunteers WHERE id = ?', (volunteer_id,))
    vol = cur.fetchone()
    if not vol:
        return jsonify({'error': 'Volunteer not found'}), 404

    volunteer = sanitize_account(dict(vol))

    # Duty history (safe)
    try:
        cur.execute('SELECT * FROM duty_history WHERE volunteer_id = ?', (volunteer_id,))
        volunteer['duty_history'] = [dict(r) for r in cur.fetchall()]
    except Exception:
        volunteer['duty_history'] = []

    return jsonify({'volunteer': volunteer})


# ----------------- DEBUG -----------------

@app.route('/api/db')
def dump_db():
    conn = get_db()
    cur = conn.cursor()
    tables = ['taluk', 'taluk_contact', 'resources', 'volunteers']
    out = {}

    for t in tables:
        try:
            cur.execute(f'SELECT * FROM {t}')
            out[t] = [dict(r) for r in cur.fetchall()]
        except Exception:
            out[t] = []

    return jsonify(out)


# ----------------- START -----------------

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)


from flask import Flask, jsonify, request, redirect
from utils.db import get_db, init_db
from config import OPENWEATHER_API_KEY
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from datetime import datetime, timedelta, timezone
import json
import os

app = Flask(__name__, static_folder='.', static_url_path='')

# ----------------- ADMIN CREDENTIALS (HARDCODED) -----------------

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"


# ----------------- HELPERS -----------------

def sanitize_account(row_dict):
    if not row_dict:
        return row_dict
    row_dict.pop('password', None)
    return row_dict


def get_openweather_api_key():
    return os.environ.get('OPENWEATHER_API_KEY', OPENWEATHER_API_KEY)


def fetch_rain_forecast(lat, lon, api_key):
    query = urlencode({
        'lat': lat,
        'lon': lon,
        'appid': api_key,
        'units': 'metric'
    })
    url = f'https://api.openweathermap.org/data/2.5/forecast?{query}'

    try:
        with urlopen(url, timeout=12) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        response_body = ''
        try:
            response_body = exc.read().decode('utf-8')
            response_json = json.loads(response_body)
            message = response_json.get('message')
            if message:
                raise Exception(f'OpenWeatherMap error {exc.code}: {message}')
        except Exception:
            pass
        raise Exception(f'OpenWeatherMap error {exc.code}: unauthorized or invalid API key')

    now = datetime.now(timezone.utc)
    next_24h = now + timedelta(hours=24)

    total_24h = 0.0
    next_slot_mm = 0.0
    next_slot_time = None

    for idx, entry in enumerate(payload.get('list', [])):
        entry_time = datetime.fromtimestamp(entry.get('dt', 0), tz=timezone.utc)
        rain_mm = float((entry.get('rain') or {}).get('3h', 0.0) or 0.0)

        if idx == 0:
            next_slot_mm = rain_mm
            next_slot_time = entry.get('dt_txt')

        if now <= entry_time <= next_24h:
            total_24h += rain_mm

    return {
        'rainfall_next_3h_mm': round(next_slot_mm, 2),
        'rainfall_next_24h_mm': round(total_24h, 2),
        'next_forecast_time': next_slot_time
    }


# ----------------- BASIC ROUTES -----------------

@app.route('/')
def index():
    return redirect('/homepage/index.html')


@app.route('/init_db')
def initdb_route():
    init_db()
    return 'Database initialized', 200

# ----------------- ADMIN API -----------------

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json() or {}

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Missing credentials'}), 400

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return jsonify({
            'status': 'success',
            'admin': {
                'username': ADMIN_USERNAME
            }
        }), 200

    return jsonify({'error': 'Invalid admin credentials'}), 401


# ----------------- TALUK APIs -----------------

@app.route('/api/taluk')
def get_taluk():
    name = request.args.get('name')
    conn = get_db()
    cur = conn.cursor()

    if not name:
        cur.execute('SELECT * FROM taluk')
        return jsonify({'taluks': [dict(r) for r in cur.fetchall()]})

    cur.execute('SELECT * FROM taluk WHERE name = ?', (name,))
    taluk = cur.fetchone()
    if not taluk:
        return jsonify({'error': 'Taluk not found'}), 404

    taluk = sanitize_account(dict(taluk))

    cur.execute('SELECT * FROM taluk_contact WHERE taluk_id = ?', (taluk['id'],))
    taluk['contact'] = dict(cur.fetchone() or {})

    cur.execute('SELECT * FROM volunteers WHERE taluk_id = ?', (taluk['id'],))
    taluk['volunteers'] = [dict(r) for r in cur.fetchall()]

    cur.execute('SELECT * FROM resources WHERE taluk_id = ?', (taluk['id'],))
    taluk['resources'] = [dict(r) for r in cur.fetchall()]

    return jsonify({'taluk': taluk})


@app.route('/api/taluk/register', methods=['POST'])
def register_taluk():
    data = request.get_json() or {}

    if not data.get('name') or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute('SELECT id FROM taluk WHERE username = ?', (data['username'],))
    if cur.fetchone():
        return jsonify({'error': 'Username already exists'}), 409

    cur.execute(
        'INSERT INTO taluk(name, district, population, username, password, elevation, latitude, longitude) VALUES(?,?,?,?,?,?,?,?)',
        (
            data['name'],
            data.get('district'),
            data.get('population'),
            data['username'],
            data['password'],
            data.get('elevation'),
            data.get('latitude'),
            data.get('longitude')
        )
    )
    conn.commit()
