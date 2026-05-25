# NASA Library 📚

> **Library Information System for SMAN 61 Jakarta**

NASA Library is a full-cycle library information system built for **SMAN 61 Jakarta** as a real client project. It digitizes and manages the school's entire library operation — from book cataloging and loans to student attendance and mandatory literacy programs — designed to sustain across annual school cycles and new student cohorts without manual re-setup.

---

## 👥 Team

| Name | Major | Faculty | University |
|---|---|---|---|
| Alisha Aline Athiyyah | Information Systems | Faculty of Computer Science | Universitas Indonesia |
| Clarissa Indriana Pramesti | Information Systems | Faculty of Computer Science | Universitas Indonesia |
| Nisa Najla Hanina Hasanah | Information Systems | Faculty of Computer Science | Universitas Indonesia |
| Naurah Iradya Kurniawan | Information Systems | Faculty of Computer Science | Universitas Indonesia |
| Samuel Sebastian Sibarani | Information Systems | Faculty of Computer Science | Universitas Indonesia |

---

## 🏫 Client

**SMAN 61 Jakarta** — a public senior high school in Jakarta. This system is deployed for the school's library staff and students, replacing manual record-keeping with a centralized digital platform.

---

## 🧠 What It Does

SMAN 61's library previously relied on manual logbooks for book loans, attendance, and literacy records — making year-end transitions and data retrieval slow and error-prone. NASA Library centralizes all of this into one system built to last beyond a single school year.

The system supports:

- **Book Repository** — full catalog management with search, cover image upload (Cloudinary), and availability tracking
- **Book Loan** — borrow and return workflow with due dates, loan history, and overdue tracking per student
- **Book Request** — students can submit requests for books not yet in the catalog
- **Attendance** — library visit attendance logging per student, tied to the school year cycle
- **Literacy Program** — manages the school's mandatory literacy activities, tracking participation and compliance per class and student
- **User Management** — role-based access for librarians, teachers, and students; supports annual student database rollover for new school year cycles
- **Dashboard** — summary view of active loans, attendance stats, and literacy program progress
- **Reports** — exportable reports for library staff and school administration
- **Recommendation** — book recommendations based on catalog data

---

## 🔄 Designed for Long-Term School Cycles

A core design requirement from the client: the system must continue working correctly when a new school year begins — new students enroll, graduating students archive, and all historical records remain intact.

This is handled through:
- School year–scoped data models (loans, attendance, and literacy records are tied to an academic year)
- Student cohort management that supports annual intake without wiping prior data
- Archival logic that preserves graduating student records while onboarding new ones

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django (Python) |
| Database | PostgreSQL |
| Media Storage | Cloudinary (book covers, profile pictures) |
| Frontend | Django Templates, HTML, CSS, JavaScript |
| Deployment (current) | Railway |
| Deployment (planned) | School's local server |

---

## 🗺️ Deployment Notes

The system is currently live on **Railway** connected to a PostgreSQL instance. A future migration to the school's **local server** is planned once the school's IT infrastructure is ready. The codebase is designed to be portable — switching from Railway to a local server requires only updating the environment variables and database connection string.

---

## 📄 License

Built as a client project for SMAN 61 Jakarta by a team from the Faculty of Computer Science, Universitas Indonesia. All rights reserved.
