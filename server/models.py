"""Database models for the Results Portal."""
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # patient | lab | doctor


# class Case(db.Model):
#     """One visit: lab results + doctor conclusion + prescriptions."""
#     __tablename__ = "cases"
#     id = db.Column(db.Integer, primary_key=True)
#     patient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
#     created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
#     reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
#     status = db.Column(db.String(20), nullable=False, default="lab_completed")
#     critical = db.Column(db.Boolean, nullable=False, default=False)
#     conclusion = db.Column(db.Text)
#     created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
#     released_at = db.Column(db.DateTime(timezone=True))
#     patient = db.relationship("User", foreign_keys=[patient_id])
#     results = db.relationship("LabResult", backref="case", cascade="all, delete-orphan")
#     prescriptions = db.relationship("Prescription", backref="case", cascade="all, delete-orphan")


# class LabResult(db.Model):
#     __tablename__ = "lab_results"
#     id = db.Column(db.Integer, primary_key=True)
#     case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False)
#     test_name = db.Column(db.String(80), nullable=False)
#     value = db.Column(db.Float, nullable=False)
#     unit = db.Column(db.String(20), nullable=False)
#     ref_low = db.Column(db.Float, nullable=False)
#     ref_high = db.Column(db.Float, nullable=False)
#     flag = db.Column(db.String(10), nullable=False)  # normal | low | high | critical


# class Prescription(db.Model):
#     __tablename__ = "prescriptions"
#     id = db.Column(db.Integer, primary_key=True)
#     case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False)
#     drug_name = db.Column(db.String(80), nullable=False)
#     dosage = db.Column(db.String(80), nullable=False)
#     instructions = db.Column(db.String(255), nullable=False)

