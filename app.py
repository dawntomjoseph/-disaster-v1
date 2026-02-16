from flask import Flask, jsonify, request, redirect
from utils.db import get_db, init_db
import os

app = Flask(__name__, static_folder='.', static_url_path='')


def sanitize_account(row_dict):
    if not row_dict:
        return row_dict
    row_dict.pop('password', None)
    return row_dict


@app.route('/')
def index():
    return redirect('/homepage/index.html')


@app.route('/init_db')
def initdb_route():
    init_db()
    return 'Database initialized', 200


@app.route('/api/taluk')
def get_taluk():
    name = request.args.get('name')
    conn = get_db()
    cur = conn.cursor()

    if not name:
        # return all taluks
        cur.execute('SELECT * FROM taluk')
        rows = cur.fetchall()
        taluks = [dict(r) for r in rows]
        return jsonify({'taluks': taluks})

    cur.execute('SELECT * FROM taluk WHERE name = ?', (name,))
    taluk = cur.fetchone()
    if not taluk:
        return jsonify({'error': 'Taluk not found'}), 404

    taluk = sanitize_account(dict(taluk))

    # contact
    cur.execute('SELECT * FROM taluk_contact WHERE taluk_id = ?', (taluk['id'],))
    contact = cur.fetchone()
    taluk['contact'] = dict(contact) if contact else None

    # volunteers
    cur.execute('SELECT * FROM volunteers WHERE taluk_id = ?', (taluk['id'],))
    taluk['volunteers'] = [dict(r) for r in cur.fetchall()]

    # resources
    cur.execute('SELECT * FROM resources WHERE taluk_id = ?', (taluk['id'],))
    taluk['resources'] = [dict(r) for r in cur.fetchall()]

    return jsonify({'taluk': taluk})



@app.route('/api/taluk/register', methods=['POST'])
def register_taluk():
    data = request.get_json() or {}
    name = data.get('name')
    username = data.get('username')
    password = data.get('password')
    district = data.get('district')
    population = data.get('population')
    elevation = data.get('elevation')

    if not name or not username or not password:
        return jsonify({'error': 'Missing name/username/password'}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute('SELECT id FROM taluk WHERE username = ?', (username,))
    if cur.fetchone():
        return jsonify({'error': 'Username already exists'}), 409

    cur.execute('INSERT INTO taluk(name, district, population, username, password, elevation) VALUES(?,?,?,?,?,?)',
                (name, district, population, username, password, elevation))
    conn.commit()

    cur.execute('SELECT * FROM taluk WHERE username = ?', (username,))
    taluk = cur.fetchone()
    return jsonify({'taluk': sanitize_account(dict(taluk))})


@app.route('/api/taluk/login', methods=['POST'])
def login_taluk():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Missing username/password'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM taluk WHERE username = ? AND password = ?', (username, password))
    taluk = cur.fetchone()
    if not taluk:
        return jsonify({'error': 'Invalid credentials'}), 401

    return jsonify({'taluk': sanitize_account(dict(taluk))})


@app.route('/api/taluk/contact', methods=['POST'])
def save_contact():
    data = request.get_json() or {}
    name = data.get('name')
    officer_name = data.get('officerName')
    phone = data.get('phone')
    email = data.get('email')

    if not name:
        return jsonify({'error': 'Missing taluk name'}), 400

    conn = get_db()
    cur = conn.cursor()

    # ensure taluk exists
    cur.execute('INSERT OR IGNORE INTO taluk(name) VALUES(?)', (name,))
    conn.commit()
    cur.execute('SELECT id FROM taluk WHERE name = ?', (name,))
    taluk_id = cur.fetchone()['id']

    # upsert contact (taluk_id UNIQUE)
    cur.execute('INSERT OR REPLACE INTO taluk_contact(id, taluk_id, officer_name, phone, email) VALUES((SELECT id FROM taluk_contact WHERE taluk_id = ?), ?, ?, ?, ?)',
                (taluk_id, taluk_id, officer_name, phone, email))
    conn.commit()

    return jsonify({'status': 'ok'})


@app.route('/api/db')
def dump_db():
    conn = get_db()
    cur = conn.cursor()
    out = {}
    for tbl in ['taluk', 'taluk_contact', 'resources', 'volunteers', 'rainfall_history']:
        try:
            cur.execute(f'SELECT * FROM {tbl}')
            out[tbl] = [dict(r) for r in cur.fetchall()]
        except Exception:
            out[tbl] = []

    return jsonify(out)


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

    taluk_id = row['id']
    cur.execute('SELECT * FROM resources WHERE taluk_id = ?', (taluk_id,))
    res = cur.fetchone()
    if not res:
        return jsonify({'resources': None})

    return jsonify({'resources': dict(res)})


@app.route('/api/resources', methods=['POST'])
def upsert_resources():
    data = request.get_json() or {}
    taluk_name = data.get('talukName')
    boats = data.get('boats')
    rescue_vehicles = data.get('rescueVehicles')
    relief_camps = data.get('reliefCamps')
    if not taluk_name:
        return jsonify({'error': 'Missing talukName'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT id FROM taluk WHERE name = ?', (taluk_name,))
    row = cur.fetchone()
    if not row:
        return jsonify({'error': 'Taluk not found'}), 404

    taluk_id = row['id']

    cur.execute('SELECT id FROM resources WHERE taluk_id = ?', (taluk_id,))
    existing = cur.fetchone()
    if existing:
        cur.execute('UPDATE resources SET boats = ?, rescue_vehicles = ?, relief_camps = ? WHERE taluk_id = ?',
                    (boats, rescue_vehicles, relief_camps, taluk_id))
    else:
        cur.execute('INSERT INTO resources(taluk_id, boats, rescue_vehicles, relief_camps) VALUES(?,?,?,?)',
                    (taluk_id, boats, rescue_vehicles, relief_camps))

    conn.commit()
    cur.execute('SELECT * FROM resources WHERE taluk_id = ?', (taluk_id,))
    res = cur.fetchone()
    return jsonify({'resources': dict(res)})


@app.route('/api/volunteer/register', methods=['POST'])
def register_volunteer():
    data = request.get_json() or {}
    first_name = data.get('firstName')
    last_name = data.get('lastName')
    phone = data.get('phone')
    availability = data.get('availability')
    username = data.get('username')
    password = data.get('password')

    if not first_name or not last_name or not username or not password:
        return jsonify({'error': 'Missing required fields'}), 400

    name = f"{first_name} {last_name}".strip()

    conn = get_db()
    cur = conn.cursor()

    cur.execute('SELECT id FROM volunteers WHERE username = ?', (username,))
    if cur.fetchone():
        return jsonify({'error': 'Username already exists'}), 409

    cur.execute('INSERT INTO volunteers(name, phone, username, password, taluk_id, availability) VALUES(?,?,?,?,?,?)',
                (name, phone, username, password, None, availability))
    conn.commit()

    cur.execute('SELECT * FROM volunteers WHERE username = ?', (username,))
    vol = cur.fetchone()
    return jsonify({'volunteer': sanitize_account(dict(vol))})


@app.route('/api/volunteer/login', methods=['POST'])
def login_volunteer():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Missing username/password'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM volunteers WHERE username = ? AND password = ?', (username, password))
    vol = cur.fetchone()
    if not vol:
        return jsonify({'error': 'Invalid credentials'}), 401

    return jsonify({'volunteer': sanitize_account(dict(vol))})


if __name__ == '__main__':
    # initialize/upgrade DB schema on startup
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
