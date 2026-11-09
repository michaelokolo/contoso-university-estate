# Sprint 0: start here

Sprint goal: **finish the estate and set up how the team works.** Runs until Sunday 15 November.

Do these in order. Each step says which story it completes.

## 1. Create the board and backlog (10 minutes)

```bash
brew install gh                 # if you don't have it
gh auth login                   # choose GitHub.com, HTTPS, log in with a browser
gh auth refresh -s project      # allow it to create project boards
python3 tools/create_backlog.py --dry-run   # see what it will create
python3 tools/create_backlog.py
```

Then on GitHub: your profile → **Projects** → **Contoso Integration Platform**:
1. Switch the view to **Board**.
2. Edit the **Status** field so the columns are: **Backlog, Ready, In progress, In review, Done**.
3. Move CU-2 to CU-8 into **Ready** (they're Sprint 0).

## 2. Protect `main` (CU-2, 5 minutes)

First push this sprint's changes (see the bottom of this page), so the CI workflow exists. Then on GitHub: repo → **Settings** → **Branches** → **Add branch ruleset** (or *Add classic branch protection rule*):

- Branch name: `main`
- ✅ Require a pull request before merging (approvals: 0 while the team has one engineer)
- ✅ Require status checks to pass → add **Lint and test (Python)** and **Validate Docker Compose**
- ✅ Block force pushes

**Prove it works (acceptance criterion):**
```bash
git switch -c chore/CU-2-prove-ci
echo "def test_broken(): assert False" > tests/test_broken.py
git add tests/test_broken.py && git commit -m "test: prove CI blocks a failing test"
git push -u origin chore/CU-2-prove-ci
gh pr create --fill
```
The PR shows a red check and can't be merged. Then fix it:
```bash
git rm tests/test_broken.py && git commit -m "test: remove deliberately failing test" && git push
```
The check goes green. Close the PR without merging (it changes nothing), and delete the branch.

## 3. Terraform state (CU-3, 5 minutes)

```bash
./deploy/bootstrap-tfstate.sh
```
It creates the state storage and writes `infra/backend.env`. Commit that file on a branch and open a PR: your first real PR through the process.

## 4. GitHub to Azure with OIDC (CU-4, 10 minutes)

```bash
./deploy/setup-oidc.sh
```
Then on GitHub: **Actions** → **Azure login check** → **Run workflow**. A green run that prints your subscription proves it: GitHub signed in to Azure **without any stored secret**.

> If your repo is **private** on a free GitHub plan, required reviewers on the `prod` environment aren't available (the script tells you). Either make the repo public (nothing secret is in it), or treat prod approval as a manual step for now.

## 5. CRM, Moodle, Microsoft 365 (CU-5 to CU-7)

Separate guides follow, one per story.

## 6. Sprint review and retro (CU-8)

At the weekend: show every system running, write the retro in `backlog/retros.md`, and we refine Sprint 1 together.

## How to work on every story from now on

```bash
git switch main && git pull
git switch -c feature/CU-12-short-name     # branch per story
# ...work, commit with Conventional Commits: feat(crm): ..., fix(sis): ...
git push -u origin HEAD
gh pr create --fill                        # fill in the PR template
# CI runs; get a review; merge with "Squash and merge"; delete the branch
```

Move the story's card across the board as you go: **Ready → In progress → In review → Done**.
