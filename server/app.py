"""Results Portal API: JWT auth, role-based access, filtering, openFDA enrichment."""
import math
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

import jwt
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import or_
from sqlalchemy import text as sql_text
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash

from server.models import Case, LabResult, Prescription, User, db, utcnow
from server.openfda import drug_info

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = "sqlite:///" + str(BASE_DIR / "portal.db")  # absolute: same file for every launch method


def database_url():
    """Use DATABASE_URL if set, forcing the psycopg2 driver for PostgreSQL URLs."""
    url = os.getenv("DATABASE_URL") or DEFAULT_DB
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


SECRET = os.getenv("SECRET_KEY")
if not SECRET or SECRET.startswith("change-me"):
    raise SystemExit("Set a strong SECRET_KEY in .env (see .env.example)")

DISCLAIMER = (
    "Demonstration system with synthetic data. Not for emergencies: if you feel "
    "seriously unwell, go to the nearest hospital or call emergency services."
)
CRITICAL_NOTICE = "CRITICAL RESULT: contact the hospital immediately. Do not wait for an appointment."
STATUSES = ("lab_completed", "doctor_reviewed", "released")

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)  # real client IP behind the load balancer
app.config["SECRET_KEY"] = SECRET
app.config["SQLALCHEMY_DATABASE_URI"] = database_url()
db.init_app(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per hour"], storage_uri="memory://")


@app.after_request
def add_headers(resp):
    resp.headers["X-Served-By"] = os.getenv("SERVER_NAME", "local")  # proves load balancing
    resp.headers["Cache-Control"] = "no-store"
    return resp


def error(message, code):
    return jsonify({"error": message}), code


@app.errorhandler(ValueError)
def bad_input(exc):
    return error(str(exc), 400)


@app.errorhandler(404)
def not_found(_):
    return error("Not found", 404)


@app.errorhandler(405)
def not_allowed(_):
    return error("Method not allowed", 405)


@app.errorhandler(429)
def too_many(_):
    return error("Too many requests, please slow down", 429)


@app.errorhandler(500)
def server_error(_):
    return error("Internal server error", 500)


# ---------- helpers ----------
def auth_required(*roles):
    """Require a valid Bearer token, optionally restricted to given roles."""
    def wrapper(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return error("Missing token", 401)
            try:
                data = jwt.decode(header[7:], SECRET, algorithms=["HS256"])
                user = db.session.get(User, int(data["sub"]))
            except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
                return error("Invalid or expired token", 401)
            if user is None:
                return error("Invalid or expired token", 401)
            if roles and user.role not in roles:
                return error("Forbidden for your role", 403)
            g.user = user
            return fn(*args, **kwargs)
        return inner
    return wrapper


def body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def req_str(data, key, max_len):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    value = value.strip()
    if len(value) > max_len:
        raise ValueError(f"{key} is too long (max {max_len} characters)")
    return value


def number(data, key, required=True):
    value = data.get(key)
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{key} must be a finite number")
    return float(value)


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError("dates must use YYYY-MM-DD")


def flag_for(value, low, high, crit_low, crit_high):
    if crit_low is not None and value <= crit_low:
        return "critical"
    if crit_high is not None and value >= crit_high:
        return "critical"
    if value < low:
        return "low"
    if value > high:
        return "high"
    return "normal"


def iso(value):
    return value.isoformat() if value else None


def summary(case):
    out = {
        "id": case.id,
        "patient": case.patient.full_name,
        "status": case.status,
        "created_at": iso(case.created_at),
        "tests": len(case.results),
        "abnormal": sum(1 for r in case.results if r.flag != "normal"),
    }
    if case.critical:
        out["critical"] = True
    return out


def detail(case, role):
    out = summary(case)
    out["disclaimer"] = DISCLAIMER
    out["results"] = [
        {"test": r.test_name, "value": r.value, "unit": r.unit,
         "range": f"{r.ref_low}-{r.ref_high}", "flag": r.flag}
        for r in case.results
    ]
    if case.critical:
        out["notice"] = CRITICAL_NOTICE
    if role != "lab":  # lab technicians never see clinical conclusions
        out["conclusion"] = case.conclusion
        out["released_at"] = iso(case.released_at)
        out["prescriptions"] = [
            {"drug": p.drug_name, "dosage": p.dosage, "instructions": p.instructions}
            for p in case.prescriptions
        ]
    return out


def visible_cases():
    """Patients only ever see their own RELEASED cases."""
    query = Case.query.join(User, Case.patient_id == User.id)
    if g.user.role == "patient":
        query = query.filter(Case.patient_id == g.user.id, Case.status == "released")
    return query


# ---------- routes ----------
@app.get("/health")
@limiter.exempt
def health():
    try:
        db.session.execute(sql_text("SELECT 1"))
    except Exception:
        return jsonify({"status": "db_unavailable"}), 503
    return jsonify({"status": "ok", "server": os.getenv("SERVER_NAME", "local")})


@app.post("/auth/login")
@limiter.limit("10 per minute")
def login():
    data = body()
    user = User.query.filter_by(username=str(data.get("username", ""))).first()
    if not user or not check_password_hash(user.password_hash, str(data.get("password", ""))):
        return error("Invalid credentials", 401)
    claims = {
        "sub": str(user.id),
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jsonify({"token": jwt.encode(claims, SECRET, algorithm="HS256"),
                    "role": user.role, "full_name": user.full_name})


@app.post("/cases")
@auth_required("lab")
def create_case():
    data = body()
    patient = User.query.filter_by(username=req_str(data, "patient_username", 50), role="patient").first()
    if not patient:
        return error("Patient not found", 404)
    items = data.get("results")
    if not isinstance(items, list) or not 1 <= len(items) <= 50:
        raise ValueError("results must be a list of 1 to 50 items")
    case = Case(patient_id=patient.id, created_by=g.user.id)
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each result must be an object")
        value, low, high = number(item, "value"), number(item, "ref_low"), number(item, "ref_high")
        if low > high:
            raise ValueError("ref_low must not exceed ref_high")
        flag = flag_for(value, low, high, number(item, "crit_low", False), number(item, "crit_high", False))
        case.results.append(LabResult(test_name=req_str(item, "test_name", 80), value=value,
                                      unit=req_str(item, "unit", 20), ref_low=low, ref_high=high, flag=flag))
    case.critical = any(r.flag == "critical" for r in case.results)
    if all(r.flag == "normal" for r in case.results):  # hybrid rule: normal results auto-release
        case.status, case.released_at = "released", utcnow()
    db.session.add(case)
    db.session.commit()
    out = detail(case, "lab")
    out["message"] = ("All values normal: released to the patient automatically."
                      if case.status == "released" else "Saved. Awaiting doctor review before release.")
    return jsonify(out), 201


# @app.get("/cases")
# @auth_required()
# def list_cases():
#     query = visible_cases()
#     status = request.args.get("status")
#     if status:
#         if status not in STATUSES:
#             raise ValueError("status must be one of: " + ", ".join(STATUSES))
#         query = query.filter(Case.status == status)
#     term = request.args.get("q", "").strip()[:50]
#     if term:
#         query = query.filter(or_(
#             User.full_name.icontains(term, autoescape=True),
#             Case.results.any(LabResult.test_name.icontains(term, autoescape=True)),
#         ))
#     start, end = parse_date(request.args.get("from")), parse_date(request.args.get("to"))
#     if start:
#         query = query.filter(Case.created_at >= start)
#     if end:
#         query = query.filter(Case.created_at < end + timedelta(days=1))
#     columns = {"date": Case.created_at, "patient": User.full_name, "status": Case.status}
#     sort = request.args.get("sort", "date")
#     if sort not in columns:
#         raise ValueError("sort must be one of: " + ", ".join(columns))
#     order = columns[sort].asc() if request.args.get("order") == "asc" else columns[sort].desc()
#     cases = query.order_by(order).limit(100).all()
#     return jsonify({"count": len(cases), "cases": [summary(c) for c in cases], "disclaimer": DISCLAIMER})


# @app.get("/cases/<int:case_id>")
# @auth_required()
# def get_case(case_id):
#     case = visible_cases().filter(Case.id == case_id).first()
#     if not case:
#         return error("Case not found", 404)  # same answer whether missing or not yours
#     return jsonify(detail(case, g.user.role))


# @app.get("/cases/<int:case_id>/medications")
# @auth_required("patient", "doctor")
# def medications(case_id):
#     case = visible_cases().filter(Case.id == case_id).first()
#     if not case:
#         return error("Case not found", 404)
#     meds = [{"drug": p.drug_name, "dosage": p.dosage, "instructions": p.instructions,
#              "drug_info": drug_info(p.drug_name)} for p in case.prescriptions]
#     return jsonify({"case_id": case.id, "medications": meds, "disclaimer": DISCLAIMER})


# @app.put("/cases/<int:case_id>/conclusion")
# @auth_required("doctor")
# def set_conclusion(case_id):
#     case = db.session.get(Case, case_id)
#     if not case:
#         return error("Case not found", 404)
#     case.conclusion = req_str(body(), "conclusion", 2000)
#     case.reviewed_by = g.user.id
#     if case.status == "lab_completed":
#         case.status = "doctor_reviewed"
#     db.session.commit()
#     return jsonify(detail(case, "doctor"))


# @app.post("/cases/<int:case_id>/prescriptions")
# @auth_required("doctor")
# def add_prescription(case_id):
#     case = db.session.get(Case, case_id)
#     if not case:
#         return error("Case not found", 404)
#     data = body()
#     case.prescriptions.append(Prescription(drug_name=req_str(data, "drug_name", 80),
#                                            dosage=req_str(data, "dosage", 80),
#                                            instructions=req_str(data, "instructions", 255)))
#     db.session.commit()
#     return jsonify(detail(case, "doctor")), 201


# @app.post("/cases/<int:case_id>/release")
# @auth_required("doctor")
# def release(case_id):
#     case = db.session.get(Case, case_id)
#     if not case:
#         return error("Case not found", 404)
#     if case.status == "released":
#         return error("Case is already released", 409)
#     if not case.conclusion:
#         return error("Write a conclusion before releasing", 400)
#     case.status, case.released_at, case.reviewed_by = "released", utcnow(), g.user.id
#     db.session.commit()
#     return jsonify(detail(case, "doctor"))


# if __name__ == "__main__":
#     app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")))




















