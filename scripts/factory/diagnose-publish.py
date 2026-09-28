import subprocess, sys, difflib

LOG = []

def log(s):
    LOG.append(str(s))

log("DIAGNOSE v14 - repair make_draft: pad desc BEFORE DRAFT_TMPL.format")
p = "scripts/factory/tests/test_qa_modes.py"
src = open(p, encoding="utf-8").read()
if "desc = desc[:160]" not in src:
    log("ALREADY PATCHED or marker missing - no change")
else:
    orig = src
    i2 = src.index("    desc = desc[:160]")
    i1 = src.rindex("    if len(desc) < 140:", 0, i2)
    i3 = src.index(chr(10), i2)
    assert_line_end = src.index(chr(10), i3 + 1)
    removed = src[i1:assert_line_end]
    log("REMOVING old padding block (after format):")
    log(removed)
    src = src[:i1] + src[assert_line_end:]
    anchor = src.index("% row['primary_keyword'])")
    anchor_end = src.index(chr(10), anchor) + 1
    pad = [
        "    if len(desc) < 140:",
        "        desc += ' Đối chiếu văn bản hiện hành trước khi áp dụng.'",
        "    if len(desc) < 140:",
        "        desc += ' Nội dung mang tính tham khảo.'",
        "    desc = desc[:160]",
        "    assert 140 <= len(desc) <= 160, len(desc)",
    ]
    src = src[:anchor_end] + chr(10).join(pad) + chr(10) + src[anchor_end:]
    log("INSERTING padded-desc block right after desc assignment, before format")
    open(p, "w", encoding="utf-8").write(src)
    log("")
    log("=== diff ===")
    for ln in difflib.unified_diff(orig.splitlines(), src.splitlines(), lineterm="", n=2):
        log(ln)
c = subprocess.run([sys.executable, "-m", "py_compile", p], capture_output=True, text=True)
log("py_compile exit=" + str(c.returncode) + " " + (c.stderr or "")[-500:])
out = chr(10).join(LOG) + chr(10)
with open("data/factory/diagnose-publish-dryrun.txt", "w", encoding="utf-8") as f:
    f.write(out)
print(out)
print("patch applied; evidence written")
