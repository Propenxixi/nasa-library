# Backend Development Guide

Library Information System & Digital Literacy Platform
SMAN 61 Jakarta

## 1. Purpose of This Document

This document serves as a **shared development guideline** for the backend team to ensure:

* Smooth collaboration within one repository
* Minimal merge conflicts
* Clear and consistent Git workflow
* Maintainable and scalable backend development

---

## 2. General Collaboration Principles

All team members **must follow these rules**:

* ❌ No direct push to `main`
* ❌ No direct push to `develop`
* ✅ All development must be done in feature branches
* ✅ All merges must go through **Merge Request (MR)**
* ✅ One feature per branch
* ✅ One person owns one feature branch at a time

These rules are mandatory to prevent conflicts and unstable code.

---

## 3. Repository & Branching Strategy

### 3.1 Main Branches

| Branch    | Purpose                                           |
| --------- | ------------------------------------------------- |
| `main`    | Stable version (final / demo / release-ready)     |
| `develop` | Active integration branch for backend development |

---

### 3.2 Feature Branches

All new work must be done in **feature branches** created from `develop`.

**Branch naming convention:**

```
feature/<feature-name>
```

**Examples:**

```
feature/book-management
feature/borrow-return
feature/literacy-review
feature-dashboard
```

---

## 4. Backend-First Development Flow

This flow **must be followed for every feature**.

---

### Step 0 – DONE BY CLARISSA

Performed once at the beginning:

* Django project initialized
* Initial commit pushed to `main`
* `develop` branch created from `main`

```
main
└── develop
```

---

### Step 1 – Create Feature Branch

Before starting any work:

```bash
git checkout develop
git pull origin develop
git checkout -b feature/<feature-name>
```

---

### Step 2 – Develop Feature Locally

While working on a feature:

* Only modify files related to your feature
* Do not refactor or touch unrelated code
* Follow Django layered architecture (Controller → Service → Repository)

If shared changes are needed (e.g. config), discuss with the team first.

---

### Step 3 – Commit Rules

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

### Step 4 – Create Merge Request (MR)

On GitLab:

* Source branch: `feature/<feature-name>`
* Target branch: `develop`
* Assign **at least one reviewer**
* Add a short description of what was implemented

**Before creating MR, ensure:**

* Application builds successfully
* No unnecessary files are committed

---

### Step 5 – Review & Merge

Reviewer responsibilities:

* Verify separation of layers
* Ensure no breaking changes

If approved, **merge into `develop`**.

---

### Step 6 – Merge to Main (Milestone Only)

Merge `develop` into `main` only when:

* A milestone is completed
* System is ready for demo or evaluation

```bash
git checkout main
git merge develop
git push origin main
```

---

## 5. Daily Development Workflow (Mandatory)

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

This ensures your branch stays updated and prevents large merge conflicts.

