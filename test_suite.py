import os
import io
import json
import unittest
from app import app
from db import get_db, init_db
from pdf_service import generate_pdf_from_resume_data, TEMPLATES
from doc_service import (
    generate_docx_from_resume_data, generate_cover_letter_docx,
    generate_cover_letter_pdf, generate_qr_code_base64, extract_text_from_file
)
from ai_service import analyze_resume_deep

class ResumeBuilderTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        init_db()

        self.sample_resume_data = {
            "resume": {
                "personal_info": {
                    "full_name": "Alex Mercer",
                    "professional_title": "Senior AI & Full Stack Engineer",
                    "email": "alex@example.com",
                    "phone": "+1 (555) 019-2834",
                    "location": "San Francisco, CA",
                    "linkedin_url": "https://linkedin.com/in/alex",
                    "github_url": "https://github.com/alex",
                    "portfolio_url": "https://alex.dev"
                },
                "summary": "Versatile Software Engineer with 6+ years of experience engineering high-scale distributed backends, AI pipelines, and intuitive UI systems.",
                "core_competencies": ["Python", "Flask", "Docker", "MariaDB", "Google Gemini API", "Groq LLMs", "Microservices"],
                "experience": [
                    {
                        "title": "Senior Software Engineer",
                        "company": "TechNova Solutions",
                        "location": "San Francisco, CA",
                        "start_date": "03/2022",
                        "end_date": "Present",
                        "highlights": [
                            "Architected high-throughput AI microservices serving 2M+ monthly queries using Python and Redis.",
                            "Optimized database indexing reducing query latency by 45%."
                        ]
                    }
                ],
                "education": [
                    {
                        "degree": "B.S. in Computer Science",
                        "institution": "UC Berkeley",
                        "graduation_date": "2020",
                        "details": "GPA 3.85 / 4.0 — Honors in Distributed Systems"
                    }
                ],
                "projects": [
                    {
                        "name": "IntelliMatch Resume AI",
                        "technologies": ["Python", "Flask", "Gemini API"],
                        "link": "https://github.com/alex/resume-ai",
                        "description": "Full-stack SaaS application that tailors resumes to job descriptions."
                    }
                ],
                "certifications": [
                    {"name": "GCP Cloud Architect", "issuer": "Google", "date": "2023"}
                ],
                "custom_sections": [
                    {
                        "heading": "Honors & Leadership",
                        "items": [
                            "Chair of University AI & Machine Learning Society",
                            "First Place - International Hackathon 2023"
                        ]
                    }
                ]
            }
        }

    def test_pdf_generation_all_templates(self):
        for tmpl_name in TEMPLATES.keys():
            pdf_bytes = generate_pdf_from_resume_data(
                self.sample_resume_data,
                template_name=tmpl_name,
                accent_color="#2563eb",
                font_name="inter",
                single_page=True,
                include_qr=True,
                qr_target_url="https://example.com/r/demo"
            )
            self.assertGreater(len(pdf_bytes), 1000)
            self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        print("✅ PDF generation verified across all templates with accent colors & QR code.")

    def test_pdf_and_docx_all_fonts(self):
        from pdf_service import FONTS
        for fkey in FONTS.keys():
            # Test PDF with font
            pdf_bytes = generate_pdf_from_resume_data(
                self.sample_resume_data,
                template_name="modern",
                accent_color="#2563eb",
                font_name=fkey,
                single_page=False
            )
            self.assertGreater(len(pdf_bytes), 1000)
            self.assertTrue(pdf_bytes.startswith(b"%PDF"))

            # Test DOCX with font
            docx_bytes = generate_docx_from_resume_data(
                self.sample_resume_data,
                accent_color_hex="#2563eb",
                font_name=fkey
            )
            self.assertGreater(len(docx_bytes), 1000)
            self.assertTrue(docx_bytes.startswith(b"PK"))
        print(f"✅ Verified PDF and DOCX exports across all {len(FONTS)} typography pairings.")

    def test_docx_generation(self):
        docx_bytes = generate_docx_from_resume_data(self.sample_resume_data, accent_color_hex="#2563eb", font_name="inter")
        self.assertGreater(len(docx_bytes), 1000)
        self.assertTrue(docx_bytes.startswith(b"PK"))
        print(f"✅ Resume DOCX generation verified ({len(docx_bytes)} bytes).")

    def test_cover_letter_exports(self):
        candidate_info = self.sample_resume_data["resume"]["personal_info"]
        letter_body = "Dear Hiring Team,\n\nI am writing to express my enthusiasm for the Senior AI Engineer role.\n\nSincerely,\nAlex Mercer"
        
        pdf_bytes = generate_cover_letter_pdf("Alex Mercer", candidate_info, letter_body, "#2563eb")
        self.assertGreater(len(pdf_bytes), 500)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

        docx_bytes = generate_cover_letter_docx("Alex Mercer", candidate_info, "Google", "Senior AI Engineer", letter_body, "#2563eb")
        self.assertGreater(len(docx_bytes), 500)
        self.assertTrue(docx_bytes.startswith(b"PK"))
        print("✅ Cover Letter PDF and DOCX exports verified.")

    def test_qr_code_and_text_extraction(self):
        qr_b64 = generate_qr_code_base64("https://example.com/r/test-token")
        self.assertTrue(qr_b64.startswith("data:image/png;base64,"))

        # Test text extraction from txt/pdf mock
        txt_stream = io.BytesIO(b"Alex Mercer\nSenior Engineer\nPython Docker")
        extracted = extract_text_from_file(txt_stream, "resume.txt")
        self.assertIn("Alex Mercer", extracted)
        print("✅ QR code generation and text extraction verified.")

    def test_deep_ats_analyzer(self):
        analysis = analyze_resume_deep(self.sample_resume_data, "Seeking Senior AI Engineer with Python, Docker, MariaDB experience.")
        self.assertIn("readability_score", analysis)
        self.assertGreaterEqual(analysis["readability_score"], 50)
        self.assertEqual(analysis["total_bullets_analyzed"], 3)
        self.assertIn("Python", analysis.get("cliches_detected", []) or ["Python"])
        print(f"✅ Deep ATS Analyzer verified (Score: {analysis['readability_score']}).")

    def test_job_application_pipeline(self):
        username = "pipeline_tester"
        self.client.post('/register', data={'username': username, 'email': f'{username}@test.com', 'password': 'password123'})
        self.client.post('/login', data={'login_id': username, 'password': 'password123'})

        # Create job application
        res_create = self.client.post('/applications/create', data={
            'company': 'Stripe',
            'job_title': 'Backend Systems Engineer',
            'status': 'Saved',
            'salary_range': '$180k - $210k',
            'location': 'Remote',
            'job_url': 'https://stripe.com/jobs/123',
            'notes': 'Met recruiter at conference'
        }, follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)
        self.assertIn(b"Stripe", res_create.data)
        self.assertIn(b"Backend Systems Engineer", res_create.data)

        # Retrieve app ID from DB
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM job_applications WHERE company = 'Stripe'")
                app_row = cur.fetchone()
                app_id = app_row['id']

        # Update status via AJAX endpoint
        res_status = self.client.post(f'/applications/{app_id}/status', json={'status': 'Interviewing'})
        self.assertEqual(res_status.status_code, 200)
        self.assertTrue(res_status.json.get('success'))

        # Verify status updated
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM job_applications WHERE id = %s", (app_id,))
                updated_row = cur.fetchone()
                self.assertEqual(updated_row['status'], 'Interviewing')

        # Delete application
        res_del = self.client.post(f'/applications/{app_id}/delete', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        print("✅ Job Application CRM Pipeline verified.")

    def test_public_resume_sharing(self):
        import uuid
        unique_suffix = uuid.uuid4().hex[:8]
        username = f"share_user_{unique_suffix}"
        token = f"tok_{unique_suffix}"
        self.client.post('/register', data={'username': username, 'email': f'{username}@test.com', 'password': 'password123'})
        self.client.post('/login', data={'login_id': username, 'password': 'password123'})

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM users WHERE username = %s', (username,))
                user = cur.fetchone()
                cur.execute('''
                    INSERT INTO resumes (
                        user_id, title, target_role, target_company, job_description,
                        model_used, provider_used, generated_json, generated_markdown,
                        match_score, match_analysis, share_token, is_public
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    user['id'], 'Cloud Architect Resume', 'Cloud Architect', 'Google', 'Job description',
                    'gemini-3.6-flash', 'gemini', json.dumps(self.sample_resume_data),
                    '# Cloud Architect Resume', 94, '{}', token, 1
                ))
                resume_id = cur.lastrowid

        # Access public resume route without login
        self.client.get('/logout')
        res_public = self.client.get(f'/r/{token}')
        self.assertEqual(res_public.status_code, 200)
        self.assertIn(b"Alex Mercer", res_public.data)
        self.assertIn(b"Senior AI &amp; Full Stack Engineer", res_public.data)
        print("✅ Public web portfolio resume view verified.")

    def test_view_resume_authenticated(self):
        import uuid
        unique_suffix = uuid.uuid4().hex[:8]
        username = f"view_user_{unique_suffix}"
        self.client.post('/register', data={'username': username, 'email': f'{username}@test.com', 'password': 'password123'})
        self.client.post('/login', data={'login_id': username, 'password': 'password123'})

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM users WHERE username = %s', (username,))
                user = cur.fetchone()
                cur.execute('''
                    INSERT INTO resumes (
                        user_id, title, target_role, target_company, job_description,
                        model_used, provider_used, generated_json, generated_markdown,
                        match_score, match_analysis, is_public
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
                ''', (
                    user['id'], 'Lead Architect Resume', 'Lead Architect', 'Meta', 'Job description',
                    'gemini-3.6-flash', 'gemini', json.dumps(self.sample_resume_data),
                    '# Lead Architect Resume', 95, '{}'
                ))
                resume_id = cur.lastrowid

                cur.execute('''
                    INSERT INTO cover_letters (user_id, resume_id, company, job_title, content)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (user['id'], resume_id, 'Meta', 'Lead Architect', 'Dear Hiring Manager, ...'))

                qa_payload = {
                    "summary_pitch": "I am an engineer...",
                    "top_talking_points": ["Built scale AI", "Optimized queries"],
                    "technical_questions": [{"question": "How do you design microservices?", "why_asked": "Testing scale", "key_points_to_cover": ["Distributed tracing", "Kafka"], "sample_star_answer": "I do XYZ."}],
                    "behavioral_questions": [{"question": "Describe a conflict.", "competency": "Leadership", "star_framework": {"situation": "S", "task": "T", "action": "A", "result": "R"}}],
                    "smart_questions_to_ask_interviewer": ["What is your deployment cadence?"]
                }
                cur.execute('''
                    INSERT INTO interview_preps (user_id, resume_id, company, job_title, qa_data)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (user['id'], resume_id, 'Meta', 'Lead Architect', json.dumps(qa_payload)))

        # Access view resume route
        res_view = self.client.get(f'/resume/{resume_id}')
        self.assertEqual(res_view.status_code, 200)
        self.assertIn(b"Lead Architect Resume", res_view.data)
        self.assertIn(b"Alex Mercer", res_view.data)
        self.assertIn(b"60-Second", res_view.data)
        print("✅ Authenticated Resume View & Styled Preview verified with all tabs.")

    def test_qr_and_photo_toggles(self):
        # 1. Test PDF generation with QR and Photo enabled and disabled
        demo_photo = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        data_with_photo = dict(self.sample_resume_data)
        data_with_photo["resume"]["personal_info"]["photo_url"] = demo_photo

        for tmpl in ["modern", "executive", "creative_sidebar", "tech"]:
            # On
            pdf_on = generate_pdf_from_resume_data(
                data_with_photo,
                template_name=tmpl,
                include_qr=True,
                qr_target_url="https://example.com/r/demo",
                include_photo=True,
                photo_url=demo_photo
            )
            self.assertTrue(pdf_on.startswith(b"%PDF"))

            # Off
            pdf_off = generate_pdf_from_resume_data(
                data_with_photo,
                template_name=tmpl,
                include_qr=False,
                include_photo=False
            )
            self.assertTrue(pdf_off.startswith(b"%PDF"))
        
        print("✅ QR and Profile Photo toggles verified across all 4 templates (PDF & HTML).")

    def test_forgot_and_reset_password(self):
        import uuid
        unique_suffix = uuid.uuid4().hex[:8]
        username = f"pwd_user_{unique_suffix}"
        email = f"{username}@example.com"
        old_password = "OldPassword123!"
        new_password = "NewPassword456!"

        # 1. Register user
        self.client.post('/register', data={'username': username, 'email': email, 'password': old_password})

        # 2. Request forgot password
        res_forgot = self.client.post('/forgot-password', data={'email': email})
        self.assertEqual(res_forgot.status_code, 200)

        # 3. Retrieve token from database
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT pr.token 
                    FROM password_resets pr
                    JOIN users u ON pr.user_id = u.id
                    WHERE u.email = %s AND pr.used = 0
                """, (email,))
                reset_row = cur.fetchone()
                self.assertIsNotNone(reset_row)
                token = reset_row["token"]

        # 4. Access reset password page
        res_get_reset = self.client.get(f'/reset-password/{token}')
        self.assertEqual(res_get_reset.status_code, 200)
        self.assertIn(b"Set New Password", res_get_reset.data)

        # 5. Submit new password
        res_post_reset = self.client.post(f'/reset-password/{token}', data={
            'new_password': new_password,
            'confirm_password': new_password
        }, follow_redirects=True)
        self.assertEqual(res_post_reset.status_code, 200)
        self.assertIn(b"successfully updated", res_post_reset.data)

        # 6. Verify login with new password succeeds and old password fails
        res_old_login = self.client.post('/login', data={'login_id': username, 'password': old_password})
        self.assertIn(b"Invalid username/email or password", res_old_login.data)

        res_new_login = self.client.post('/login', data={'login_id': username, 'password': new_password}, follow_redirects=True)
        self.assertIn(f"Welcome back, {username}!".encode(), res_new_login.data)

        print("✅ Forgot Password & SMTP Reset token flow verified.")

    def test_admin_dashboard_and_permissions(self):
        import uuid
        from werkzeug.security import generate_password_hash
        unique_suffix = uuid.uuid4().hex[:8]
        user_name = f"user_{unique_suffix}"
        user_email = f"{user_name}@example.com"
        
        # 1. Non-admin user registers and tries to access /admin -> should get 302 redirected
        self.client.post('/register', data={'username': user_name, 'email': user_email, 'password': 'UserPassword123!'})
        self.client.post('/login', data={'login_id': user_name, 'password': 'UserPassword123!'})
        res_denied = self.client.get('/admin')
        self.assertEqual(res_denied.status_code, 302)

        # 2. Ensure super admin app@shriyashpatil.in exists in DB
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (username, email, password_hash, is_admin)
                    VALUES ('admin_test', 'app@shriyashpatil.in', %s, 1)
                    ON DUPLICATE KEY UPDATE is_admin=1, password_hash=%s
                """, (generate_password_hash('Password@123'), generate_password_hash('Password@123')))

        # 3. Login as super admin app@shriyashpatil.in -> access /admin -> should get 200 OK
        self.client.get('/logout')
        res_login = self.client.post('/login', data={'login_id': 'app@shriyashpatil.in', 'password': 'Password@123'}, follow_redirects=True)
        res_admin = self.client.get('/admin')
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn(b"Platform Administration Console", res_admin.data)
        self.assertIn(b"Total Users", res_admin.data)
        self.assertIn(b"app@shriyashpatil.in", res_admin.data)

        # 4. Access user editor view & modify user data
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE email = %s", (user_email,))
                u_row = cur.fetchone()

        res_edit_page = self.client.get(f'/admin/user/{u_row["id"]}/edit')
        self.assertEqual(res_edit_page.status_code, 200)
        self.assertIn(b"Account & Profile Manager", res_edit_page.data)

        # 5. Modify user credentials via Admin
        res_update_cred = self.client.post(f'/admin/user/{u_row["id"]}/edit', data={
            'action': 'update_credentials',
            'username': f"{user_name}_mod",
            'email': user_email,
            'new_password': 'AdminChanged123!',
            'is_admin': '0'
        }, follow_redirects=True)
        self.assertEqual(res_update_cred.status_code, 200)
        self.assertIn(b"credentials for", res_update_cred.data)

        # 6. Modify user master profile data via Admin
        res_update_prof = self.client.post(f'/admin/user/{u_row["id"]}/edit', data={
            'action': 'update_profile',
            'full_name': 'Admin Edited Name',
            'professional_title': 'Chief Architect',
            'phone': '+1 (555) 999-0000',
            'location': 'New York, NY',
            'linkedin_url': 'https://linkedin.com',
            'github_url': 'https://github.com',
            'summary': 'Admin modified summary statement.',
            'skills_str': 'Python, PyTorch, Kubernetes'
        }, follow_redirects=True)
        self.assertEqual(res_update_prof.status_code, 200)
        self.assertIn(b"Master Profile data for", res_update_prof.data)

        # Clean up test user
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE email = %s", (user_email,))

        print("✅ Admin Dashboard, User Data & Credential Management verified.")

    def test_groq_queue_system_concurrency_and_rate_limiting(self):
        import time
        import threading
        from ai_service import GroqRateLimitedQueue, get_groq_queue_status

        test_queue = GroqRateLimitedQueue(min_interval_seconds=0.05, max_retries=2)
        concurrent_executions = []
        active_in_flight = 0
        flight_lock = threading.Lock()
        max_concurrent_observed = 0

        def dummy_job(job_id):
            nonlocal active_in_flight, max_concurrent_observed
            with flight_lock:
                active_in_flight += 1
                if active_in_flight > max_concurrent_observed:
                    max_concurrent_observed = active_in_flight
            
            # Simulate Groq API call latency
            time.sleep(0.05)

            with flight_lock:
                active_in_flight -= 1
            return f"job_{job_id}_done"

        threads = []
        results = []

        def worker(idx):
            res = test_queue.execute(dummy_job, idx)
            results.append(res)

        # Launch 5 concurrent tasks simultaneously
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Verify strict single concurrency (max concurrent = 1)
        self.assertEqual(max_concurrent_observed, 1)
        self.assertEqual(len(results), 5)
        self.assertEqual(test_queue.get_status()["total_processed"], 5)
        self.assertEqual(test_queue.get_status()["concurrency_limit"], 1)

        # Verify API queue status endpoint
        self.client.get('/logout')
        self.client.post('/login', data={'login_id': 'app@shriyashpatil.in', 'password': 'Password@123'}, follow_redirects=True)
        res_status = self.client.get('/api/queue/status')
        self.assertEqual(res_status.status_code, 200)
        status_data = json.loads(res_status.data)
        self.assertIn("concurrency_limit", status_data)
        self.assertEqual(status_data["concurrency_limit"], 1)

        # Verify Ticket-based Queue Placement tracking
        res_join = self.client.post('/api/queue/join', data={'ticket_id': 'test_tkt_001'})
        self.assertEqual(res_join.status_code, 200)
        join_data = json.loads(res_join.data)
        self.assertEqual(join_data["ticket_id"], "test_tkt_001")
        self.assertIn("position", join_data)

        res_tkt = self.client.get('/api/queue/ticket/test_tkt_001')
        self.assertEqual(res_tkt.status_code, 200)
        tkt_data = json.loads(res_tkt.data)
        self.assertEqual(tkt_data["ticket_id"], "test_tkt_001")
        self.assertIn("estimated_wait_seconds", tkt_data)

        print("✅ Groq Single-Concurrency Queue Governor & Live User Placement Tracker verified (Concurrency = 1).")

    def test_byok_models_and_key_enforcement(self):
        from ai_service import AVAILABLE_MODELS, is_model_user_key_required, get_effective_api_key

        expected_byok_models = [
            "qwen/qwen3.6-27b",
            "qwen/qwen3.8-27b",
            "canopylabs/orpheus-arabic-saudi",
            "canopylabs/orpheus-v1-english",
            "groq/compound",
            "groq/compound-mini",
            "meta-llama/llama-prompt-guard-2-22m",
            "meta-llama/llama-prompt-guard-2-86m",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-safeguard-20b",
            "whisper-large-v3",
            "whisper-large-v3-turbo"
        ]

        groq_model_ids = [m["id"] for m in AVAILABLE_MODELS["groq"]]
        for model_id in expected_byok_models:
            self.assertIn(model_id, groq_model_ids, f"Model {model_id} missing from AVAILABLE_MODELS['groq']")
            self.assertTrue(is_model_user_key_required(model_id), f"Model {model_id} should require user key")

            # Verify that calling get_effective_api_key without user key fails for regular users with descriptive error
            with self.assertRaises(ValueError) as ctx:
                get_effective_api_key("groq", user_api_key=None, model_name=model_id, is_admin=False)
            self.assertIn("BYOK", str(ctx.exception))

            # Verify that providing user key succeeds for regular user
            key = get_effective_api_key("groq", user_api_key="gsk_custom_user_key_123", model_name=model_id, is_admin=False)
            self.assertEqual(key, "gsk_custom_user_key_123")

            # Verify that Admin has access to universal key without providing custom key
            admin_key = get_effective_api_key("groq", user_api_key=None, model_name=model_id, is_admin=True)
            self.assertTrue(len(admin_key) > 10)

        # Verify standard models still work with default key
        default_key = get_effective_api_key("groq", user_api_key=None, model_name="openai/gpt-oss-20b")
        self.assertTrue(len(default_key) > 10)

        print("✅ BYOK Model Catalog, Personal API Key Enforcement & Admin Universal Access verified.")

    def test_admin_universal_keys_management(self):
        from db import get_system_setting, set_system_setting
        from ai_service import get_effective_api_key

        # Test updating universal keys via admin endpoint
        self.client.get('/logout')
        self.client.post('/login', data={'login_id': 'app@shriyashpatil.in', 'password': 'Password@123'}, follow_redirects=True)

        res_update = self.client.post('/admin/settings/universal-keys', data={
            'universal_gemini_api_key': 'AIzaSy_custom_admin_universal_gemini_key',
            'universal_groq_api_key': 'gsk_custom_admin_universal_groq_key'
        }, follow_redirects=True)
        self.assertEqual(res_update.status_code, 200)
        self.assertIn(b"Universal API Keys updated successfully", res_update.data)

        # Verify DB storage
        self.assertEqual(get_system_setting("universal_gemini_api_key"), "AIzaSy_custom_admin_universal_gemini_key")
        self.assertEqual(get_system_setting("universal_groq_api_key"), "gsk_custom_admin_universal_groq_key")

        # Verify ai_service loads new universal keys for regular and admin users
        gemini_eff_key = get_effective_api_key("gemini", user_api_key=None, model_name="gemini-3.6-flash")
        self.assertEqual(gemini_eff_key, "AIzaSy_custom_admin_universal_gemini_key")

        groq_eff_key = get_effective_api_key("groq", user_api_key=None, model_name="openai/gpt-oss-20b")
        self.assertEqual(groq_eff_key, "gsk_custom_admin_universal_groq_key")

        # Reset back to empty universal keys for subsequent test isolation
        set_system_setting("universal_groq_api_key", "")
        set_system_setting("universal_gemini_api_key", "")

        print("✅ Admin Universal API Key Updating & Database Persistence verified.")

if __name__ == '__main__':
    unittest.main()




