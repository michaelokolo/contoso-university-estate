"""Create the labels, sprints (milestones), issues and project board on GitHub from backlog/backlog.json.

Needs the GitHub CLI, signed in with project scope:
    brew install gh
    gh auth login
    gh auth refresh -s project

Run from the repo root:
    python tools/create_backlog.py --dry-run    # show what would be created
    python tools/create_backlog.py              # create it (safe to re-run: existing items are skipped)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

BACKLOG = Path(__file__).resolve().parent.parent / "backlog" / "backlog.json"
PROJECT_TITLE = "Contoso Integration Platform"


def gh(args: list[str], dry: bool, capture: bool = True) -> str:
    if dry:
        print("  gh", " ".join(a if " " not in a else repr(a) for a in args))
        return ""
    result = subprocess.run(["gh", *args], capture_output=capture, text=True)
    if result.returncode != 0:
        print(f"  ! gh {' '.join(args[:3])} ... failed: {result.stderr.strip()}", file=sys.stderr)
        return ""
    return result.stdout.strip()


def body_for(item: dict) -> str:
    if "body" in item:
        return item["body"]
    criteria = "\n".join(f"- [ ] {c}" for c in item["acceptance"])
    return (f"## Story\n{item['story']}\n\n## Acceptance criteria\n{criteria}\n\n"
            f"**Story points:** {item.get('points', '?')}\n\n*Backlog ID: {item['id']}*")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    dry = parser.parse_args().dry_run
    data = json.loads(BACKLOG.read_text())

    repo = "OWNER/REPO" if dry else gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], dry)
    if not repo:
        sys.exit("Run this inside the cloned repo, signed in with `gh auth login`.")
    owner = repo.split("/")[0]
    print(f"Repository: {repo}\n")

    print("Labels")
    for label in data["labels"]:
        gh(["label", "create", label["name"], "--color", label["color"], "--description", label["description"], "--force"], dry)

    print("Sprints (milestones)")
    existing = [] if dry else json.loads(gh(["api", f"repos/{repo}/milestones?state=all", "--paginate"], dry) or "[]")
    have = {m["title"] for m in existing}
    for m in data["milestones"]:
        if m["title"] in have:
            print(f"  skip {m['title']} (exists)")
            continue
        gh(["api", f"repos/{repo}/milestones", "-f", f"title={m['title']}", "-f", f"due_on={m['due_on']}",
            "-f", f"description={m['description']}"], dry)

    print("Project board")
    number = ""
    if not dry:
        projects = json.loads(gh(["project", "list", "--owner", owner, "--format", "json"], dry) or '{"projects": []}')
        number = next((str(p["number"]) for p in projects["projects"] if p["title"] == PROJECT_TITLE), "")
        if not number:
            created = json.loads(gh(["project", "create", "--owner", owner, "--title", PROJECT_TITLE, "--format", "json"], dry) or "{}")
            number = str(created.get("number", ""))
        print(f"  project #{number}")
    else:
        gh(["project", "create", "--owner", owner, "--title", PROJECT_TITLE], dry)

    print("Issues")
    titles = set() if dry else {i["title"] for i in json.loads(
        gh(["issue", "list", "--state", "all", "--limit", "500", "--json", "title"], dry) or "[]")}
    for item in data["issues"]:
        title = f"{item['id']}: {item['title']}"
        if title in titles:
            print(f"  skip {title} (exists)")
            continue
        args = ["issue", "create", "--title", title, "--body", body_for(item), "--milestone", item["milestone"]]
        for label in item["labels"]:
            args += ["--label", label]
        url = gh(args, dry)
        if url and number:
            gh(["project", "item-add", number, "--owner", owner, "--url", url], dry)
        print(f"  {title}")

    print("\nDone. Open the project on GitHub and set the board columns: Backlog, Ready, In progress, In review, Done.")


if __name__ == "__main__":
    main()
