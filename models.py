from flask_sqlalchemy import SQLAlchemy
import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.String(80), primary_key=True)  # Unique user identifier.
    ip_address = db.Column(db.String(45))
    location_country = db.Column(db.String(80))
    location_city = db.Column(db.String(80))
    first_login = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    sessions = db.relationship('Session', backref='user', lazy=True)

class Session(db.Model):
    __tablename__ = 'sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(80), db.ForeignKey('users.user_id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    page = db.Column(db.String(120), nullable=False)
    session_time = db.Column(db.Float, nullable=False)
    referral_source = db.Column(db.String(120))
    user_agent = db.Column(db.String(200))
    feedback = db.Column(db.Text)
