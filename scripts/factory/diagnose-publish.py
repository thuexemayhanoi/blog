import subprocess, sys

IDS = "BLG-00635..BLG-00644"
LOG = []

def log(s):
    LOG.append(str(s))

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

log("DIAGNOSE v8 - invoke real factory-operator publish (throwaway workspace, no push)")
c, o, e = run(["git", "rev-parse", "HEAD"])
log("head=" + o.strip())
log("")
log("=== factory-operator.py publish --ids " + IDS + " ===")
c, o, e = run([sys.executable, "scripts/factory/factory-operator.py", "publish", "--ids", IDS])
log("publish exit=" + str(c))
log("--- stdout ---")
log(o)
log("--- stderr ---")
log(e)
log("")
log("=== git status --porcelain after op ===")
c2, o2, e2 = run(["git", "status", "--porcelain"])
log(o2)
log("")
log("=== restore workspace (no state pushed) ===")
c3, o3, e3 = run(["git", "reset", "--hard", "HEAD"])
log("git reset exit=" + str(c3))
log(o3.strip())
c4, o4, e4 = run(["git", "clean", "-fd"])
log("git clean exit=" + str(c4))
log(o4.strip())
out = chr(10).join(LOG) + chr(10)
with open("data/factory/diagnose-publish-dryrun.txt", "w", encoding="utf-8") as f:
    f.write(out)
print(out)
print("evidence written after restore; workspace tree is back to HEAD")
