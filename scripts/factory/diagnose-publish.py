import subprocess, sys

IDS = "BLG-00635,BLG-00636,BLG-00637,BLG-00638,BLG-00639,BLG-00640,BLG-00641,BLG-00642,BLG-00643,BLG-00644"
LOG = []

def log(s):
    LOG.append(str(s))

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

log("DIAGNOSE v15 - validate repaired test on post-publish tree")
c, o, e = run(["git", "rev-parse", "HEAD"])
ORIG = o.strip()
log("orig_head=" + ORIG)
c, o, e = run([sys.executable, "scripts/factory/factory-operator.py", "publish", "--ids", IDS])
log("publish exit=" + str(c))
log("")
log("=== test_qa_modes.py on post-publish tree (repaired) ===")
c, o, e = run([sys.executable, "scripts/factory/tests/test_qa_modes.py"])
log("exit=" + str(c))
log((o or "")[-1500:])
log((e or "")[-1500:])
log("")
log("=== factory-operator verify --scope fast on post-publish tree ===")
c, o, e = run([sys.executable, "scripts/factory/factory-operator.py", "verify", "--scope", "fast"])
log("verify exit=" + str(c))
log((o or "")[-2500:])
log((e or "")[-800:])
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
