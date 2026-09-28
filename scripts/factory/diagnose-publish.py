import subprocess, sys, os

IDS = "BLG-00635,BLG-00636,BLG-00637,BLG-00638,BLG-00639,BLG-00640,BLG-00641,BLG-00642,BLG-00643,BLG-00644"
LOG = []

def log(s):
    LOG.append(str(s))

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

def sh(script):
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

log("DIAGNOSE v10 - full post-op workflow sequence (no push)")
c, o, e = run(["git", "rev-parse", "HEAD"])
ORIG = o.strip()
log("orig_head=" + ORIG)
log("")
log("=== STEP 1: op publish ===")
c, o, e = run([sys.executable, "scripts/factory/factory-operator.py", "publish", "--ids", IDS])
log("publish exit=" + str(c))
log((o or "")[-2000:])
log("stderr tail: " + (e or "")[-800:])
log("")
log("=== STEP 2: xoa lenh ===")
c, o, e = sh("git rm -f --ignore-unmatch --quiet data/factory/operator-command.json; rm -f data/factory/operator-command.json; echo done")
log("rm exit=" + str(c) + " " + o.strip())
log("")
log("=== STEP 3: verify chuan (workflow stage) ===")
c, o, e = sh("find scripts -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null; git add -A; git write-tree")
VT = o.strip()
log("verified_tree=" + VT)
c, o, e = run([sys.executable, "scripts/factory/factory-operator.py", "verify", "--scope", "fast"])
log("verify exit=" + str(c))
log("--- verify stdout ---")
log(o)
log("--- verify stderr ---")
log(e)
c, o, e = sh("find scripts -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null; git add -A; git write-tree")
log("tree_after_verify=" + o.strip())
log("tree_match=" + str(o.strip() == VT))
log("")
log("=== STEP 4: commit local (no push) ===")
c, o, e = sh("git config user.name factory-operator-bot; git config user.email 41898282+github-actions[bot]@users.noreply.github.com; git add -A; git write-tree")
log("tree_pre_commit=" + o.strip() + " match=" + str(o.strip() == VT))
c, o, e = sh("git diff --cached --quiet; echo diff_exit=$?")
log("diff_cached_quiet: " + o.strip())
c, o, e = sh("git commit -m factory-operator-test-local-only -q; git rev-parse HEAD^tree")
log("commit exit=" + str(c) + " out=" + o.strip())
c, o, e = sh("git rev-parse HEAD^{tree}")
log("head_tree=" + o.strip() + " match_verified=" + str(o.strip() == VT))
log("")
log("=== restore ===")
c, o, e = run(["git", "reset", "--hard", ORIG])
log("reset exit=" + str(c))
c, o, e = run(["git", "clean", "-fd"])
log("clean exit=" + str(c))
out = chr(10).join(LOG) + chr(10)
with open("data/factory/diagnose-publish-dryrun.txt", "w", encoding="utf-8") as f:
    f.write(out)
print(out)
print("evidence written after restore")
