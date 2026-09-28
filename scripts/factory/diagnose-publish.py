import subprocess, sys

IDS = "BLG-00635,BLG-00636,BLG-00637,BLG-00638,BLG-00639,BLG-00640,BLG-00641,BLG-00642,BLG-00643,BLG-00644"
LOG = []

def log(s):
    LOG.append(str(s))

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

log("DIAGNOSE v11 - test_qa_modes stderr on post-promote state")
c, o, e = run(["git", "rev-parse", "HEAD"])
ORIG = o.strip()
log("orig_head=" + ORIG)
c, o, e = run([sys.executable, "scripts/factory/factory-operator.py", "publish", "--ids", IDS])
log("publish exit=" + str(c))
log("")
log("=== test_qa_modes.py on post-promote tree ===")
c, o, e = run([sys.executable, "scripts/factory/tests/test_qa_modes.py"])
log("exit=" + str(c))
log("--- stdout ---")
log(o[-4000:])
log("--- stderr ---")
log(e[-8000:])
log("")
c, o, e = run(["git", "reset", "--hard", ORIG])
log("reset exit=" + str(c))
c, o, e = run(["git", "clean", "-fd"])
log("clean exit=" + str(c))
out = chr(10).join(LOG) + chr(10)
with open("data/factory/diagnose-publish-dryrun.txt", "w", encoding="utf-8") as f:
    f.write(out)
print(out)
print("evidence written after restore")
