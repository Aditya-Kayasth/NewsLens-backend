# models.py
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import ARRAY

# Initialize SQLAlchemy
db = SQLAlchemy()

# Define the User model
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(100), nullable=True)
    
    # Use PostgreSQL's ARRAY type to store the list of strings
    preferred_domains = db.Column(ARRAY(db.String))

    def __init__(self, name, email, password, location, preferred_domains=None):
        self.name = name
        self.email = email
        self.password = password
        self.location = location
        self.preferred_domains = preferred_domains if preferred_domains is not None else []

    def as_dict(self):
       """Helper to return user data as a dict"""
       return {
           "name": self.name,
           "email": self.email,
           "preferred_domains": self.preferred_domains or []
       }