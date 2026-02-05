from flask import Flask, request, jsonify, send_from_directory
import sqlite3
from datetime import datetime
import os

app = Flask(__name__, static_folder='.', static_url_path='')

# Database path
DB_PATH = 'disaster_relief.db'

def get_db_connection():
    """Create a connection to the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Serve static files
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

@app.route('/api/register-volunteer', methods=['POST'])
def register_volunteer():
    """Handle volunteer registration"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['username', 'password', 'fname', 'lname', 'email', 'phone']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO volunteer (username, password, first_name, last_name, email, phone, skills, availability, bio)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['username'],
            data['password'],
            data['fname'],
            data['lname'],
            data['email'],
            data['phone'],
            data.get('skills', ''),
            data.get('availability', ''),
            data.get('bio', '')
        ))
        
        conn.commit()
        volunteer_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Volunteer registered successfully',
            'id': volunteer_id
        }), 201
    
    except sqlite3.IntegrityError as e:
        if 'username' in str(e):
            return jsonify({
                'success': False,
                'message': 'Username already exists'
            }), 400
        elif 'email' in str(e):
            return jsonify({
                'success': False,
                'message': 'Email already exists'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/register-taluk', methods=['POST'])
def register_taluk():
    """Handle taluk registration"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['username', 'password', 'talukName', 'population', 'elevation']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO taluk (username, password, name, population, elevation)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            data['username'],
            data['password'],
            data['talukName'],
            int(data['population']),
            float(data['elevation'])
        ))
        
        conn.commit()
        taluk_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Taluk registered successfully',
            'id': taluk_id
        }), 201
    
    except sqlite3.IntegrityError as e:
        if 'username' in str(e):
            return jsonify({
                'success': False,
                'message': 'Username already exists'
            }), 400
        elif 'name' in str(e):
            return jsonify({
                'success': False,
                'message': 'Taluk name already exists'
            }), 400
    except ValueError:
        return jsonify({
            'success': False,
            'message': 'Invalid population or elevation value'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/login', methods=['POST'])
def login():
    """Handle login for both volunteer and taluk"""
    try:
        data = request.get_json()
        
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        user_type = data.get('user_type', '').strip()
        
        if not all([username, password, user_type]):
            return jsonify({'success': False, 'message': 'Missing credentials'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            if user_type == 'volunteer':
                cursor.execute('SELECT id, username, password FROM volunteer WHERE username = ?', (username,))
            elif user_type == 'taluk':
                cursor.execute('SELECT id, username, password FROM taluk WHERE username = ?', (username,))
            else:
                return jsonify({'success': False, 'message': 'Invalid user type'}), 400
            
            user = cursor.fetchone()
            
            if user is None:
                conn.close()
                return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
            
            # Convert row to dict for easier access
            user_dict = dict(user)
            stored_password = user_dict.get('password', '')
            
            # Check password
            if stored_password.strip() != password:
                conn.close()
                return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
            
            conn.close()
            return jsonify({
                'success': True,
                'id': user_dict['id'],
                'message': 'Login successful'
            }), 200
        except Exception as db_error:
            conn.close()
            raise db_error
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/volunteers', methods=['GET'])
def get_volunteers():
    """Get all volunteers"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM volunteer')
        volunteers = cursor.fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': [dict(v) for v in volunteers]
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/taluks', methods=['GET'])
def get_taluks():
    """Get all taluks"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM taluk')
        taluks = cursor.fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': [dict(t) for t in taluks]
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/volunteer/<int:volunteer_id>', methods=['GET'])
def get_volunteer(volunteer_id):
    """Get a specific volunteer by ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM volunteer WHERE id = ?', (volunteer_id,))
        volunteer = cursor.fetchone()
        conn.close()
        
        if volunteer is None:
            return jsonify({
                'success': False,
                'message': 'Volunteer not found'
            }), 404
        
        return jsonify({
            'success': True,
            'data': dict(volunteer)
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/taluk/<int:taluk_id>', methods=['GET'])
def get_taluk(taluk_id):
    """Get a specific taluk by ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM taluk WHERE id = ?', (taluk_id,))
        taluk = cursor.fetchone()
        conn.close()
        
        if taluk is None:
            return jsonify({
                'success': False,
                'message': 'Taluk not found'
            }), 404
        
        return jsonify({
            'success': True,
            'data': dict(taluk)
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/volunteer/<int:volunteer_id>', methods=['DELETE'])
def delete_volunteer(volunteer_id):
    """Delete a volunteer"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM volunteer WHERE id = ?', (volunteer_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Volunteer not found'
            }), 404
        
        conn.close()
        return jsonify({
            'success': True,
            'message': 'Volunteer deleted successfully'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/taluk/<int:taluk_id>', methods=['DELETE'])
def delete_taluk(taluk_id):
    """Delete a taluk"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM taluk WHERE id = ?', (taluk_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Taluk not found'
            }), 404
        
        conn.close()
        return jsonify({
            'success': True,
            'message': 'Taluk deleted successfully'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

if __name__ == '__main__':
    # Check if database exists, if not create it
    if not os.path.exists(DB_PATH):
        print("Database not found. Please run create_db.py first.")
    
    app.run(debug=True, port=5000)
