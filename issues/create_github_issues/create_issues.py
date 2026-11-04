"""Create labels, milestones and issues on GitHub using the REST API (gh api).

Usage: python3 create_issues.py OWNER/REPO [--dry-run]
Skips issues whose title already exists, so it is safe to re-run.
"""
import json, subprocess, sys
from issues import ISSUES

COLORS = {
    "user story": "1D76DB", "setup": "5319E7",
    "role: gym goer": "0E8A16", "role: admin": "D93F0B",
    "core: LLM": "FBCA04", "core: differentiator": "B60205",
}
MILESTONES = {
    "Alpha": "Core user stories for the Alpha: upload, measurement, AI coaching, validation and results.",
    "Beta": "Roadmap to Beta: admin dashboards, trainer grading, comparisons, data deletion and more lifts.",
}

def api(path, method="GET", fields=None, check=True):
    args = ["gh", "api", "-X", method, path]
    inp = None
    if fields is not None:
        args += ["--input", "-"]
        inp = json.dumps(fields)
    r = subprocess.run(args, input=inp, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"{method} {path} failed: {r.stdout.strip()} {r.stderr.strip()}")
    return json.loads(r.stdout) if r.stdout.strip() else None

def main():
    repo, dry = sys.argv[1], "--dry-run" in sys.argv
    R = f"repos/{repo}"
    labels = sorted({l for i in ISSUES for l in i["labels"]})
    if dry:
        print(f"{len(ISSUES)} issues, {len(labels)} labels")
        for i in ISSUES: print(f"  {i['milestone']:<6} {i['title']}")
        return
    have_labels = {l["name"] for l in api(f"{R}/labels?per_page=100")}
    for l in labels:
        if l not in have_labels:
            api(f"{R}/labels", "POST", {"name": l, "color": COLORS.get(l, "C5DEF5")})
    ms = {m["title"]: m["number"] for m in api(f"{R}/milestones?state=all&per_page=100")}
    for t, d in MILESTONES.items():
        if t not in ms:
            ms[t] = api(f"{R}/milestones", "POST", {"title": t, "description": d})["number"]
    existing = {i["title"] for i in api(f"{R}/issues?state=all&per_page=100")}
    for i in ISSUES:
        if i["title"] in existing:
            print("skip  ", i["title"]); continue
        res = api(f"{R}/issues", "POST", {"title": i["title"], "body": i["body"],
                                           "labels": i["labels"], "milestone": ms[i["milestone"]]})
        print(f"#{res['number']:<3} {i['title']}")

if __name__ == "__main__":
    main()
