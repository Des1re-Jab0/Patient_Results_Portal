"""Tests for the CLI display code: colours, table alignment and safe output. No server needed.

Usage (project folder, virtual environment active):  python tests/test_cli_format.py
"""
import contextlib
import importlib.util
import io
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("portal", ROOT / "cli" / "portal.py")
portal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portal)

ANSI = re.compile("\x1b\\[[0-9;]*m")
results = {"passed": 0, "failed": 0}


def check(name, condition, detail=""):
    key = "passed" if condition else "failed"
    results[key] += 1
    print(("PASS  " if condition else "FAIL  ") + name + ("" if condition or not detail else "   -> " + str(detail)))


def capture(function, *args):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        function(*args)
    return buffer.getvalue()


def set_color(on):
    portal.COLOR["out"] = on
    portal.COLOR["err"] = on


ROWS = [(1, "Alice Uwase", "released", "2026-11-24", 2, 0, ""),
        (3, "Eric Mugisha", "lab_completed", "2026-11-24", 1, 1, "YES")]
HEADERS = ["ID", "PATIENT", "STATUS", "DATE", "TESTS", "ABNORMAL", "CRITICAL"]
RESULT_ROWS = [("Potassium", 6.9, "mmol/L", "3.5-5.0", "CRITICAL"), ("Sodium", 140, "mmol/L", "135-145", "NORMAL")]
RESULT_HEADERS = ["TEST", "VALUE", "UNIT", "REF RANGE", "FLAG"]

print("--- colour switch ---")
set_color(False)
check("paint returns plain text when colour is off", portal.paint("hi", "red") == "hi")
set_color(True)
check("paint adds colour codes when colour is on", portal.paint("hi", "red") == "\x1b[31mhi\x1b[0m")
check("paint with no style leaves text alone", portal.paint("hi") == "hi")
os.environ["FORCE_COLOR"] = "1"
os.environ["NO_COLOR"] = "1"
portal.init_color(False)
check("NO_COLOR wins over FORCE_COLOR", portal.COLOR["out"] is False)
del os.environ["NO_COLOR"]
portal.init_color(True)
check("--no-color turns colours off", portal.COLOR["out"] is False)
del os.environ["FORCE_COLOR"]

print("--- table layout ---")
for label, on in (("colour off", False), ("colour on", True)):
    set_color(on)
    for name, rows, headers, style in (("case list", ROWS, HEADERS, portal.list_style),
                                       ("result table", RESULT_ROWS, RESULT_HEADERS, portal.result_style)):
        lines = [ANSI.sub("", line) for line in capture(portal.table, rows, headers, style).splitlines()]
        body = [line for line in lines if not set(line) <= {"-"}]
        check(name + " columns stay aligned (" + label + ")", len({len(line) for line in body}) == 1, [len(x) for x in body])

print("--- colours carry meaning ---")
set_color(True)
raw = capture(portal.table, ROWS, HEADERS, portal.list_style)
check("header row has a blue background", "\x1b[1;97;44m" in raw)
check("critical case shows a red badge", "\x1b[1;97;41m" in raw)
check("released status is green", "\x1b[32mreleased" in raw)
check("awaiting-doctor status is magenta", "\x1b[35mlab_completed" in raw)
raw = capture(portal.table, RESULT_ROWS, RESULT_HEADERS, portal.result_style)
check("critical value is bold red", "\x1b[1;31m6.9" in raw)
check("normal flag is green", "\x1b[32mNORMAL" in raw)
set_color(False)
plain = capture(portal.table, ROWS, HEADERS, portal.list_style)
check("no colour codes at all when colour is off", "\x1b" not in plain)
check("plain mode still has a header rule", "-----" in plain)

print("--- notices and safety ---")
set_color(False)
check("critical notice is still obvious without colour", capture(portal.banner, "Go now", "bold").startswith("!!! Go now"))
set_color(True)
banner = capture(portal.banner, "Go now", "bold", "white", "bg_red")
check("critical notice is a red banner with colour", "\x1b[1;97;41m" in banner and "Go now" in banner)
lines = [x for x in capture(portal.footer, {"disclaimer": "word " * 40}, "web-01").splitlines() if x.strip()]
check("every disclaimer line is coloured (survives pagers)", all(x.startswith("\x1b[") for x in lines), lines)
check("server text cannot inject terminal escape codes", "\x1b" not in portal.clean("a\x1b[31mred\x1b[0m"))
check("newlines in server text become spaces", portal.clean("a\nb") == "a b")
set_color(False)

print()
print("RESULT: %d passed, %d failed" % (results["passed"], results["failed"]))
sys.exit(1 if results["failed"] else 0)
