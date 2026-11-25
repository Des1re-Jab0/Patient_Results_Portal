"""Local smoke test. Runs the API in-process on a temporary database: no server needed.

Usage (project folder, virtual environment active):  python tests/smoke_test.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp()
os.environ["SECRET_KEY"] = "test-secret-key-" + "x" * 40
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(TMP) / "test.db").as_posix()
os.environ["OPENFDA_API_KEY"] = ""

import server.seed  # noqa: E402  (creates tables and loads the demo data)
from server import openfda  # noqa: E402
from server.app import app  # noqa: E402

client = app.test_client()
results = {"passed": 0, "failed": 0}


def check(name, condition, detail=""):
    key = "passed" if condition else "failed"
    results[key] += 1
    print(("PASS  " if condition else "FAIL  ") + name + ("" if condition or not detail else "   -> " + str(detail)))


def login(username, password):
    resp = client.post("/auth/login", json={"username": username, "password": password})
    return resp.get_json().get("token", "") if resp.status_code == 200 else ""


def auth(token):
    return {"Authorization": "Bearer " + token}


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


print("--- basics ---")
resp = client.get("/health")
check("health endpoint is ok", resp.status_code == 200 and resp.get_json()["status"] == "ok")
check("X-Served-By header is present", "X-Served-By" in resp.headers)
check("wrong password is rejected (401)",
      client.post("/auth/login", json={"username": "patient1", "password": "nope"}).status_code == 401)
patient1 = login("patient1", "Patient123!")
patient2 = login("patient2", "Patient456!")
lab = login("lab1", "LabTech123!")
doctor = login("doctor1", "Doctor123!")
check("all four demo accounts can log in", all([patient1, patient2, lab, doctor]))
check("no token is rejected (401)", client.get("/cases").status_code == 401)
check("forged token is rejected (401)", client.get("/cases", headers=auth("abc.def.ghi")).status_code == 401)

print("--- patient visibility ---")
cases = client.get("/cases", headers=auth(patient1)).get_json()["cases"]
check("patient1 sees only released cases 1 and 2", {c["id"] for c in cases} == {1, 2}, cases)
case2 = client.get("/cases/2", headers=auth(patient1)).get_json()
check("case 2 shows a HIGH glucose flag", case2["results"][0]["flag"] == "high")
check("case 2 shows the doctor conclusion and Metformin",
      bool(case2["conclusion"]) and case2["prescriptions"][0]["drug"] == "Metformin")
check("unreleased case 3 is hidden from patient1 (404)", client.get("/cases/3", headers=auth(patient1)).status_code == 404)
check("patient2 sees nothing yet", client.get("/cases", headers=auth(patient2)).get_json()["count"] == 0)

print("--- search, filter, sort and validation ---")
check("search glucose finds 1 case", client.get("/cases?q=glucose", headers=auth(patient1)).get_json()["count"] == 1)
check("search with SQL injection text finds nothing",
      client.get("/cases?q=%27+OR+1%3D1+--", headers=auth(patient1)).get_json()["count"] == 0)
check("percent sign is not a wildcard", client.get("/cases?q=%25", headers=auth(patient1)).get_json()["count"] == 0)
check("status filter works", client.get("/cases?status=released", headers=auth(patient1)).get_json()["count"] == 2)
check("sort ascending works", client.get("/cases?sort=date&order=asc", headers=auth(patient1)).status_code == 200)
check("unknown sort column is rejected (400)", client.get("/cases?sort=password_hash", headers=auth(patient1)).status_code == 400)
check("bad date is rejected (400)", client.get("/cases?from=notadate", headers=auth(patient1)).status_code == 400)

print("--- roles ---")
check("patient cannot upload results (403)", client.post("/cases", headers=auth(patient1), json={}).status_code == 403)
check("lab cannot release a case (403)", client.post("/cases/3/release", headers=auth(lab)).status_code == 403)
check("lab sees no conclusion field", "conclusion" not in client.get("/cases/2", headers=auth(lab)).get_json())

print("--- lab upload and hybrid release rule ---")
normal = client.post("/cases", headers=auth(lab), json={"patient_username": "patient1", "results": [
    {"test_name": "Sodium", "value": 140, "unit": "mmol/L", "ref_low": 135, "ref_high": 145}]})
check("normal upload is released automatically", normal.status_code == 201 and normal.get_json()["status"] == "released")
critical = client.post("/cases", headers=auth(lab), json={"patient_username": "patient2", "results": [
    {"test_name": "Hemoglobin", "value": 6.1, "unit": "g/dL", "ref_low": 12, "ref_high": 16, "crit_low": 7, "crit_high": 20}]})
crit_id = critical.get_json()["id"]
check("critical upload waits for the doctor",
      critical.status_code == 201 and critical.get_json()["status"] == "lab_completed" and critical.get_json()["critical"])
check("patient2 cannot see the unreleased critical case", client.get("/cases/" + str(crit_id), headers=auth(patient2)).status_code == 404)
check("NaN value is rejected (400)", client.post("/cases", headers=auth(lab), data='{"patient_username":"patient1","results":[{"test_name":"a","value":NaN,"unit":"u","ref_low":0,"ref_high":1}]}', content_type="application/json").status_code == 400)
check("ref_low above ref_high is rejected (400)", client.post("/cases", headers=auth(lab), json={"patient_username": "patient1", "results": [
    {"test_name": "a", "value": 1, "unit": "u", "ref_low": 5, "ref_high": 1}]}).status_code == 400)
check("non-JSON body is rejected (400)", client.post("/cases", headers=auth(lab), data="garbage", content_type="application/json").status_code == 400)

print("--- doctor workflow and the critical notice ---")
url = "/cases/" + str(crit_id)
check("release without a conclusion is refused (400)", client.post(url + "/release", headers=auth(doctor)).status_code == 400)
check("oversized conclusion is rejected (400)", client.put(url + "/conclusion", headers=auth(doctor), json={"conclusion": "x" * 2001}).status_code == 400)
check("doctor saves a conclusion", client.put(url + "/conclusion", headers=auth(doctor), json={"conclusion": "Severe anaemia. Attend hospital now."}).get_json()["status"] == "doctor_reviewed")
check("doctor adds a prescription", client.post(url + "/prescriptions", headers=auth(doctor), json={"drug_name": "Ferrous sulfate", "dosage": "200 mg", "instructions": "Once daily"}).status_code == 201)
check("doctor releases the case", client.post(url + "/release", headers=auth(doctor)).get_json()["status"] == "released")
check("releasing twice is refused (409)", client.post(url + "/release", headers=auth(doctor)).status_code == 409)
shown = client.get(url, headers=auth(patient2)).get_json()
check("patient2 now sees the CRITICAL notice", "CRITICAL" in shown.get("notice", ""))
check("patient1 cannot read patient2's case (404)", client.get(url, headers=auth(patient1)).status_code == 404)

print("--- openFDA integration (network is mocked) ---")
fda = {"results": [{"purpose": ["Test purpose"], "warnings": ["Test warning"]}]}
openfda._cache.clear()
with mock.patch("server.openfda.requests.get", return_value=FakeResponse(200, fda)) as fake_get:
    meds = client.get("/cases/2/medications", headers=auth(patient1)).get_json()["medications"][0]["drug_info"]
    check("drug info is parsed from the openFDA format", meds["available"] and meds["purpose"] == "Test purpose" and meds["warnings"] == "Test warning", meds)
    client.get("/cases/2/medications", headers=auth(patient1))
    check("second lookup is served from the cache", fake_get.call_count == 1, fake_get.call_count)
openfda._cache.clear()
with mock.patch("server.openfda.requests.get", return_value=FakeResponse(404, {})):
    info = client.get("/cases/2/medications", headers=auth(patient1)).get_json()["medications"][0]["drug_info"]
    check("unknown drug gives a clear message", not info["available"] and "No FDA label" in info["reason"], info)
openfda._cache.clear()
import requests  # noqa: E402
with mock.patch("server.openfda.requests.get", side_effect=requests.ConnectionError("down")):
    resp = client.get("/cases/2/medications", headers=auth(patient1))
    info = resp.get_json()["medications"][0]["drug_info"]
    check("API outage does not crash the app", resp.status_code == 200 and not info["available"] and "unavailable" in info["reason"], info)
openfda._cache.clear()
with mock.patch("server.openfda.requests.get", return_value=FakeResponse(429, {})):
    info = client.get("/cases/2/medications", headers=auth(patient1)).get_json()["medications"][0]["drug_info"]
    check("openFDA rate limit (429) is handled", not info["available"] and "429" in info["reason"], info)
check("patient1 cannot read medications of someone else's case (404)", client.get(url + "/medications", headers=auth(patient1)).status_code == 404)

print("--- login rate limit (last, because it blocks further logins) ---")
codes = [client.post("/auth/login", json={"username": "x", "password": "y"}).status_code for _ in range(12)]
check("too many login attempts are blocked (429)", 429 in codes, codes)

print()
print("RESULT: %d passed, %d failed" % (results["passed"], results["failed"]))
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if results["failed"] else 0)
