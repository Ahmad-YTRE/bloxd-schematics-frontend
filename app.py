from flask import Flask, request, jsonify, send_file, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import uuid

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-123')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

db = SQLAlchemy(app)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    schematics = db.relationship('Schematic', backref='author', lazy=True)

# Schematic Model
class Schematic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    filename = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Initialize DB
with app.app_context():
    db.create_all()

# Auth Routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    hashed_password = generate_password_hash(data['password'], method='sha256')
    new_user = User(username=data['username'], password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User created"}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data['username']).first()
    if user and check_password_hash(user.password, data['password']):
        session['user_id'] = user.id
        return jsonify({"message": "Logged in"})
    return jsonify({"error": "Invalid credentials"}), 401

# Schematic Routes
@app.route('/api/schematics', methods=['GET'])
def get_schematics():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    schematics = Schematic.query.filter_by(user_id=session['user_id']).all()
    return jsonify([{"id": s.id, "name": s.name} for s in schematics])

@app.route('/api/upload', methods=['POST'])
def upload():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    file = request.files['file']
    if not file or not file.filename.endswith('.bloxdschem'):
        return jsonify({"error": "Invalid file"}), 400
    
    filename = f"{uuid.uuid4()}.bloxdschem"
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    new_schematic = Schematic(
        name=request.form.get('name', 'Untitled'),
        filename=filename,
        user_id=session['user_id']
    )
    db.session.add(new_schematic)
    db.session.commit()
    
    return jsonify({"id": new_schematic.id, "name": new_schematic.name})

@app.route('/api/download/<int:schematic_id>', methods=['GET'])
def download(schematic_id):
    schematic = Schematic.query.get_or_404(schematic_id)
    return send_file(
        os.path.join(app.config['UPLOAD_FOLDER'], schematic.filename),
        as_attachment=True,
        download_name=f"{schematic.name}.bloxdschem"
    )

# Serve Frontend
@app.route('/')
def home():
    return app.send_static_file('index.html')

if __name__ == '__main__':
    app.run()