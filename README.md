# Nasa Library Information Systems

## Rules

### Step 1 – Commit Rules

Commit **small, logical changes** with clear messages.

**Commit message convention:**

```
feat: add book management API
fix: correct fine calculation logic
refactor: simplify service layer
chore: update docker configuration
```

Example:

```bash
git add .
git commit -m "feat: implement borrow book API"
git push origin feature/<feature-name>
```

---

### Step 2 – Create Merge Request (MR)

On GitLab:

* Source branch: `feature/<feature-name>`
* Target branch: `develop`
* Assign **at least one reviewer**
* Add a short description of what was implemented

**Before creating MR, ensure:**

* Application builds successfully
* No unnecessary files are committed

---

### Step 3 – Review & Merge

Reviewer responsibilities:

* Verify separation of layers
* Ensure no breaking changes

If approved, **merge into `develop`**.

---

### Step 4 – Merge to Main (Milestone Only)

Merge `develop` into `main` only when:

* A milestone is completed
* System is ready for demo or evaluation

```bash
git checkout main
git merge develop
git push origin main
```

---

## Daily Development Workflow (Mandatory)

Start a new feature:

```bash
git checkout develop
git pull origin develop
git checkout feature/<your-feature>
```

Finish a feature:

```bash
git push origin feature/<feature-name>
# then create MR to develop
```

