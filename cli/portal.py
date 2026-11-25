"""Command-line client for the Results Portal API, with colour output (Windows 10+, macOS, Linux)."""
import argparse
import ctypes
import getpass
import os
import sys
import textwrap
from pathlib import Path

import requests

BASE_URL = os.getenv("PORTAL_URL", "http://127.0.0.1:5000").rstrip("/")
TOKEN_FILE = Path.home() / ".results_portal_token"
TIMEOUT = 10
WIDTH = 78

CODES = {"bold": "1", "red": "31", "green": "32", "yellow": "33", "blue": "34", "magenta": "35",
         "cyan": "36", "black": "30", "gray": "90", "white": "97",
         "bg_red": "41", "bg_green": "42", "bg_yellow": "43", "bg_blue": "44"}
COLOR = {"out": False, "err": False}

STATUS_STYLE = {"released": ("green",), "doctor_reviewed": ("yellow",), "lab_completed": ("magenta",)}
FLAG_STYLE = {"NORMAL": ("green",), "HIGH": ("bold", "yellow"), "LOW": ("bold", "cyan"),
              "CRITICAL": ("bold", "white", "bg_red")}
VALUE_STYLE = {"HIGH": ("bold", "yellow"), "LOW": ("bold", "cyan"), "CRITICAL": ("bold", "red")}


# ---------- colour and text helpers ----------
def enable_windows_ansi(handle_id):
    """Turn on ANSI colour support for a Windows console handle. Returns True on success."""
    if os.name != "nt":
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.GetStdHandle.restype = ctypes.c_void_p
        kernel32.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        kernel32.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        handle = kernel32.GetStdHandle(handle_id)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except (AttributeError, OSError):
        return False


def init_color(disabled=False):
    """Colours are on in a terminal. Off for --no-color, NO_COLOR, pipes and dumb terminals."""
    if disabled or os.getenv("NO_COLOR") or os.getenv("TERM") == "dumb":
        COLOR["out"] = COLOR["err"] = False
        return
    forced = bool(os.getenv("FORCE_COLOR"))
    COLOR["out"] = (forced or sys.stdout.isatty()) and enable_windows_ansi(-11)
    COLOR["err"] = (forced or sys.stderr.isatty()) and enable_windows_ansi(-12)


def paint(text, *styles, err=False):
    if not COLOR["err" if err else "out"] or not styles:
        return text
    return "\033[" + ";".join(CODES[s] for s in styles) + "m" + text + "\033[0m"


def symbol(preferred, fallback):
    """Use a Unicode symbol only if the output encoding can show it."""
    try:
        preferred.encode(sys.stdout.encoding or "ascii")
        return preferred
    except (UnicodeEncodeError, LookupError):
        return fallback


def clean(value):
    """Remove control characters (such as terminal escape codes) from text sent by the server."""
    return "".join(ch if ch.isprintable() else (" " if ch in "\r\n\t" else "") for ch in str(value))


def die(message):
    print(paint("Error: ", "bold", "red", err=True) + clean(message), file=sys.stderr)
    sys.exit(1)


def ok(message):
    print(paint(symbol("\u2713", "OK") + " " + message, "green"))


def warn(message):
    print(paint(message, "yellow"))


def served(server):
    print(paint("[served by " + clean(server) + "]", "gray"))


def banner(message, *styles):
    """Full-width coloured box for important notices."""
    if not COLOR["out"]:
        print("!!! " + message + " !!!")
        return
    for line in textwrap.wrap(message, WIDTH - 4) or [""]:
        print(paint("  " + line.ljust(WIDTH - 4) + "  ", *styles))


def table(rows, headers, cell_style=None):
    """Print an aligned table. Widths use plain text; colours are added after padding."""
    rows = [[clean(c) for c in row] for row in rows]
    widths = [max(len(x) for x in col) for col in zip(headers, *rows)]
    header = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(paint(" " + header + " ", "bold", "white", "bg_blue"))
    if not COLOR["out"]:
        print("-" * (len(header) + 2))
    for row in rows:
        cells = []
        for col, (text, width) in enumerate(zip(row, widths)):
            styles = cell_style(col, text, row) if cell_style else ()
            cells.append(paint(text.ljust(width), *styles))
        print(" " + "  ".join(cells) + " ")


def list_style(col, text, row):
    critical = row[6] == "YES"
    if col == 0:
        return ("bold", "red") if critical else ("bold", "cyan")
    if col == 1:
        return ("bold", "red") if critical else ("bold",)
    if col == 2:
        return STATUS_STYLE.get(text, ())
    if col == 3:
        return ("gray",)
    if col == 5:
        return ("bold", "yellow") if text != "0" else ("gray",)
    if col == 6 and critical:
        return ("bold", "white", "bg_red")
    return ()


def result_style(col, text, row):
    flag = row[4]
    if col == 0:
        return VALUE_STYLE.get(flag, ("bold",))
    if col == 1:
        return VALUE_STYLE.get(flag, ())
    if col in (2, 3):
        return ("gray",)
    if col == 4:
        return FLAG_STYLE.get(flag, ())
    return ()


def footer(data, server):
    if data.get("disclaimer"):
        print()
        for line in textwrap.wrap(clean(data["disclaimer"]), WIDTH):
            print(paint(line, "yellow"))  # one colour code per line, so pagers keep it
    served(server)


# ---------- talking to the API ----------
def call(method, path, payload=None, params=None, auth=True):
    """Send a request; turn every failure into a readable message."""
    headers = {}
    if auth:
        if not TOKEN_FILE.exists():
            die("You are not logged in. Run: portal.py login <username>")
        headers["Authorization"] = "Bearer " + TOKEN_FILE.read_text().strip()
    try:
        resp = requests.request(method, BASE_URL + path, json=payload, params=params,
                                headers=headers, timeout=TIMEOUT)
    except requests.RequestException:
        die("Cannot reach the server at " + BASE_URL + ". Check PORTAL_URL and your connection.")
    try:
        data = resp.json()
    except ValueError:
        die("Unexpected server response (HTTP " + str(resp.status_code) + ").")
    if resp.status_code == 401 and auth:
        die("Session expired or invalid. Please log in again.")
    if resp.status_code >= 400:
        die(data.get("error", "Request failed") + " (HTTP " + str(resp.status_code) + ")")
    return data, resp.headers.get("X-Served-By", "?")


# ---------- commands ----------
def cmd_login(args):
    password = getpass.getpass("Password: ")
    data, server = call("POST", "/auth/login", {"username": args.username, "password": password}, auth=False)
    TOKEN_FILE.write_text(data["token"])
    TOKEN_FILE.chmod(0o600)
    print(paint(symbol("\u2713", "OK") + " Logged in as ", "green") + paint(clean(data["full_name"]), "bold", "green")
          + paint(" (" + clean(data["role"]) + ")", "cyan"))
    served(server)


def cmd_logout(_):
    TOKEN_FILE.unlink(missing_ok=True)
    ok("Logged out.")


# def cmd_list(args):
#     params = {"status": args.status, "q": args.search, "from": args.date_from, "to": args.date_to,
#               "sort": args.sort, "order": "asc" if args.asc else "desc"}
#     data, server = call("GET", "/cases", params={k: v for k, v in params.items() if v})
#     if not data["cases"]:
#         warn("No cases found. If you were tested recently, your results may still be in review.")
#     else:
#         rows = [(c["id"], c["patient"], c["status"], c["created_at"][:10], c["tests"],
#                  c["abnormal"], "YES" if c.get("critical") else "") for c in data["cases"]]
#         table(rows, ["ID", "PATIENT", "STATUS", "DATE", "TESTS", "ABNORMAL", "CRITICAL"], list_style)
#         print(paint(str(len(rows)) + " case(s)", "gray"))
#     footer(data, server)


# def cmd_show(args):
#     data, server = call("GET", "/cases/" + str(args.case_id))
#     sep = paint("  |  ", "gray")
#     print(paint("Case " + str(data["id"]), "bold", "cyan") + sep + paint(clean(data["patient"]), "bold") + sep
#           + paint(clean(data["status"]), *STATUS_STYLE.get(data["status"], ())) + sep
#           + paint(data["created_at"][:10], "gray"))
#     if data.get("notice"):
#         print()
#         banner(clean(data["notice"]), "bold", "white", "bg_red")
#     print()
#     rows = [(r["test"], r["value"], r["unit"], r["range"], r["flag"].upper()) for r in data["results"]]
#     table(rows, ["TEST", "VALUE", "UNIT", "REF RANGE", "FLAG"], result_style)
#     if "conclusion" in data:
#         print()
#         conclusion = clean(data["conclusion"]) if data["conclusion"] else paint("not yet added", "yellow")
#         print(paint("Doctor conclusion: ", "bold", "cyan") + conclusion)
#         for p in data["prescriptions"]:
#             print(paint("Prescribed: ", "bold", "green") + clean(p["drug"]) + " - " + clean(p["dosage"])
#                   + " - " + clean(p["instructions"]))
#     footer(data, server)


# def cmd_meds(args):
#     data, server = call("GET", "/cases/" + str(args.case_id) + "/medications")
#     if not data["medications"]:
#         warn("No medication prescribed for this case.")
#     for med in data["medications"]:
#         print(paint(clean(med["drug"]), "bold", "green") + "  " + clean(med["dosage"])
#               + paint("  |  ", "gray") + clean(med["instructions"]))
#         info = med["drug_info"]
#         if info["available"]:
#             for label, key, color in (("Purpose", "purpose", "cyan"), ("Warnings", "warnings", "yellow")):
#                 if info.get(key):
#                     print("  " + paint(label + ":", "bold", color))
#                     print(textwrap.fill(clean(info[key]), WIDTH, initial_indent="    ", subsequent_indent="    "))
#             print(paint("  Source: openFDA (https://open.fda.gov)", "gray"))
#         else:
#             warn("  Drug information unavailable: " + clean(info["reason"]))
#         print()
#     footer(data, server)


# def parse_test(raw):
#     parts = [p.strip() for p in raw.split(",")]
#     if len(parts) not in (5, 7):
#         die("--test format: name,value,unit,ref_low,ref_high[,crit_low,crit_high]")
#     try:
#         item = {"test_name": parts[0], "value": float(parts[1]), "unit": parts[2],
#                 "ref_low": float(parts[3]), "ref_high": float(parts[4])}
#         if len(parts) == 7:
#             item["crit_low"], item["crit_high"] = float(parts[5]), float(parts[6])
#     except ValueError:
#         die("Numeric fields in --test must be numbers: " + raw)
#     return item


# def cmd_upload(args):
#     payload = {"patient_username": args.patient, "results": [parse_test(t) for t in args.test]}
#     data, server = call("POST", "/cases", payload)
#     message = "Case " + str(data["id"]) + " created. " + clean(data["message"])
#     if data.get("status") == "released":
#         ok(message)
#     else:
#         warn(message)
#     if data.get("critical"):
#         print(paint("CRITICAL value detected: this case needs urgent doctor review.", "bold", "red"))
#     served(server)


# def cmd_conclude(args):
#     data, server = call("PUT", "/cases/" + str(args.case_id) + "/conclusion", {"conclusion": args.text})
#     ok("Conclusion saved. Status: " + clean(data["status"]))
#     served(server)


# def cmd_prescribe(args):
#     payload = {"drug_name": args.drug, "dosage": args.dose, "instructions": args.instructions}
#     data, server = call("POST", "/cases/" + str(args.case_id) + "/prescriptions", payload)
#     ok("Prescription added.")
#     served(server)


# def cmd_release(args):
#     data, server = call("POST", "/cases/" + str(args.case_id) + "/release")
#     ok("Case " + str(data["id"]) + " released to the patient.")
#     served(server)


# def build_parser():
#     parser = argparse.ArgumentParser(prog="portal.py", description="Results Portal CLI (set PORTAL_URL to choose the server)")
#     parser.add_argument("--no-color", action="store_true", help="turn colours off (also: set NO_COLOR=1)")
#     sub = parser.add_subparsers(dest="command", required=True)

#     p = sub.add_parser("login", help="log in")
#     p.add_argument("username")
#     p.set_defaults(func=cmd_login)

#     sub.add_parser("logout", help="log out").set_defaults(func=cmd_logout)

#     p = sub.add_parser("list", help="list cases (filter, search, sort)")
#     p.add_argument("--status", choices=["lab_completed", "doctor_reviewed", "released"])
#     p.add_argument("--search", help="patient name or test name")
#     p.add_argument("--from", dest="date_from", help="YYYY-MM-DD")
#     p.add_argument("--to", dest="date_to", help="YYYY-MM-DD")
#     p.add_argument("--sort", choices=["date", "patient", "status"], default="date")
#     p.add_argument("--asc", action="store_true", help="oldest first")
#     p.set_defaults(func=cmd_list)

#     p = sub.add_parser("show", help="show one case in detail")
#     p.add_argument("case_id", type=int)
#     p.set_defaults(func=cmd_show)

#     p = sub.add_parser("meds", help="show prescriptions with drug information (openFDA)")
#     p.add_argument("case_id", type=int)
#     p.set_defaults(func=cmd_meds)

#     p = sub.add_parser("upload", help="(lab) upload results for a patient")
#     p.add_argument("patient", help="patient username")
#     p.add_argument("--test", action="append", required=True,
#                    help="name,value,unit,ref_low,ref_high[,crit_low,crit_high] (repeatable)")
#     p.set_defaults(func=cmd_upload)

#     p = sub.add_parser("conclude", help="(doctor) write the conclusion")
#     p.add_argument("case_id", type=int)
#     p.add_argument("text")
#     p.set_defaults(func=cmd_conclude)

#     p = sub.add_parser("prescribe", help="(doctor) add a prescription")
#     p.add_argument("case_id", type=int)
#     p.add_argument("--drug", required=True)
#     p.add_argument("--dose", required=True)
#     p.add_argument("--instructions", required=True)
#     p.set_defaults(func=cmd_prescribe)

#     p = sub.add_parser("release", help="(doctor) release the case to the patient")
#     p.add_argument("case_id", type=int)
#     p.set_defaults(func=cmd_release)
#     return parser


# if __name__ == "__main__":
#     args = build_parser().parse_args()
#     init_color(args.no_color)
#     args.func(args)