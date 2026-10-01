# 📄 ResumeAI — AI Tailored Resume Generator & Career Suite 🚀

<p align="center">
  <strong>An intelligent, full-stack AI Resume Builder & Career Suite built with Python, Flask, MariaDB, Google Gemini, and Groq.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Flask-3.1-black?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/Google_Gemini-GenAI-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Gemini">
  <img src="https://img.shields.io/badge/Groq-Llama_/_Mistral-F55036?style=for-the-badge" alt="Groq">
  <img src="https://img.shields.io/badge/MariaDB-Database-003545?style=for-the-badge&logo=mariadb&logoColor=white" alt="MariaDB">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License">
</p>

---

## 🌟 Overview

**ResumeAI** is an all-in-one AI career suite designed to empower job seekers. From parsing existing resumes (PDF/DOCX/TXT) to tailoring bullet points against specific job descriptions using Google's X-Y-Z formula, ResumeAI automates the entire application preparation pipeline: ATS resume generation, cover letters, STAR interview kits, and application tracking.

---

## ✨ Features

### 1. 👤 User Accounts & Data Isolation
- Secure user registration, password hashing (`werkzeug.security`), and session management.
- Multi-user support with data isolation in MariaDB.
- Forgot & Reset password workflows with time-limited tokens.

### 2. 🗂️ Master Profile Inventory & Smart Resume Parser
- Maintain your unified career inventory: Contact info, social links (LinkedIn, GitHub, Portfolio), master summaries, work experiences, education, projects, and certifications.
- **Resume Importer**: Upload `.pdf`, `.docx`, or `.txt` resumes; AI parses and populates your Master Profile automatically.
- One-click **Demo Profile Loader** for quick testing.

### 3. 🤖 Dual AI Model Engine (Gemini & Groq)
- **Google Gemini**: Gemini 3.6 Flash, Gemini 3.7 Flash, Gemini 3.5 Flash.
- **Groq Cloud**: Ultra-fast LLM inference.
- Bring Your Own Key (BYOK) per user or server-level fallback defaults.

### 4. 🎯 Job Description Tailoring & ATS Scoring
- Deep analysis comparing your master profile against target Job Descriptions (JD).
- Aligns bullet points using Google's formula: *Accomplished [X] as measured by [Y], by doing [Z]*.
- Computes comprehensive ATS Match Score (0–100%), matched keywords, and gap recommendations.

### 5. ✉️ AI Cover Letter Generator
- Crafts compelling, highly targeted cover letters tailored to the company, role, and resume achievements.
- Multiple tones: *Professional & Persuasive*, *Modern & Engaging*, *Executive & Strategic*, *Concise & Direct*.
- Direct export to **PDF** and **Microsoft Word (.docx)**.

### 6. 🎙️ AI Interview Prep Kit (STAR Framework)
- 60-second *"Tell Me About Yourself"* elevator pitch tailored to the target role.
- Technical and architectural probe questions with suggested answers.
- Behavioral questions mapped directly to the **STAR method** (*Situation, Task, Action, Result*).
- Strategic questions to ask the interview panel.

### 7. ✍️ In-Line AI Bullet Point Re-Writer
- In-place bullet transformer with pre-set modes: *Google X-Y-Z*, *Add Metrics / %*, *Power Verbs*, *Punchy 1-Line*, *Leadership Tone*.

### 8. 📊 ATS & Readability Analytics
- Readability scoring based on bullet word counts and clarity.
- Detection of corporate clichés, overused buzzwords, and weak verbs.
- Passive voice identification and active voice recommendations.

### 9. 🎨 Multi-Template & Multi-Format Export
- **PDF Export** powered by WeasyPrint with 4 distinct themes:
  - *Modern Blue* (ATS Optimized)
  - *Executive Serif* (Classic & Formal)
  - *Creative Sidebar* (Two-column layout)
  - *Tech Terminal* (Developer & Systems oriented)
- Custom accent colors with dynamic palette picker.
- **1-Page Fit Mode**: Automatic dynamic scaling to guarantee single-page layouts.
- **Export formats**: PDF (`.pdf`), Microsoft Word (`.docx`), Markdown (`.md`), and JSON (`.json`).

### 10. 🔗 Public Shareable Web Resumes
- Generate unique shareable web links (`/r/<share_token>`) with printable views.
- Embedded scannable QR codes linking directly to your live portfolio.

### 11. 📋 Job Application CRM (Pipeline Tracker)
- Built-in Kanban pipeline tracker: *Saved*, *Applied*, *Interviewing*, *Offered*, *Rejected*.
- Associate applications directly with tailored resumes, salary notes, and deadlines.

---

## 📂 Project Architecture

```
resume-builder/
├── app.py               # Main Flask application and REST routes
├── ai_service.py        # Gemini & Groq AI generation and ATS scoring engine
├── db.py                # MariaDB connection pooling, schema migrations, queries
├── pdf_service.py       # WeasyPrint PDF renderer, dynamic CSS themes, QR codes
├── doc_service.py       # DOCX document generation with styling and formatting
├── email_service.py     # Password reset email delivery engine
├── test_suite.py        # Comprehensive unit & integration test suite
├── requirements.txt     # Python package dependencies
├── .env.example         # Template environment configuration
├── static/              # Frontend styles, client JS, brand assets
│   ├── css/
│   └── js/
└── templates/           # Jinja2 HTML templates
    ├── base.html
    ├── dashboard.html
    ├── generate.html
    ├── profile.html
    ├── resumes_list.html
    ├── edit_resume.html
    ├── view_resume.html
    ├── public_resume.html
    ├── applications.html
    ├── settings.html
    ├── login.html
    ├── register.html
    ├── forgot_password.html
    └── reset_password.html
```

---

## 🛠️ Installation & Quickstart

### 1. Prerequisites
- Python 3.10+
- MariaDB or MySQL 8.0+
- System libraries for WeasyPrint (e.g. `libpango-1.0-0`, `libcairo2`, `libgdk-pixbuf-2.0-0`)

### 2. Clone the Repository
```bash
git clone https://github.com/ShriyashBPatil/resume-builder.git
cd resume-builder
```

### 3. Setup Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
```
Update `.env` with your MariaDB connection details and optional Gemini/Groq API keys:
```ini
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=resume_builder
PORT=9999
SECRET_KEY=your_secret_key
```

### 5. Run the Application
```bash
python3 app.py
```
Open `http://localhost:9999` in your web browser.

---

## 🧪 Running Tests

Run the complete test suite:
```bash
python3 test_suite.py
```

---

## 📜 License

Distributed under the **MIT License**.

---

## 👨‍💻 Author

**SHRIYASH PATIL**
- GitHub: [@ShriyashBPatil](https://github.com/ShriyashBPatil)
- Website: [shriyashpatil.in](https://shriyashpatil.in)
