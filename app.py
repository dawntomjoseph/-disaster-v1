from flask import Flask, jsonify, request, redirect
from utils.db import get_db, init_db

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
