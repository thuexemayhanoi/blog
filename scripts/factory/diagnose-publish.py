import subprocess, sys, os, json, shutil, tempfile, importlib.util, traceback

IDS = "BLG-00635,BLG-00636,BLG-00637,BLG-00638,BLG-00639,BLG-00640,BLG-00641,BLG-00642,BLG-00643,BLG-00644"
LOG = []

def log(s):
    LOG.append(str(s))

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

log("DIAGNOSE v12 - why fixture draft for next chunk scores REPAIR")
c, o, e = run(["git", "rev-parse", "HEAD"])
ORIG = o.strip()
log("orig_head=" + ORIG)
c, o, e = run([sys.executable, "scripts/factory/factory-operator.py", "publish", "--ids", IDS])
log("publish exit=" + str(c))
log("")
try:
    spec = importlib.util.spec_from_file_location("tqm", "scripts/factory/tests/test_qa_modes.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    base = tempfile.mkdtemp()
    fx = os.path.join(base, "repo")
    shutil.copytree(m.ROOT, fx, ignore=m.IGNORE)
    dd = os.path.join(fx, "_drafts")
    for fn in os.listdir(dd):
        os.remove(os.path.join(dd, fn))
    def py(*a):
        return m.run_py(list(a), fx)
    r = py("scripts/factory/factory-operator.py", "prepare-next", "--count", "10")
    log("prepare-next exit=" + str(r.returncode))
    log((r.stdout or "")[-1200:])
    row = m.first_writing(fx)
    log("row=" + row["id"])
    log("keyword=" + str(row.get("primary_keyword")))
    log("word_target=" + str(row.get("word_target")))
    log("internal_links=" + str(row.get("internal_links")))
    log("canonical_url=" + str(row.get("canonical_url")))
    p = m.make_draft(fx, row)
    log("draft=" + p)
    r = py("scripts/factory/factory-operator.py", "qa", "--scope", "fast", "--ids", row["id"])
    log("qa exit=" + str(r.returncode))
    log("--- qa stdout tail ---")
    log((r.stdout or "")[-5000:])
    log("--- qa stderr tail ---")
    log((r.stderr or "")[-2000:])
    ev = os.path.join(fx, "data", "qa", row["id"] + ".json")
    if os.path.exists(ev):
        log("--- qa evidence ---")
        log(open(ev, encoding="utf-8").read()[-9000:])
    else:
        log("no qa evidence file")
    shutil.rmtree(base, ignore_errors=True)
except Exception:
    log("EXCEPTION:")
    log(traceback.format_exc()[-4000:])
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
