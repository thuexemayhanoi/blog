import subprocess, sys, os, json, shutil, tempfile, importlib.util, re

LOG = []

def log(s):
    LOG.append(str(s))

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

log("DIAGNOSE v13 - engine description_length criterion vs fixture desc")
src = open("scripts/factory/factory-operator.py", encoding="utf-8").read()
lines = src.split(chr(10))
for i, ln in enumerate(lines):
    if "description_length" in ln or "description" in ln and ("len" in ln or "140" in ln or "160" in ln):
        log("L" + str(i+1) + ": " + ln)
log("")
log("=== context around description_length checks ===")
idxs = [i for i, ln in enumerate(lines) if "description_length" in ln]
for i in idxs:
    lo = max(0, i - 15)
    hi = min(len(lines), i + 6)
    for j in range(lo, hi):
        log("L" + str(j+1) + ": " + lines[j])
    log("---")
log("")
log("=== fixture descs for next-chunk rows ===")
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
    def py2(*a):
        return m.run_py(list(a), fx)
    r = py2("scripts/factory/factory-operator.py", "prepare-next", "--count", "10")
    log("prepare-next exit=" + str(r.returncode))
    for k in range(3):
        rows = m.matrix_rows(fx)
        row = [x for x in rows if x["status"] == "WRITING"][k]
        p = m.make_draft(fx, row)
        text = open(p, encoding="utf-8").read()
        mm = re.search(r"^description: (.*)$", text, flags=re.M)
        d = mm.group(1)
        log(row["id"] + " keyword=" + row["primary_keyword"])
        log("  desc_len=" + str(len(d)) + " desc=" + d)
    shutil.rmtree(base, ignore_errors=True)
except Exception as ex:
    import traceback
    log(traceback.format_exc()[-3000:])
out = chr(10).join(LOG) + chr(10)
with open("data/factory/diagnose-publish-dryrun.txt", "w", encoding="utf-8") as f:
    f.write(out)
print(out)
print("evidence written; workspace not mutated")
