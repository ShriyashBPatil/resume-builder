import os
import json
import uuid
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, send_file, Response, make_response
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import io
import markdown

from db import get_db, init_db, get_system_setting, set_system_setting, get_all_system_settings
from email_service import send_password_reset_email, send_welcome_email
from ai_service import (
    AVAILABLE_MODELS, generate_tailored_resume, json_to_markdown, ai_chat_assistant,
    generate_cover_letter, generate_interview_prep, parse_uploaded_resume_text,
    rewrite_bullet_point, analyze_resume_deep, get_groq_queue_status,
    get_ticket_queue_status, register_queue_ticket
)
from pdf_service import generate_pdf_from_resume_data, render_resume_html, TEMPLATES, FONTS
from doc_service import (
    extract_text_from_file, generate_docx_from_resume_data,
    generate_cover_letter_docx, generate_cover_letter_pdf, generate_qr_code_base64
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "resume_ai_secret_super_key_2026")

# Server base URL configuration (defaults to server.shriyashpatil.in:9999)
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://server.shriyashpatil.in:9999").rstrip('/')

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT is_admin, email FROM users WHERE id = %s", (session["user_id"],))
                user_record = cur.fetchone()
                if not user_record or (not user_record.get("is_admin") and user_record.get("email") != "app@shriyashpatil.in"):
                    flash("Access denied. Admin privileges required.", "danger")
                    return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function

# Context processor for user data
@app.context_processor
def inject_user():
    user = None
    is_admin = False
    if "user_id" in session:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, username, email, gemini_api_key, groq_api_key, preferred_model_provider, preferred_model, is_admin FROM users WHERE id = %s", (session["user_id"],))
                user = cur.fetchone()
                if user:
                    is_admin = bool(user.get("is_admin")) or user.get("email") == "app@shriyashpatil.in"
    return dict(current_user=user, is_admin=is_admin, available_models=AVAILABLE_MODELS)

# ---------- AUTH ROUTES ----------

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("register.html")

        password_hash = generate_password_hash(password)

        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)", (username, email, password_hash))
                    user_id = cur.lastrowid
                    
                    # Create empty profile
                    cur.execute("""
                        INSERT INTO profiles (user_id, full_name, email, skills, experiences, educations, projects, certifications, custom_sections)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        user_id, username, email,
                        json.dumps([]), json.dumps([]), json.dumps([]),
                        json.dumps([]), json.dumps([]), json.dumps([])
                    ))
            
            # Dispatch Welcome Email asynchronously or directly
            try:
                login_link = f"{APP_BASE_URL}/login"
                send_welcome_email(to_email=email, recipient_name=username, login_url=login_link)
            except Exception as mail_err:
                print(f"[WELCOME EMAIL ERROR] Could not dispatch welcome email to {email}: {mail_err}")

            flash("Registration successful! A welcome email has been sent. You can now log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash("Error registering user: Username or Email may already exist.", "danger")
            return render_template("register.html")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        login_id = request.form.get("login_id", "").strip()
        password = request.form.get("password", "")

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE username = %s OR email = %s", (login_id, login_id.lower()))
                user = cur.fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username/email or password.", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    
    simulated_link = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Please enter your account email address.", "danger")
            return render_template("forgot_password.html")

        user = None
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, username, email FROM users WHERE email = %s", (email,))
                user = cur.fetchone()

        if user:
            reset_token = uuid.uuid4().hex + uuid.uuid4().hex
            expires_at = datetime.utcnow() + timedelta(hours=1)

            with get_db() as conn:
                with conn.cursor() as cur:
                    # Invalidate old unused tokens for this user
                    cur.execute("UPDATE password_resets SET used = 1 WHERE user_id = %s", (user["id"],))
                    cur.execute("""
                        INSERT INTO password_resets (user_id, token, expires_at)
                        VALUES (%s, %s, %s)
                    """, (user["id"], reset_token, expires_at))

            reset_link = f"{APP_BASE_URL}/reset-password/{reset_token}"
            result = send_password_reset_email(to_email=user["email"], reset_link=reset_link, recipient_name=user["username"])

            if result.get("simulated"):
                simulated_link = reset_link
                flash(result["message"], "info")
            elif result.get("success"):
                flash(result["message"], "success")
                return redirect(url_for("login"))
            else:
                flash(result.get("error", "Failed to send reset email."), "danger")
        else:
            # Security best practice: generic notice or simulation notice
            flash(f"If an account with {email} exists, password reset instructions have been sent.", "info")

    return render_template("forgot_password.html", simulated_reset_link=simulated_link)

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pr.*, u.username, u.email 
                FROM password_resets pr
                JOIN users u ON pr.user_id = u.id
                WHERE pr.token = %s AND pr.used = 0 AND pr.expires_at > UTC_TIMESTAMP()
            """, (token,))
            reset_record = cur.fetchone()

    if not reset_record:
        flash("Invalid or expired password reset link. Please request a new one.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not new_password or len(new_password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("reset_password.html", token=token)

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("reset_password.html", token=token)

        password_hash = generate_password_hash(new_password)

        with get_db() as conn:
            with conn.cursor() as cur:
                # Update user password
                cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, reset_record["user_id"]))
                # Mark token as used
                cur.execute("UPDATE password_resets SET used = 1 WHERE id = %s", (reset_record["id"],))

        flash("Your password has been successfully updated! You can now sign in.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)

# ---------- ADMIN DASHBOARD & CONTROLS ----------

@app.route("/admin")
@admin_required
def admin_dashboard():
    with get_db() as conn:
        with conn.cursor() as cur:
            # 1. Platform Statistics
            cur.execute("SELECT COUNT(*) AS total FROM users")
            total_users = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM resumes")
            total_resumes = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM resumes WHERE is_public = 1")
            public_resumes = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM cover_letters")
            total_cover_letters = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM interview_preps")
            total_preps = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM job_applications")
            total_applications = cur.fetchone()["total"]

            # 2. Detailed Users List with their Resume Counts and Profile Photos
            cur.execute("""
                SELECT u.id, u.username, u.email, u.preferred_model_provider, u.preferred_model, u.is_admin, u.created_at,
                       p.profile_photo_url, p.full_name,
                       COUNT(r.id) AS resume_count
                FROM users u
                LEFT JOIN profiles p ON u.id = p.user_id
                LEFT JOIN resumes r ON u.id = r.user_id
                GROUP BY u.id
                ORDER BY u.created_at DESC
            """)
            users = cur.fetchall()

            # 3. Recent 10 Resumes across the platform
            cur.execute("""
                SELECT r.id, r.title, r.target_role, r.target_company, r.match_score, r.created_at, u.username
                FROM resumes r
                JOIN users u ON r.user_id = u.id
                ORDER BY r.created_at DESC
                LIMIT 10
            """)
            recent_resumes = cur.fetchall()

    stats = {
        "total_users": total_users,
        "total_resumes": total_resumes,
        "public_resumes": public_resumes,
        "total_cover_letters": total_cover_letters,
        "total_preps": total_preps,
        "total_applications": total_applications
    }

    universal_gemini_key = get_system_setting("universal_gemini_api_key", os.environ.get("GEMINI_API_KEY", ""))
    universal_groq_key = get_system_setting("universal_groq_api_key", os.environ.get("GROQ_API_KEY", ""))
    queue_status = get_groq_queue_status()

    return render_template(
        "admin_dashboard.html",
        stats=stats,
        users=users,
        recent_resumes=recent_resumes,
        queue_status=queue_status,
        admin_email="app@shriyashpatil.in",
        smtp_host=os.environ.get("SMTP_SERVER", "mail.shriyashpatil.in"),
        smtp_port=os.environ.get("SMTP_PORT", 465),
        universal_gemini_key=universal_gemini_key,
        universal_groq_key=universal_groq_key
    )

@app.route("/admin/settings/universal-keys", methods=["POST"])
@admin_required
def admin_update_universal_keys():
    universal_gemini_key = request.form.get("universal_gemini_api_key", "").strip()
    universal_groq_key = request.form.get("universal_groq_api_key", "").strip()

    set_system_setting("universal_gemini_api_key", universal_gemini_key, "Universal default Google Gemini API Key")
    if universal_groq_key:
        set_system_setting("universal_groq_api_key", universal_groq_key, "Universal default Groq Cloud API Key")

    flash("Platform Universal API Keys updated successfully!", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/api/queue/status")
@login_required
def api_queue_status():
    return jsonify(get_groq_queue_status())

@app.route("/api/queue/ticket/<ticket_id>")
@login_required
def api_ticket_status(ticket_id):
    return jsonify(get_ticket_queue_status(ticket_id))

@app.route("/api/queue/join", methods=["GET", "POST"])
@login_required
def api_queue_join():
    ticket_id = request.values.get("ticket_id", "").strip()
    if not ticket_id:
        ticket_id = f"tkt_{uuid.uuid4().hex[:12]}"
    status = register_queue_ticket(ticket_id)
    return jsonify(status)

@app.route("/admin/user/<int:user_id>/toggle-role", methods=["POST"])
@admin_required
def admin_toggle_user_role(user_id):
    if user_id == session["user_id"]:
        flash("You cannot modify your own administrative role.", "warning")
        return redirect(url_for("admin_dashboard"))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, email, is_admin FROM users WHERE id = %s", (user_id,))
            target_user = cur.fetchone()
            if not target_user:
                flash("User not found.", "danger")
                return redirect(url_for("admin_dashboard"))

            new_role = 0 if target_user.get("is_admin") else 1
            cur.execute("UPDATE users SET is_admin = %s WHERE id = %s", (new_role, user_id))

    role_str = "Admin" if new_role else "Standard User"
    flash(f"User '{target_user['username']}' role updated to {role_str}.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/user/<int:user_id>/send-reset", methods=["POST"])
@admin_required
def admin_send_reset(user_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, email FROM users WHERE id = %s", (user_id,))
            target_user = cur.fetchone()

    if not target_user:
        flash("User not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    reset_token = uuid.uuid4().hex + uuid.uuid4().hex
    expires_at = datetime.utcnow() + timedelta(hours=1)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE password_resets SET used = 1 WHERE user_id = %s", (user_id,))
            cur.execute("INSERT INTO password_resets (user_id, token, expires_at) VALUES (%s, %s, %s)", (user_id, reset_token, expires_at))

    reset_link = f"{APP_BASE_URL}/reset-password/{reset_token}"
    result = send_password_reset_email(to_email=target_user["email"], reset_link=reset_link, recipient_name=target_user["username"])

    if result.get("success"):
        flash(f"Password reset email sent to {target_user['email']}!", "success")
    else:
        flash(f"Failed to deliver reset email: {result.get('error')}", "danger")

    return redirect(url_for("admin_dashboard"))

@app.route("/admin/user/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_user_edit(user_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user_record = cur.fetchone()

    if not user_record:
        flash("User not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        action = request.form.get("action")

        # 1. Update Account Credentials / Admin Role
        if action == "update_credentials":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            new_password = request.form.get("new_password", "").strip()
            is_admin_val = 1 if request.form.get("is_admin") == "1" else 0

            if not username or not email:
                flash("Username and Email are required.", "danger")
                return redirect(url_for("admin_user_edit", user_id=user_id))

            with get_db() as conn:
                with conn.cursor() as cur:
                    if new_password:
                        pwd_hash = generate_password_hash(new_password)
                        cur.execute("""
                            UPDATE users SET username = %s, email = %s, is_admin = %s, password_hash = %s
                            WHERE id = %s
                        """, (username, email, is_admin_val, pwd_hash, user_id))
                    else:
                        cur.execute("""
                            UPDATE users SET username = %s, email = %s, is_admin = %s
                            WHERE id = %s
                        """, (username, email, is_admin_val, user_id))

            flash(f"User credentials for '{username}' updated successfully!", "success")
            return redirect(url_for("admin_user_edit", user_id=user_id))

        # 2. Update Master Profile Data
        elif action == "update_profile":
            full_name = request.form.get("full_name", "").strip()
            professional_title = request.form.get("professional_title", "").strip()
            phone = request.form.get("phone", "").strip()
            location = request.form.get("location", "").strip()
            linkedin_url = request.form.get("linkedin_url", "").strip()
            github_url = request.form.get("github_url", "").strip()
            summary = request.form.get("summary", "").strip()
            profile_photo_url = request.form.get("profile_photo_url", "").strip()
            skills_str = request.form.get("skills_str", "").strip()
            skills_list = [s.strip() for s in skills_str.split(",") if s.strip()]

            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO profiles (
                            user_id, full_name, professional_title, phone, location,
                            linkedin_url, github_url, profile_photo_url, summary, skills
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            full_name=VALUES(full_name),
                            professional_title=VALUES(professional_title),
                            phone=VALUES(phone),
                            location=VALUES(location),
                            linkedin_url=VALUES(linkedin_url),
                            github_url=VALUES(github_url),
                            profile_photo_url=VALUES(profile_photo_url),
                            summary=VALUES(summary),
                            skills=VALUES(skills)
                    """, (
                        user_id, full_name, professional_title, phone, location,
                        linkedin_url, github_url, profile_photo_url, summary, json.dumps(skills_list)
                    ))

            flash(f"Master Profile data for '{user_record['username']}' updated successfully!", "success")
            return redirect(url_for("admin_user_edit", user_id=user_id))

    # GET Request: Fetch Profile & Resumes
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profiles WHERE user_id = %s", (user_id,))
            profile_record = cur.fetchone() or {}

            if profile_record.get("skills") and isinstance(profile_record["skills"], str):
                try:
                    profile_record["skills"] = json.loads(profile_record["skills"])
                except Exception:
                    profile_record["skills"] = []
            elif not profile_record.get("skills"):
                profile_record["skills"] = []

            cur.execute("""
                SELECT id, title, target_role, target_company, template_name, match_score, is_public, created_at 
                FROM resumes 
                WHERE user_id = %s 
                ORDER BY created_at DESC
            """, (user_id,))
            user_resumes = cur.fetchall()

    return render_template(
        "admin_user_edit.html",
        user=user_record,
        profile=profile_record,
        resumes=user_resumes
    )

@app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    if user_id == session["user_id"]:
        flash("You cannot delete your own active administrator account.", "danger")
        return redirect(url_for("admin_dashboard"))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, email FROM users WHERE id = %s", (user_id,))
            target_user = cur.fetchone()
            if not target_user:
                flash("User not found.", "danger")
                return redirect(url_for("admin_dashboard"))

            if target_user["email"] == "app@shriyashpatil.in":
                flash("Primary super administrator account cannot be deleted.", "danger")
                return redirect(url_for("admin_dashboard"))

            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))

    flash(f"User account '{target_user['username']}' and all associated resumes have been permanently deleted.", "info")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/resume/<int:resume_id>/delete", methods=["POST"])
@admin_required
def admin_delete_resume(resume_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, user_id FROM resumes WHERE id = %s", (resume_id,))
            resume_record = cur.fetchone()
            if not resume_record:
                flash("Resume not found.", "danger")
                return redirect(url_for("admin_dashboard"))

            cur.execute("DELETE FROM resumes WHERE id = %s", (resume_id,))

    flash(f"Resume '{resume_record['title']}' deleted successfully.", "info")
    return redirect(url_for("admin_user_edit", user_id=resume_record["user_id"]))

# ---------- DASHBOARD & GENERATOR ----------

@app.route("/dashboard")
@login_required
def dashboard():
    with get_db() as conn:
        with conn.cursor() as cur:
            # Get profile info
            cur.execute("SELECT * FROM profiles WHERE user_id = %s", (session["user_id"],))
            profile = cur.fetchone() or {}
            
            # Parse json fields safely
            for field in ['skills', 'experiences', 'educations', 'projects', 'certifications', 'custom_sections']:
                if profile.get(field) and isinstance(profile[field], str):
                    try:
                        profile[field] = json.loads(profile[field])
                    except Exception:
                        profile[field] = []

            # Get recent resumes
            cur.execute("""
                SELECT id, title, target_role, target_company, provider_used, model_used, match_score, is_public, share_token, created_at 
                FROM resumes WHERE user_id = %s ORDER BY created_at DESC LIMIT 10
            """, (session["user_id"],))
            resumes = cur.fetchall()

            # Get application pipeline counts
            cur.execute("""
                SELECT status, COUNT(*) as count FROM job_applications 
                WHERE user_id = %s GROUP BY status
            """, (session["user_id"],))
            app_stats_rows = cur.fetchall()
            app_stats = {r["status"]: r["count"] for r in app_stats_rows}
            total_apps = sum(app_stats.values())

    return render_template(
        "dashboard.html",
        profile=profile,
        resumes=resumes,
        app_stats=app_stats,
        total_apps=total_apps
    )

# ---------- PROFILE MANAGEMENT & RESUME IMPORTER ----------

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = session["user_id"]
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        professional_title = request.form.get("professional_title", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        location = request.form.get("location", "").strip()
        linkedin_url = request.form.get("linkedin_url", "").strip()
        github_url = request.form.get("github_url", "").strip()
        portfolio_url = request.form.get("portfolio_url", "").strip()
        summary = request.form.get("summary", "").strip()

        profile_photo_url = request.form.get("profile_photo_url", "").strip()

        # Complex structured fields from forms / json
        skills_raw = request.form.get("skills_json", "[]")
        experiences_raw = request.form.get("experiences_json", "[]")
        educations_raw = request.form.get("educations_json", "[]")
        projects_raw = request.form.get("projects_json", "[]")
        certifications_raw = request.form.get("certifications_json", "[]")
        custom_sections_raw = request.form.get("custom_sections_json", "[]")

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO profiles (
                        user_id, full_name, professional_title, email, phone, location,
                        linkedin_url, github_url, portfolio_url, profile_photo_url, summary,
                        skills, experiences, educations, projects, certifications, custom_sections
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        full_name=VALUES(full_name),
                        professional_title=VALUES(professional_title),
                        email=VALUES(email),
                        phone=VALUES(phone),
                        location=VALUES(location),
                        linkedin_url=VALUES(linkedin_url),
                        github_url=VALUES(github_url),
                        portfolio_url=VALUES(portfolio_url),
                        profile_photo_url=VALUES(profile_photo_url),
                        summary=VALUES(summary),
                        skills=VALUES(skills),
                        experiences=VALUES(experiences),
                        educations=VALUES(educations),
                        projects=VALUES(projects),
                        certifications=VALUES(certifications),
                        custom_sections=VALUES(custom_sections)
                """, (
                    user_id, full_name, professional_title, email, phone, location,
                    linkedin_url, github_url, portfolio_url, profile_photo_url, summary,
                    skills_raw, experiences_raw, educations_raw, projects_raw, certifications_raw, custom_sections_raw
                ))
        
        flash("Master Profile updated successfully!", "success")
        return redirect(url_for("profile"))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profiles WHERE user_id = %s", (user_id,))
            profile = cur.fetchone() or {}
            
            for field in ['skills', 'experiences', 'educations', 'projects', 'certifications', 'custom_sections']:
                if profile.get(field):
                    if isinstance(profile[field], str):
                        try:
                            profile[field] = json.loads(profile[field])
                        except Exception:
                            profile[field] = []
                else:
                    profile[field] = []

    return render_template("profile.html", profile=profile)

@app.route("/api/import-resume", methods=["POST"])
@login_required
def api_import_resume():
    """Upload existing PDF/DOCX/TXT resume -> Extract text -> AI parse into Master Profile."""
    user_id = session["user_id"]
    if "resume_file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    file = request.files["resume_file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "No file selected."}), 400

    filename = secure_filename(file.filename)
    try:
        raw_text = extract_text_from_file(io.BytesIO(file.read()), filename)
        if not raw_text.strip():
            return jsonify({"success": False, "error": "Could not extract any readable text from document."}), 400

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT gemini_api_key, groq_api_key, preferred_model_provider, preferred_model FROM users WHERE id = %s", (user_id,))
                user_config = cur.fetchone() or {}

        provider = user_config.get("preferred_model_provider", "gemini")
        model_name = user_config.get("preferred_model", "gemini-3.6-flash")
        api_key = user_config.get(f"{provider}_api_key")

        parsed_profile = parse_uploaded_resume_text(
            provider=provider,
            model_name=model_name,
            user_api_key=api_key,
            raw_resume_text=raw_text
        )

        # Save parsed data to DB
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO profiles (
                        user_id, full_name, professional_title, email, phone, location,
                        linkedin_url, github_url, portfolio_url, summary,
                        skills, experiences, educations, projects, certifications, custom_sections
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        full_name=VALUES(full_name),
                        professional_title=VALUES(professional_title),
                        email=VALUES(email),
                        phone=VALUES(phone),
                        location=VALUES(location),
                        linkedin_url=VALUES(linkedin_url),
                        github_url=VALUES(github_url),
                        portfolio_url=VALUES(portfolio_url),
                        summary=VALUES(summary),
                        skills=VALUES(skills),
                        experiences=VALUES(experiences),
                        educations=VALUES(educations),
                        projects=VALUES(projects),
                        certifications=VALUES(certifications),
                        custom_sections=VALUES(custom_sections)
                """, (
                    user_id,
                    parsed_profile.get("full_name", ""),
                    parsed_profile.get("professional_title", ""),
                    parsed_profile.get("email", ""),
                    parsed_profile.get("phone", ""),
                    parsed_profile.get("location", ""),
                    parsed_profile.get("linkedin_url", ""),
                    parsed_profile.get("github_url", ""),
                    parsed_profile.get("portfolio_url", ""),
                    parsed_profile.get("summary", ""),
                    json.dumps(parsed_profile.get("skills", [])),
                    json.dumps(parsed_profile.get("experiences", [])),
                    json.dumps(parsed_profile.get("educations", [])),
                    json.dumps(parsed_profile.get("projects", [])),
                    json.dumps(parsed_profile.get("certifications", [])),
                    json.dumps(parsed_profile.get("custom_sections", []))
                ))

        return jsonify({
            "success": True,
            "message": "Resume document parsed and imported into your Master Profile!",
            "profile": parsed_profile
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/rewrite-bullet", methods=["POST"])
@login_required
def api_rewrite_bullet():
    """Rewrite a single bullet point using AI."""
    user_id = session["user_id"]
    data = request.get_json() or {}
    bullet_text = data.get("bullet_text", "").strip()
    mode = data.get("mode", "xyz")
    custom_instruction = data.get("custom_instruction", "").strip()
    req_provider = data.get("provider", "").strip().lower()
    req_model = data.get("model", "").strip()

    if not bullet_text:
        return jsonify({"success": False, "error": "Bullet text is required."}), 400

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT gemini_api_key, groq_api_key, preferred_model_provider, preferred_model, is_admin FROM users WHERE id = %s", (user_id,))
            user_config = cur.fetchone() or {}

    provider = req_provider or user_config.get("preferred_model_provider", "gemini")
    model_name = req_model or user_config.get("preferred_model", "gemini-3.6-flash")
    api_key = user_config.get(f"{provider}_api_key")
    is_admin = bool(user_config.get("is_admin", 0))

    try:
        rewritten = rewrite_bullet_point(
            provider=provider,
            model_name=model_name,
            user_api_key=api_key,
            bullet_text=bullet_text,
            mode=mode,
            custom_instruction=custom_instruction,
            is_admin=is_admin
        )
        return jsonify({"success": True, "rewritten": rewritten})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ---------- API KEYS & SETTINGS ----------

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user_id = session["user_id"]
    if request.method == "POST":
        gemini_api_key = request.form.get("gemini_api_key", "").strip()
        groq_api_key = request.form.get("groq_api_key", "").strip()
        preferred_provider = request.form.get("preferred_model_provider", "gemini")
        preferred_model = request.form.get("preferred_model", "gemini-3.6-flash")

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users SET 
                        gemini_api_key = %s,
                        groq_api_key = %s,
                        preferred_model_provider = %s,
                        preferred_model = %s
                    WHERE id = %s
                """, (
                    gemini_api_key if gemini_api_key else None,
                    groq_api_key if groq_api_key else None,
                    preferred_provider,
                    preferred_model,
                    user_id
                ))
        flash("Settings and API keys updated successfully!", "success")
        return redirect(url_for("settings"))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT username, email, gemini_api_key, groq_api_key, preferred_model_provider, preferred_model FROM users WHERE id = %s", (user_id,))
            user = cur.fetchone()

    return render_template("settings.html", user=user)

# ---------- RESUME GENERATION ----------

@app.route("/generate", methods=["GET", "POST"])
@login_required
def generate():
    user_id = session["user_id"]
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profiles WHERE user_id = %s", (user_id,))
            profile_record = cur.fetchone() or {}
            
            cur.execute("SELECT email, gemini_api_key, groq_api_key, preferred_model_provider, preferred_model, is_admin FROM users WHERE id = %s", (user_id,))
            user_config = cur.fetchone() or {}

    is_admin = bool(user_config.get("is_admin")) or user_config.get("email") == "app@shriyashpatil.in"

    if request.method == "POST":
        job_description = request.form.get("job_description", "").strip()
        custom_instructions = request.form.get("custom_instructions", "").strip()
        provider = request.form.get("provider", user_config.get("preferred_model_provider", "gemini"))
        model_name = request.form.get("model_name", user_config.get("preferred_model", "gemini-3.6-flash"))
        custom_key = request.form.get("custom_api_key", "").strip()
        queue_ticket_id = request.form.get("queue_ticket_id", "").strip()

        # Check if master profile is empty
        has_profile_info = bool(profile_record.get("full_name") or profile_record.get("summary") or (profile_record.get("skills") and profile_record.get("skills") != "[]"))
        if not has_profile_info:
            flash("Your Master Profile is empty. Please fill in your profile details first so the AI can tailor your resume.", "warning")
            return redirect(url_for("profile"))

        if not job_description:
            flash("Job Description is required to generate a tailored resume.", "danger")
            return redirect(url_for("generate"))

        active_key = custom_key
        if not active_key:
            if provider == "gemini":
                active_key = user_config.get("gemini_api_key")
            elif provider == "groq":
                active_key = user_config.get("groq_api_key")

        profile_clean = dict(profile_record)
        profile_clean.pop('updated_at', None)
        profile_clean.pop('created_at', None)
        profile_clean.pop('id', None)
        profile_clean.pop('user_id', None)

        for field in ['skills', 'experiences', 'educations', 'projects', 'certifications', 'custom_sections']:
            if profile_clean.get(field) and isinstance(profile_clean[field], str):
                try:
                    profile_clean[field] = json.loads(profile_clean[field])
                except Exception:
                    profile_clean[field] = []

        try:
            parsed_json, raw_text = generate_tailored_resume(
                provider=provider,
                model_name=model_name,
                user_api_key=active_key,
                profile_data=profile_clean,
                job_description=job_description,
                additional_notes=custom_instructions,
                queue_ticket_id=queue_ticket_id,
                is_admin=is_admin
            )

            target_role = parsed_json.get("target_role", "Tailored Resume")
            target_company = parsed_json.get("target_company", "")
            match_score = parsed_json.get("match_score", 85)
            match_analysis = parsed_json.get("match_analysis", {})
            title = f"{target_role}" + (f" at {target_company}" if target_company else "")
            
            # Inject photo_url from profile into personal_info if present and not yet set
            if profile_record.get("profile_photo_url"):
                if "resume" in parsed_json and "personal_info" in parsed_json["resume"]:
                    if not parsed_json["resume"]["personal_info"].get("photo_url"):
                        parsed_json["resume"]["personal_info"]["photo_url"] = profile_record["profile_photo_url"]
                elif "personal_info" in parsed_json:
                    if not parsed_json["personal_info"].get("photo_url"):
                        parsed_json["personal_info"]["photo_url"] = profile_record["profile_photo_url"]

            markdown_content = json_to_markdown(parsed_json)
            share_token = uuid.uuid4().hex[:16]

            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO resumes (
                            user_id, title, target_role, target_company, job_description,
                            model_used, provider_used, generated_json, generated_markdown,
                            match_score, match_analysis, share_token, include_qr, include_photo
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        user_id, title, target_role, target_company, job_description,
                        model_name, provider, json.dumps(parsed_json), markdown_content,
                        match_score, json.dumps(match_analysis), share_token, 1, 1
                    ))
                    new_resume_id = cur.lastrowid

            flash("Resume generated and optimized successfully!", "success")
            return redirect(url_for("view_resume", resume_id=new_resume_id))

        except Exception as e:
            flash(f"AI Generation failed: {str(e)}", "danger")
            return render_template(
                "generate.html",
                profile=profile_record,
                user_config=user_config,
                job_description=job_description,
                custom_instructions=custom_instructions,
                selected_provider=provider,
                selected_model=model_name
            )

    return render_template(
        "generate.html",
        profile=profile_record,
        user_config=user_config,
        selected_provider=user_config.get("preferred_model_provider", "gemini"),
        selected_model=user_config.get("preferred_model", "gemini-3.6-flash")
    )

@app.route("/build-manual", methods=["GET", "POST"])
@login_required
def build_manual():
    user_id = session["user_id"]

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profiles WHERE user_id = %s", (user_id,))
            profile_record = cur.fetchone() or {}

    profile_clean = dict(profile_record)
    for field in ['skills', 'experiences', 'educations', 'projects', 'certifications', 'custom_sections']:
        if profile_clean.get(field) and isinstance(profile_clean[field], str):
            try:
                profile_clean[field] = json.loads(profile_clean[field])
            except Exception:
                profile_clean[field] = []

    if request.method == "POST":
        template_name = request.form.get("template_name", "modern")
        accent_color = request.form.get("accent_color", "#2563eb")
        font_name = request.form.get("font_name", "inter")
        single_page_mode = 1 if request.form.get("single_page_mode") == "1" else 0
        include_qr_val = 1 if request.form.get("include_qr", "1") == "1" else 0
        include_photo_val = 1 if request.form.get("include_photo", "1") == "1" else 0
        title = request.form.get("title", "").strip() or "Standard Resume"
        target_role = request.form.get("target_role", "").strip() or profile_clean.get("professional_title", "")

        # Check if edited JSON was submitted directly
        edited_json_str = request.form.get("edited_resume_json", "").strip()
        if edited_json_str:
            try:
                full_payload = json.loads(edited_json_str)
            except Exception:
                full_payload = None
        else:
            full_payload = None

        if not full_payload:
            resume_obj = {
                "personal_info": {
                    "full_name": profile_clean.get("full_name", "Your Name"),
                    "professional_title": target_role or profile_clean.get("professional_title", ""),
                    "email": profile_clean.get("email", ""),
                    "phone": profile_clean.get("phone", ""),
                    "location": profile_clean.get("location", ""),
                    "linkedin_url": profile_clean.get("linkedin_url", ""),
                    "github_url": profile_clean.get("github_url", ""),
                    "portfolio_url": profile_clean.get("portfolio_url", ""),
                    "photo_url": profile_clean.get("profile_photo_url", "")
                },
                "summary": profile_clean.get("summary", ""),
                "core_competencies": profile_clean.get("skills", []),
                "experience": profile_clean.get("experiences", []),
                "education": profile_clean.get("educations", []),
                "projects": profile_clean.get("projects", []),
                "certifications": profile_clean.get("certifications", []),
                "custom_sections": profile_clean.get("custom_sections", [])
            }

            full_payload = {
                "target_role": target_role,
                "target_company": "",
                "match_score": 100,
                "match_analysis": {
                    "strengths": ["Built directly with manual editor without AI alterations"],
                    "keyword_matches": profile_clean.get("skills", []),
                    "missing_or_recommended_skills": [],
                    "ats_tips": ["Review bullet points for quantified metrics before submitting."]
                },
                "resume": resume_obj
            }

        markdown_content = json_to_markdown(full_payload)
        share_token = uuid.uuid4().hex[:16]

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO resumes (
                        user_id, title, target_role, target_company, job_description,
                        model_used, provider_used, template_name, custom_accent_color, custom_font, single_page_mode,
                        include_qr, include_photo,
                        generated_json, generated_markdown, match_score, match_analysis, share_token
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id, title, target_role, "", "Built with Direct Builder & Live Editor",
                    "manual", "none", template_name, accent_color, font_name, single_page_mode,
                    include_qr_val, include_photo_val,
                    json.dumps(full_payload), markdown_content,
                    100, json.dumps(full_payload.get("match_analysis", {})), share_token
                ))
                new_resume_id = cur.lastrowid

        flash("Resume built and saved successfully!", "success")
        return redirect(url_for("view_resume", resume_id=new_resume_id, template=template_name, accent_color=accent_color, font=font_name, single_page=single_page_mode, qr=include_qr_val, photo=include_photo_val))

    selected_template = request.args.get("template", "modern")
    selected_font = request.args.get("font", "inter")
    return render_template(
        "build_manual.html",
        profile=profile_clean,
        templates=TEMPLATES,
        fonts=FONTS,
        selected_template=selected_template,
        selected_font=selected_font
    )

# ---------- VIEW / EDIT / DOWNLOAD RESUME ----------

@app.route("/resumes")
@login_required
def resumes_list():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, target_role, target_company, provider_used, model_used, match_score, is_public, share_token, created_at 
                FROM resumes WHERE user_id = %s ORDER BY created_at DESC
            """, (session["user_id"],))
            resumes = cur.fetchall()
    return render_template("resumes_list.html", resumes=resumes)

@app.route("/resume/<int:resume_id>")
@login_required
def view_resume(resume_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM resumes WHERE id = %s AND user_id = %s", (resume_id, session["user_id"]))
            resume = cur.fetchone()

            # Check if cover letter exists for this resume
            cur.execute("SELECT * FROM cover_letters WHERE resume_id = %s AND user_id = %s ORDER BY id DESC LIMIT 1", (resume_id, session["user_id"]))
            cover_letter = cur.fetchone()

            # Check if interview prep exists for this resume
            cur.execute("SELECT * FROM interview_preps WHERE resume_id = %s AND user_id = %s ORDER BY id DESC LIMIT 1", (resume_id, session["user_id"]))
            interview_prep = cur.fetchone()

    if not resume:
        flash("Resume not found.", "danger")
        return redirect(url_for("dashboard"))

    # Auto-heal share_token if not set
    if not resume.get("share_token"):
        new_token = uuid.uuid4().hex[:16]
        resume["share_token"] = new_token
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE resumes SET share_token = %s WHERE id = %s", (new_token, resume_id))

    if isinstance(resume["generated_json"], str):
        resume["generated_json"] = json.loads(resume["generated_json"])
    if resume.get("match_analysis") and isinstance(resume["match_analysis"], str):
        resume["match_analysis"] = json.loads(resume["match_analysis"])

    if interview_prep and isinstance(interview_prep["qa_data"], str):
        interview_prep["qa_data"] = json.loads(interview_prep["qa_data"])

    # Deep ATS & readability analysis
    deep_analysis = analyze_resume_deep(resume["generated_json"], resume.get("job_description", ""))

    selected_template = request.args.get("template", resume.get("template_name", "modern"))
    accent_color = request.args.get("accent_color", resume.get("custom_accent_color", "#2563eb"))
    selected_font = request.args.get("font", resume.get("custom_font", "inter"))
    single_page = request.args.get("single_page", str(resume.get("single_page_mode", 0))) == "1"
    
    # QR & Photo toggles: default to resume db field if not specified in request args
    default_include_qr = resume.get("include_qr", 1) if resume.get("include_qr") is not None else 1
    default_include_photo = resume.get("include_photo", 1) if resume.get("include_photo") is not None else 1
    
    include_qr = request.args.get("qr", str(default_include_qr)) == "1"
    include_photo = request.args.get("photo", str(default_include_photo)) == "1"

    # Compute QR target URL
    qr_target_url = ""
    if resume.get("share_token"):
        qr_target_url = request.host_url.rstrip('/') + url_for('public_resume_view', share_token=resume['share_token'])
    else:
        # Fallback to portfolio or linkedin URL if available
        raw_info = resume["generated_json"].get("resume", resume["generated_json"]).get("personal_info", {})
        qr_target_url = raw_info.get("portfolio_url") or raw_info.get("linkedin_url") or raw_info.get("github_url") or ""

    # Extract photo URL if present
    raw_info = resume["generated_json"].get("resume", resume["generated_json"]).get("personal_info", {})
    photo_url = raw_info.get("photo_url", "")

    # Render high-fidelity styled template HTML matching PDF output
    rendered_styled_html = render_resume_html(
        resume_payload=resume["generated_json"],
        template_name=selected_template,
        accent_color=accent_color,
        font_name=selected_font,
        single_page=single_page,
        include_qr=include_qr,
        qr_target_url=qr_target_url,
        include_photo=include_photo,
        photo_url=photo_url
    )

    return render_template(
        "view_resume.html",
        resume=resume,
        rendered_styled_html=rendered_styled_html,
        templates=TEMPLATES,
        fonts=FONTS,
        selected_template=selected_template,
        selected_font=selected_font,
        accent_color=accent_color,
        single_page=single_page,
        include_qr=include_qr,
        include_photo=include_photo,
        cover_letter=cover_letter,
        interview_prep=interview_prep,
        deep_analysis=deep_analysis
    )

@app.route("/resume/<int:resume_id>/edit", methods=["GET", "POST"])
@login_required
def edit_resume(resume_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM resumes WHERE id = %s AND user_id = %s", (resume_id, session["user_id"]))
            resume = cur.fetchone()

    if not resume:
        flash("Resume not found.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        json_content_raw = request.form.get("json_content", "").strip()
        markdown_content = request.form.get("markdown_content", "").strip()

        try:
            parsed_json = json.loads(json_content_raw)
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE resumes SET 
                            title = %s,
                            generated_json = %s,
                            generated_markdown = %s
                        WHERE id = %s AND user_id = %s
                    """, (title, json.dumps(parsed_json), markdown_content, resume_id, session["user_id"]))
            flash("Resume saved successfully!", "success")
            return redirect(url_for("view_resume", resume_id=resume_id))
        except Exception as e:
            flash(f"Failed to update resume: Invalid JSON data. {str(e)}", "danger")

    if isinstance(resume["generated_json"], str):
        resume["generated_json"] = json.loads(resume["generated_json"])

    return render_template("edit_resume.html", resume=resume, json_pretty=json.dumps(resume["generated_json"], indent=2))

@app.route("/resume/<int:resume_id>/delete", methods=["POST"])
@login_required
def delete_resume(resume_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM resumes WHERE id = %s AND user_id = %s", (resume_id, session["user_id"]))
    flash("Resume deleted successfully.", "info")
    return redirect(url_for("resumes_list"))

# ---------- EXPORT RESUME (PDF, DOCX, MD, JSON) ----------

@app.route("/resume/<int:resume_id>/download/pdf")
@login_required
def download_pdf(resume_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM resumes WHERE id = %s AND user_id = %s", (resume_id, session["user_id"]))
            resume = cur.fetchone()

    if not resume:
        flash("Resume not found.", "danger")
        return redirect(url_for("dashboard"))

    payload = resume["generated_json"]
    if isinstance(payload, str):
        payload = json.loads(payload)

    selected_template = request.args.get("template", resume.get("template_name", "modern"))
    accent_color = request.args.get("accent_color", resume.get("custom_accent_color", "#2563eb"))
    font_name = request.args.get("font", resume.get("custom_font", "inter"))
    single_page = request.args.get("single_page", str(resume.get("single_page_mode", 0))) == "1"
    
    default_include_qr = resume.get("include_qr", 1) if resume.get("include_qr") is not None else 1
    default_include_photo = resume.get("include_photo", 1) if resume.get("include_photo") is not None else 1
    
    include_qr = request.args.get("qr", str(default_include_qr)) == "1"
    include_photo = request.args.get("photo", str(default_include_photo)) == "1"
    
    qr_url = ""
    if include_qr:
        if resume.get("share_token"):
            qr_url = request.host_url.rstrip('/') + url_for('public_resume_view', share_token=resume['share_token'])
        else:
            raw_info = payload.get("resume", payload).get("personal_info", {})
            qr_url = raw_info.get("portfolio_url") or raw_info.get("linkedin_url") or raw_info.get("github_url") or ""

    raw_info = payload.get("resume", payload).get("personal_info", {})
    photo_url = raw_info.get("photo_url", "")

    pdf_data = generate_pdf_from_resume_data(
        resume_payload=payload,
        template_name=selected_template,
        accent_color=accent_color,
        font_name=font_name,
        single_page=single_page,
        include_qr=include_qr,
        qr_target_url=qr_url,
        include_photo=include_photo,
        photo_url=photo_url
    )
    filename = f"Resume_{resume['title'].replace(' ', '_').replace('/', '_')}_{selected_template}.pdf"

    return send_file(
        io.BytesIO(pdf_data),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

@app.route("/resume/<int:resume_id>/download/docx")
@login_required
def download_docx(resume_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM resumes WHERE id = %s AND user_id = %s", (resume_id, session["user_id"]))
            resume = cur.fetchone()

    if not resume:
        flash("Resume not found.", "danger")
        return redirect(url_for("dashboard"))

    payload = resume["generated_json"]
    if isinstance(payload, str):
        payload = json.loads(payload)

    accent_color = request.args.get("accent_color", resume.get("custom_accent_color", "#2563eb"))
    font_name = request.args.get("font", resume.get("custom_font", "inter"))
    docx_bytes = generate_docx_from_resume_data(payload, accent_color_hex=accent_color, font_name=font_name)
    filename = f"Resume_{resume['title'].replace(' ', '_')}.docx"

    return send_file(
        io.BytesIO(docx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=filename
    )

@app.route("/resume/<int:resume_id>/download/md")
@login_required
def download_markdown(resume_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM resumes WHERE id = %s AND user_id = %s", (resume_id, session["user_id"]))
            resume = cur.fetchone()

    if not resume:
        flash("Resume not found.", "danger")
        return redirect(url_for("dashboard"))

    md_content = resume.get("generated_markdown", "")
    filename = f"Resume_{resume['title'].replace(' ', '_')}.md"
    
    response = make_response(md_content)
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "text/markdown; charset=utf-8"
    return response

@app.route("/resume/<int:resume_id>/download/json")
@login_required
def download_json(resume_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM resumes WHERE id = %s AND user_id = %s", (resume_id, session["user_id"]))
            resume = cur.fetchone()

    if not resume:
        flash("Resume not found.", "danger")
        return redirect(url_for("dashboard"))

    json_content = resume.get("generated_json", "{}")
    if not isinstance(json_content, str):
        json_content = json.dumps(json_content, indent=2)

    filename = f"Resume_{resume['title'].replace(' ', '_')}.json"
    response = make_response(json_content)
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "application/json"
    return response

# ---------- PUBLIC SHAREABLE WEB RESUME ----------

@app.route("/resume/<int:resume_id>/toggle-share", methods=["POST"])
@login_required
def toggle_share(resume_id):
    user_id = session["user_id"]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, is_public, share_token FROM resumes WHERE id = %s AND user_id = %s", (resume_id, user_id))
            resume = cur.fetchone()
            if not resume:
                return jsonify({"success": False, "error": "Resume not found"}), 404

            new_is_public = 1 if not resume.get("is_public") else 0
            share_token = resume.get("share_token") or uuid.uuid4().hex[:16]

            cur.execute("UPDATE resumes SET is_public = %s, share_token = %s WHERE id = %s", (new_is_public, share_token, resume_id))

    share_url = url_for("public_resume_view", share_token=share_token, _external=True)
    return jsonify({
        "success": True,
        "is_public": bool(new_is_public),
        "share_token": share_token,
        "share_url": share_url
    })

@app.route("/r/<share_token>")
def public_resume_view(share_token):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM resumes WHERE share_token = %s AND is_public = 1", (share_token,))
            resume = cur.fetchone()

    if not resume:
        return render_template("index.html"), 404

    payload = resume["generated_json"]
    if isinstance(payload, str):
        payload = json.loads(payload)

    res_data = payload.get("resume", payload)
    return render_template("public_resume.html", resume=res_data, resume_meta=resume)

# ---------- COVER LETTER ROUTES ----------

@app.route("/api/generate-cover-letter", methods=["POST"])
@login_required
def api_generate_cover_letter():
    user_id = session["user_id"]
    data = request.get_json() or {}
    resume_id = data.get("resume_id")
    company = data.get("company", "").strip()
    job_title = data.get("job_title", "").strip()
    job_description = data.get("job_description", "").strip()
    tone = data.get("tone", "Professional & Persuasive")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM resumes WHERE id = %s AND user_id = %s", (resume_id, user_id))
            resume = cur.fetchone()

            cur.execute("SELECT email, gemini_api_key, groq_api_key, preferred_model_provider, preferred_model, is_admin FROM users WHERE id = %s", (user_id,))
            user_config = cur.fetchone() or {}

    is_admin = bool(user_config.get("is_admin")) or user_config.get("email") == "app@shriyashpatil.in"

    if not resume:
        return jsonify({"success": False, "error": "Resume not found."}), 404

    resume_payload = resume["generated_json"]
    if isinstance(resume_payload, str):
        resume_payload = json.loads(resume_payload)

    jd_text = job_description or resume.get("job_description", "")
    target_comp = company or resume.get("target_company", "") or "Hiring Team"
    target_title = job_title or resume.get("target_role", "") or "Professional Position"

    provider = user_config.get("preferred_model_provider", "gemini")
    model_name = user_config.get("preferred_model", "gemini-3.6-flash")
    api_key = user_config.get(f"{provider}_api_key")

    try:
        letter_content = generate_cover_letter(
            provider=provider,
            model_name=model_name,
            user_api_key=api_key,
            resume_data=resume_payload,
            job_description=jd_text,
            company=target_comp,
            role=target_title,
            tone=tone,
            is_admin=is_admin
        )

        with get_db() as conn:
            with conn.cursor() as cur:
                # Check existing cover letter for this resume
                cur.execute("SELECT id FROM cover_letters WHERE resume_id = %s AND user_id = %s", (resume_id, user_id))
                existing = cur.fetchone()
                if existing:
                    cur.execute("""
                        UPDATE cover_letters SET
                            company = %s, job_title = %s, job_description = %s, content = %s
                        WHERE id = %s
                    """, (target_comp, target_title, jd_text, letter_content, existing["id"]))
                    cl_id = existing["id"]
                else:
                    cur.execute("""
                        INSERT INTO cover_letters (user_id, resume_id, company, job_title, job_description, content)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (user_id, resume_id, target_comp, target_title, jd_text, letter_content))
                    cl_id = cur.lastrowid

        return jsonify({
            "success": True,
            "cover_letter_id": cl_id,
            "content": letter_content
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/resume/<int:resume_id>/cover-letter/pdf")
@login_required
def download_cover_letter_pdf(resume_id):
    user_id = session["user_id"]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM resumes WHERE id = %s AND user_id = %s", (resume_id, user_id))
            resume = cur.fetchone()
            cur.execute("SELECT * FROM cover_letters WHERE resume_id = %s AND user_id = %s ORDER BY id DESC LIMIT 1", (resume_id, user_id))
            cover_letter = cur.fetchone()

    if not resume or not cover_letter:
        flash("Cover letter not found. Please generate one first.", "warning")
        return redirect(url_for("view_resume", resume_id=resume_id))

    res_json = resume["generated_json"]
    if isinstance(res_json, str):
        res_json = json.loads(res_json)
    info = res_json.get("resume", res_json).get("personal_info", {})

    pdf_bytes = generate_cover_letter_pdf(
        candidate_name=info.get("full_name", "Applicant"),
        candidate_info=info,
        letter_text=cover_letter["content"],
        accent_color_hex=resume.get("custom_accent_color", "#2563eb")
    )
    filename = f"Cover_Letter_{cover_letter['company']}_{cover_letter['job_title']}.pdf".replace(' ', '_')
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

@app.route("/resume/<int:resume_id>/cover-letter/docx")
@login_required
def download_cover_letter_docx(resume_id):
    user_id = session["user_id"]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM resumes WHERE id = %s AND user_id = %s", (resume_id, user_id))
            resume = cur.fetchone()
            cur.execute("SELECT * FROM cover_letters WHERE resume_id = %s AND user_id = %s ORDER BY id DESC LIMIT 1", (resume_id, user_id))
            cover_letter = cur.fetchone()

    if not resume or not cover_letter:
        flash("Cover letter not found. Please generate one first.", "warning")
        return redirect(url_for("view_resume", resume_id=resume_id))

    res_json = resume["generated_json"]
    if isinstance(res_json, str):
        res_json = json.loads(res_json)
    info = res_json.get("resume", res_json).get("personal_info", {})

    docx_bytes = generate_cover_letter_docx(
        candidate_name=info.get("full_name", "Applicant"),
        candidate_info=info,
        company=cover_letter["company"],
        job_title=cover_letter["job_title"],
        letter_text=cover_letter["content"],
        accent_color_hex=resume.get("custom_accent_color", "#2563eb")
    )
    filename = f"Cover_Letter_{cover_letter['company']}_{cover_letter['job_title']}.docx".replace(' ', '_')
    return send_file(
        io.BytesIO(docx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=filename
    )

# ---------- INTERVIEW PREP ROUTES ----------

@app.route("/api/generate-interview-prep", methods=["POST"])
@login_required
def api_generate_interview_prep():
    user_id = session["user_id"]
    data = request.get_json() or {}
    resume_id = data.get("resume_id")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM resumes WHERE id = %s AND user_id = %s", (resume_id, user_id))
            resume = cur.fetchone()
            cur.execute("SELECT email, gemini_api_key, groq_api_key, preferred_model_provider, preferred_model, is_admin FROM users WHERE id = %s", (user_id,))
            user_config = cur.fetchone() or {}

    if not resume:
        return jsonify({"success": False, "error": "Resume not found."}), 404

    is_admin = bool(user_config.get("is_admin")) or user_config.get("email") == "app@shriyashpatil.in"
    resume_payload = resume["generated_json"]
    if isinstance(resume_payload, str):
        resume_payload = json.loads(resume_payload)

    provider = user_config.get("preferred_model_provider", "gemini")
    model_name = user_config.get("preferred_model", "gemini-3.6-flash")
    api_key = user_config.get(f"{provider}_api_key")

    try:
        prep_data = generate_interview_prep(
            provider=provider,
            model_name=model_name,
            user_api_key=api_key,
            resume_data=resume_payload,
            job_description=resume.get("job_description", ""),
            is_admin=is_admin
        )

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM interview_preps WHERE resume_id = %s AND user_id = %s", (resume_id, user_id))
                existing = cur.fetchone()
                if existing:
                    cur.execute("""
                        UPDATE interview_preps SET
                            company = %s, job_title = %s, qa_data = %s
                        WHERE id = %s
                    """, (resume.get("target_company", ""), resume.get("target_role", ""), json.dumps(prep_data), existing["id"]))
                    ip_id = existing["id"]
                else:
                    cur.execute("""
                        INSERT INTO interview_preps (user_id, resume_id, company, job_title, qa_data)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (user_id, resume_id, resume.get("target_company", ""), resume.get("target_role", ""), json.dumps(prep_data)))
                    ip_id = cur.lastrowid

        return jsonify({
            "success": True,
            "interview_prep_id": ip_id,
            "prep_data": prep_data
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ---------- JOB APPLICATIONS TRACKER (CRM PIPELINE) ----------

@app.route("/applications")
@login_required
def applications_list():
    user_id = session["user_id"]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ja.*, r.title as resume_title, r.match_score 
                FROM job_applications ja
                LEFT JOIN resumes r ON ja.resume_id = r.id
                WHERE ja.user_id = %s
                ORDER BY ja.updated_at DESC
            """, (user_id,))
            applications = cur.fetchall()

            # Get user's resumes for dropdown linking
            cur.execute("SELECT id, title, target_company, target_role FROM resumes WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
            user_resumes = cur.fetchall()

    # Organize into Kanban columns
    columns = {
        "Saved": [],
        "Applied": [],
        "Interviewing": [],
        "Offered": [],
        "Rejected": []
    }
    for app_item in applications:
        status = app_item.get("status", "Saved")
        if status in columns:
            columns[status].append(app_item)
        else:
            columns["Saved"].append(app_item)

    return render_template(
        "applications.html",
        columns=columns,
        applications=applications,
        user_resumes=user_resumes
    )

@app.route("/applications/create", methods=["POST"])
@login_required
def create_application():
    user_id = session["user_id"]
    company = request.form.get("company", "").strip()
    job_title = request.form.get("job_title", "").strip()
    job_url = request.form.get("job_url", "").strip()
    salary_range = request.form.get("salary_range", "").strip()
    location = request.form.get("location", "").strip()
    status = request.form.get("status", "Saved")
    resume_id = request.form.get("resume_id") or None
    notes = request.form.get("notes", "").strip()
    applied_date = request.form.get("applied_date") or None
    follow_up_date = request.form.get("follow_up_date") or None

    if not company or not job_title:
        flash("Company name and Job Title are required.", "danger")
        return redirect(url_for("applications_list"))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO job_applications (
                    user_id, resume_id, company, job_title, job_url, salary_range,
                    location, status, notes, applied_date, follow_up_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id, resume_id, company, job_title, job_url, salary_range,
                location, status, notes, applied_date, follow_up_date
            ))

    flash(f"Application for '{job_title}' at {company} added!", "success")
    return redirect(url_for("applications_list"))

@app.route("/applications/<int:app_id>/status", methods=["POST"])
@login_required
def update_application_status(app_id):
    user_id = session["user_id"]
    data = request.get_json() or {}
    new_status = data.get("status")

    if new_status not in ['Saved', 'Applied', 'Interviewing', 'Offered', 'Rejected']:
        return jsonify({"success": False, "error": "Invalid status"}), 400

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE job_applications SET status = %s WHERE id = %s AND user_id = %s
            """, (new_status, app_id, user_id))

    return jsonify({"success": True, "new_status": new_status})

@app.route("/applications/<int:app_id>/delete", methods=["POST"])
@login_required
def delete_application(app_id):
    user_id = session["user_id"]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM job_applications WHERE id = %s AND user_id = %s", (app_id, user_id))
    flash("Job application deleted.", "info")
    return redirect(url_for("applications_list"))

# ---------- QUICK SAMPLE PROFILE POPULATION ----------

@app.route("/profile/load-sample", methods=["POST"])
@login_required
def load_sample_profile():
    sample_profile = {
        "full_name": "Alex Mercer",
        "professional_title": "Senior Full-Stack & AI Engineer",
        "email": "alex.mercer@example.com",
        "phone": "+1 (555) 349-2810",
        "location": "San Francisco, CA (Open to Remote)",
        "linkedin_url": "https://linkedin.com/in/alex-mercer-dev",
        "github_url": "https://github.com/alexmercer",
        "portfolio_url": "https://alexmercer.io",
        "summary": "Versatile Software Engineer with 6+ years of experience engineering high-scale distributed backends, AI-powered web applications, and intuitive UI systems. Proven record reducing latency by 40% and deploying LLM pipelines using Python, Docker, and Cloud Native architectures.",
        "skills": [
            "Python", "Flask", "FastAPI", "JavaScript", "TypeScript", "React", "Docker",
            "MariaDB / MySQL", "PostgreSQL", "Redis", "Google Gemini API", "Groq LLMs",
            "System Design", "Microservices", "CI/CD", "Linux Architecture"
        ],
        "experiences": [
            {
                "title": "Senior Software Engineer",
                "company": "TechNova Solutions",
                "location": "San Francisco, CA",
                "start_date": "03/2022",
                "end_date": "Present",
                "highlights": [
                    "Architected high-throughput AI microservices serving 2M+ monthly queries using Python, Groq LLMs, and Redis caching.",
                    "Migrated legacy monolithic database to optimized MariaDB cluster with sharding, boosting query performance by 45%.",
                    "Led cross-functional team of 7 engineers adhering to agile methodologies and rigorous unit/integration testing."
                ]
            },
            {
                "title": "Full Stack Developer",
                "company": "Apex Cloud Systems",
                "location": "Austin, TX",
                "start_date": "06/2019",
                "end_date": "02/2022",
                "highlights": [
                    "Developed responsive web dashboards with React and Flask, increasing user engagement metrics by 35%.",
                    "Integrated automated ATS applicant pipelines processing over 50,000 candidate profiles per year.",
                    "Dockerized entire staging and production workflows, reducing team deployment cycle time by 60%."
                ]
            }
        ],
        "educations": [
            {
                "degree": "B.S. in Computer Science",
                "institution": "University of California, Berkeley",
                "graduation_date": "2019",
                "details": "GPA 3.85 / 4.0 — Honors in Distributed Systems"
            }
        ],
        "projects": [
            {
                "name": "IntelliMatch Resume AI",
                "technologies": ["Python", "Flask", "Gemini API", "MariaDB", "WeasyPrint"],
                "link": "https://github.com/alexmercer/resume-ai",
                "description": "Full-stack SaaS application that tailors user experience to targeted job descriptions with real-time ATS match scoring and PDF export."
            },
            {
                "name": "Distributed Task Engine",
                "technologies": ["Python", "Redis", "Docker", "MariaDB"],
                "link": "https://github.com/alexmercer/task-engine",
                "description": "Fault-tolerant job scheduler handling 100,000+ concurrent asynchronous background executions."
            }
        ],
        "certifications": [
            {"name": "Google Cloud Certified Professional Cloud Architect", "issuer": "Google", "date": "2023"},
            {"name": "AWS Certified Solutions Architect", "issuer": "Amazon Web Services", "date": "2022"}
        ],
        "custom_sections": [
            {
                "heading": "Awards & Recognitions",
                "items": [
                    "Winner of Global Hackathon 2023 - Best Generative AI Application",
                    "Speaker at PyData 2024: Scaling LLM APIs in Production"
                ]
            }
        ]
    }

    user_id = session["user_id"]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE profiles SET
                    full_name = %s,
                    professional_title = %s,
                    email = %s,
                    phone = %s,
                    location = %s,
                    linkedin_url = %s,
                    github_url = %s,
                    portfolio_url = %s,
                    summary = %s,
                    skills = %s,
                    experiences = %s,
                    educations = %s,
                    projects = %s,
                    certifications = %s,
                    custom_sections = %s
                WHERE user_id = %s
            """, (
                sample_profile["full_name"],
                sample_profile["professional_title"],
                sample_profile["email"],
                sample_profile["phone"],
                sample_profile["location"],
                sample_profile["linkedin_url"],
                sample_profile["github_url"],
                sample_profile["portfolio_url"],
                sample_profile["summary"],
                json.dumps(sample_profile["skills"]),
                json.dumps(sample_profile["experiences"]),
                json.dumps(sample_profile["educations"]),
                json.dumps(sample_profile["projects"]),
                json.dumps(sample_profile["certifications"]),
                json.dumps(sample_profile["custom_sections"]),
                user_id
            ))

    flash("Demo profile loaded! You can now test resume generation with a single click.", "success")
    return redirect(url_for("profile"))

# ---------- AI CHAT ASSISTANT API ----------

@app.route("/api/resume/<int:resume_id>/chat", methods=["POST"])
@login_required
def chat_resume(resume_id):
    user_id = session["user_id"]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM resumes WHERE id = %s AND user_id = %s", (resume_id, user_id))
            resume = cur.fetchone()

            cur.execute("SELECT email, gemini_api_key, groq_api_key, preferred_model_provider, preferred_model, is_admin FROM users WHERE id = %s", (user_id,))
            user_config = cur.fetchone() or {}

    if not resume:
        return jsonify({"success": False, "error": "Resume not found"}), 404

    is_admin = bool(user_config.get("is_admin")) or user_config.get("email") == "app@shriyashpatil.in"
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    history = data.get("history", [])
    provider = data.get("provider") or user_config.get("preferred_model_provider", "gemini")
    model_name = data.get("model_name") or user_config.get("preferred_model", "gemini-3.6-flash")

    if not message:
        return jsonify({"success": False, "error": "Message is required"}), 400

    active_key = None
    if provider == "gemini":
        active_key = user_config.get("gemini_api_key")
    elif provider == "groq":
        active_key = user_config.get("groq_api_key")

    try:
        reply = ai_chat_assistant(
            provider=provider,
            model_name=model_name,
            user_api_key=active_key,
            user_message=message,
            resume_context=resume,
            chat_history=history,
            is_admin=is_admin
        )
        return jsonify({"success": True, "reply": reply})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 9999))
    print(f"🚀 Resume AI Generator running at http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
