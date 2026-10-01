import pymysql
import os
import json
from contextlib import contextmanager

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "resume_builder")

def get_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        with conn.cursor() as cursor:
            # Users table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                gemini_api_key VARCHAR(255) DEFAULT NULL,
                groq_api_key VARCHAR(255) DEFAULT NULL,
                preferred_model_provider VARCHAR(50) DEFAULT 'gemini',
                preferred_model VARCHAR(100) DEFAULT 'gemini-3.6-flash',
                is_admin TINYINT(1) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            try:
                cursor.execute("ALTER TABLE users ADD COLUMN is_admin TINYINT(1) DEFAULT 0;")
            except Exception:
                pass

            # User Profile Details table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT UNIQUE NOT NULL,
                full_name VARCHAR(150),
                professional_title VARCHAR(150),
                profile_photo_url MEDIUMTEXT DEFAULT NULL,
                email VARCHAR(255),
                phone VARCHAR(50),
                location VARCHAR(150),
                linkedin_url VARCHAR(255),
                github_url VARCHAR(255),
                portfolio_url VARCHAR(255),
                summary TEXT,
                skills JSON,
                experiences JSON,
                educations JSON,
                projects JSON,
                certifications JSON,
                custom_sections JSON,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # Safe column additions for existing profiles table
            try:
                cursor.execute("ALTER TABLE profiles ADD COLUMN profile_photo_url MEDIUMTEXT DEFAULT NULL;")
            except Exception:
                pass

            # Resumes generated table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                title VARCHAR(200) NOT NULL,
                target_role VARCHAR(200),
                target_company VARCHAR(200),
                job_description MEDIUMTEXT NOT NULL,
                model_used VARCHAR(100) NOT NULL,
                provider_used VARCHAR(50) NOT NULL,
                template_name VARCHAR(50) DEFAULT 'modern',
                custom_accent_color VARCHAR(20) DEFAULT '#2563eb',
                custom_font VARCHAR(50) DEFAULT 'inter',
                single_page_mode TINYINT(1) DEFAULT 0,
                include_qr TINYINT(1) DEFAULT 1,
                include_photo TINYINT(1) DEFAULT 1,
                share_token VARCHAR(64) UNIQUE DEFAULT NULL,
                is_public TINYINT(1) DEFAULT 0,
                generated_json JSON NOT NULL,
                generated_markdown MEDIUMTEXT,
                match_score INT DEFAULT 0,
                match_analysis JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # Safe column additions for existing resumes table if running against existing DB
            columns_to_add = [
                ("custom_accent_color", "VARCHAR(20) DEFAULT '#2563eb'"),
                ("custom_font", "VARCHAR(50) DEFAULT 'inter'"),
                ("single_page_mode", "TINYINT(1) DEFAULT 0"),
                ("include_qr", "TINYINT(1) DEFAULT 1"),
                ("include_photo", "TINYINT(1) DEFAULT 1"),
                ("share_token", "VARCHAR(64) UNIQUE DEFAULT NULL"),
                ("is_public", "TINYINT(1) DEFAULT 0"),
            ]
            for col_name, col_def in columns_to_add:
                try:
                    cursor.execute(f"ALTER TABLE resumes ADD COLUMN {col_name} {col_def};")
                except Exception:
                    pass  # Column already exists

            # Cover Letters table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cover_letters (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                resume_id INT DEFAULT NULL,
                company VARCHAR(200) NOT NULL,
                job_title VARCHAR(200) NOT NULL,
                job_description MEDIUMTEXT,
                content MEDIUMTEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # Interview Preps table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS interview_preps (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                resume_id INT DEFAULT NULL,
                company VARCHAR(200),
                job_title VARCHAR(200),
                qa_data JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # Job Applications (Mini-CRM / Pipeline Tracker)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_applications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                resume_id INT DEFAULT NULL,
                cover_letter_id INT DEFAULT NULL,
                company VARCHAR(200) NOT NULL,
                job_title VARCHAR(200) NOT NULL,
                job_url VARCHAR(500) DEFAULT '',
                salary_range VARCHAR(100) DEFAULT '',
                location VARCHAR(150) DEFAULT '',
                status ENUM('Saved', 'Applied', 'Interviewing', 'Offered', 'Rejected') DEFAULT 'Saved',
                notes MEDIUMTEXT,
                applied_date DATE DEFAULT NULL,
                follow_up_date DATE DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE SET NULL,
                FOREIGN KEY (cover_letter_id) REFERENCES cover_letters(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # Password Resets (Forgot Password Tokens)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_resets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                token VARCHAR(100) UNIQUE NOT NULL,
                expires_at DATETIME NOT NULL,
                used TINYINT(1) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # System Settings Table (Universal API Keys, System Configs)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                setting_key VARCHAR(100) PRIMARY KEY,
                setting_value MEDIUMTEXT NOT NULL,
                description VARCHAR(255) DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # Seed default system keys if not already present
            cursor.execute("""
                INSERT IGNORE INTO system_settings (setting_key, setting_value, description)
                VALUES 
                ('universal_gemini_api_key', '', 'Universal default Google Gemini API Key'),
                ('universal_groq_api_key', '', 'Universal default Groq Cloud API Key')
            """)

            print("Database initialized & schema updated successfully!")

def get_system_setting(key: str, default: str = "") -> str:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = %s", (key,))
                row = cur.fetchone()
                if row and row.get("setting_value") is not None:
                    val = row["setting_value"].strip()
                    if val:
                        return val
    except Exception:
        pass
    return default

def set_system_setting(key: str, value: str, description: str = "") -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO system_settings (setting_key, setting_value, description)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    setting_value = VALUES(setting_value),
                    description = IF(VALUES(description) != '', VALUES(description), description)
            """, (key, value.strip(), description))

def get_all_system_settings() -> dict:
    settings = {}
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT setting_key, setting_value FROM system_settings")
                rows = cur.fetchall()
                for r in rows:
                    settings[r["setting_key"]] = r["setting_value"]
    except Exception:
        pass
    return settings

if __name__ == "__main__":
    init_db()

