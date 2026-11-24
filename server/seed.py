"""Create tables and load SYNTHETIC demo data. Use --reset to wipe and reseed."""
import sys

from werkzeug.security import generate_password_hash

from server.app import app, flag_for
from server.models import Case, LabResult, Prescription, User, db, utcnow

ACCOUNTS = [
    ("patient1", "Patient123!", "patient", "Alice Uwase"),
    ("patient2", "Patient456!", "patient", "Eric Mugisha"),
    ("lab1", "LabTech123!", "lab", "Jane Lab Technician"),
    ("doctor1", "Doctor123!", "doctor", "Dr. Paul Habimana"),
]

# patient, tests (name, value, unit, ref_low, ref_high, crit_low, crit_high), conclusion, meds
CASES = [
    ("patient1", [("Hemoglobin", 13.5, "g/dL", 12, 16, 7, 20),
                  ("White cells", 6.2, "x10^9/L", 4, 11, 2, 30)], None, []),
    ("patient1", [("Fasting glucose", 7.9, "mmol/L", 3.9, 5.5, 2.5, 25)],
     "Elevated blood glucose. Diet changes and medication started; recheck in 4 weeks.",
     [("Metformin", "500 mg twice daily", "Take with meals")]),
    ("patient2", [("Potassium", 6.9, "mmol/L", 3.5, 5.0, 2.5, 6.5)], None, []),
    ("patient2", [("Total cholesterol", 6.2, "mmol/L", 0, 5.2, None, None)], None, []),
]


def build(users, patient, tests, conclusion, meds):
    case = Case(patient_id=users[patient].id, created_by=users["lab1"].id)
    for name, value, unit, low, high, crit_low, crit_high in tests:
        flag = flag_for(float(value), float(low), float(high), crit_low, crit_high)
        case.results.append(LabResult(test_name=name, value=value, unit=unit,
                                      ref_low=low, ref_high=high, flag=flag))
    case.critical = any(r.flag == "critical" for r in case.results)
    if all(r.flag == "normal" for r in case.results):
        case.status, case.released_at = "released", utcnow()
    if conclusion:
        case.conclusion = conclusion
        case.status, case.released_at = "released", utcnow()
        case.reviewed_by = users["doctor1"].id
    for drug, dose, note in meds:
        case.prescriptions.append(Prescription(drug_name=drug, dosage=dose, instructions=note))
    return case


# with app.app_context():
#     if "--reset" in sys.argv:
#         db.drop_all()
#     db.create_all()
#     if User.query.first():
#         print("Database already seeded. Use --reset to wipe and reseed.")
#         sys.exit(0)
#     users = {}
#     for username, password, role, full_name in ACCOUNTS:
#         users[username] = User(username=username, full_name=full_name, role=role,
#                                password_hash=generate_password_hash(password))
#         db.session.add(users[username])
#     db.session.flush()
#     for patient, tests, conclusion, meds in CASES:
#         db.session.add(build(users, patient, tests, conclusion, meds))
#     db.session.commit()
#     print("Seeded 4 accounts and 4 cases.")
