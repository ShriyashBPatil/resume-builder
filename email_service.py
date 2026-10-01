import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# SMTP Configurations
SMTP_SERVER = os.environ.get("SMTP_SERVER", "mail.shriyashpatil.in")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 465))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "app@shriyashpatil.in")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "Shriyash@11")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", "app@shriyashpatil.in")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "ResumeAI")

def _get_base_template(headline_title: str, main_content_html: str, callout_note: str = "") -> str:
    """
    Clean, elegant HTML email with pure typography, generous whitespace, and no emojis or icons.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{headline_title}</title>
  <style type="text/css">
    body {{
      margin: 0;
      padding: 0;
      background-color: #fafafa;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #262626;
      -webkit-font-smoothing: antialiased;
      line-height: 1.65;
    }}
    table {{ border-collapse: collapse; }}
    a {{ color: #000000; text-decoration: underline; }}
    .btn {{
      display: inline-block;
      background-color: #000000;
      color: #ffffff !important;
      text-decoration: none !important;
      font-size: 13px;
      font-weight: 500;
      padding: 11px 22px;
      border-radius: 4px;
      letter-spacing: 0.1px;
    }}
    .btn:hover {{ background-color: #333333 !important; }}
    @media only screen and (max-width: 600px) {{
      .wrapper {{ width: 100% !important; padding: 16px !important; }}
      .card {{ padding: 32px 24px !important; }}
    }}
  </style>
</head>
<body style="background-color: #fafafa; margin: 0; padding: 48px 16px;">
  <table border="0" cellpadding="0" cellspacing="0" width="100%">
    <tr>
      <td align="center">
        <table border="0" cellpadding="0" cellspacing="0" width="100%" class="wrapper" style="max-width: 500px; text-align: left;">
          
          <!-- Pure Text Header -->
          <tr>
            <td style="padding-bottom: 24px;">
              <span style="font-size: 14px; font-weight: 600; letter-spacing: -0.2px; color: #171717;">ResumeAI</span>
            </td>
          </tr>

          <!-- Card Container -->
          <tr>
            <td class="card" style="background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 6px; padding: 36px 32px;">
              {main_content_html}

              {f'''
              <div style="margin-top: 28px; padding-top: 16px; border-top: 1px solid #f0f0f0; font-size: 12px; color: #737373; line-height: 1.5;">
                {callout_note}
              </div>
              ''' if callout_note else ''}
            </td>
          </tr>

          <!-- Minimal Footer -->
          <tr>
            <td style="padding-top: 20px; font-size: 11px; color: #a3a3a3; line-height: 1.6;">
              ResumeAI &bull; Built and developed by <a href="https://shriyashpatil.in" target="_blank" style="color: #737373; text-decoration: underline;">shriyashpatil.in</a><br />
              <a href="mailto:app@shriyashpatil.in" style="color: #a3a3a3; text-decoration: underline;">app@shriyashpatil.in</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

def send_password_reset_email(to_email: str, reset_link: str, recipient_name: str = "") -> dict:
    """
    Sends a clean text-first password reset email.
    """
    subject = "Reset your ResumeAI password"
    name = recipient_name or "there"

    content_html = f"""
      <h1 style="margin: 0 0 16px 0; font-size: 17px; font-weight: 600; color: #171717; letter-spacing: -0.2px;">
        Reset your password
      </h1>
      <p style="margin: 0 0 20px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        Hello {name}, we received a request to reset your password. Click the link below to set a new password for your account.
      </p>
      <div style="margin: 24px 0;">
        <a href="{reset_link}" target="_blank" class="btn">
          Reset password
        </a>
      </div>
      <p style="margin: 20px 0 0 0; font-size: 12px; color: #737373; line-height: 1.5;">
        This link is valid for 1 hour. If you did not request this, please disregard this email.
      </p>
    """

    text_body = f"""Hello {name},

We received a request to reset your ResumeAI password:
{reset_link}

This link is valid for 1 hour. If you did not request this, you can ignore this email.

— The ResumeAI Team
app@shriyashpatil.in
"""

    html_body = _get_base_template("Reset your password", content_html)
    return _send_mime_email(to_email, subject, text_body, html_body, reset_link)

def send_otp_verification_email(to_email: str, otp_code: str, recipient_name: str = "") -> dict:
    """
    Sends a clean OTP verification email.
    """
    subject = f"{otp_code} is your ResumeAI verification code"
    name = recipient_name or "there"

    content_html = f"""
      <h1 style="margin: 0 0 16px 0; font-size: 17px; font-weight: 600; color: #171717; letter-spacing: -0.2px;">
        Verification code
      </h1>
      <p style="margin: 0 0 20px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        Hello {name}, use the code below to complete your verification:
      </p>
      <div style="margin: 20px 0;">
        <div style="display: inline-block; padding: 12px 20px; background-color: #f5f5f5; border: 1px solid #e5e5e5; border-radius: 4px; font-family: ui-monospace, Menlo, Monaco, Consolas, monospace; font-size: 24px; font-weight: 600; letter-spacing: 6px; color: #171717;">
          {otp_code}
        </div>
      </div>
      <p style="margin: 16px 0 0 0; font-size: 12px; color: #737373; line-height: 1.5;">
        This code is valid for 10 minutes.
      </p>
    """

    text_body = f"""Hello {name},

Your verification code is: {otp_code}

Valid for 10 minutes.

— The ResumeAI Team
app@shriyashpatil.in
"""

    html_body = _get_base_template(f"Verification Code: {otp_code}", content_html)
    return _send_mime_email(to_email, subject, text_body, html_body)

def send_welcome_email(to_email: str, recipient_name: str = "", login_url: str = "") -> dict:
    """
    Sends a pure, clean HTML welcome email without logos or emojis.
    """
    subject = "Welcome to ResumeAI"
    name = recipient_name or "there"
    url = login_url or "http://server.shriyashpatil.in:9999/login"

    content_html = f"""
      <h1 style="margin: 0 0 16px 0; font-size: 17px; font-weight: 600; color: #171717; letter-spacing: -0.2px;">
        Welcome to ResumeAI
      </h1>
      <p style="margin: 0 0 16px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        Hello {name}, thank you for creating an account. Your workspace is ready.
      </p>
      <p style="margin: 0 0 20px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        You can build tailored resumes tailored to specific job postings, generate cover letters, and download formatted PDF or Word documents.
      </p>
      <div style="margin: 24px 0 8px 0;">
        <a href="{url}" class="btn">
          Go to Dashboard
        </a>
      </div>
    """

    callout_note = "If you have an existing resume, you can upload it in your profile settings to auto-fill your background details."

    text_body = f"""Hello {name},

Welcome to ResumeAI. Your workspace is ready.

You can sign in here:
{url}

— The ResumeAI Team
app@shriyashpatil.in
"""

    html_body = _get_base_template("Welcome to ResumeAI", content_html, callout_note)
    return _send_mime_email(to_email, subject, text_body, html_body, url)

def send_closed_beta_welcome_email(to_email: str, recipient_name: str = "", login_url: str = "") -> dict:
    """
    Sends a clean Closed Beta welcome email.
    """
    subject = "Welcome to the ResumeAI Closed Beta"
    name = recipient_name or "there"
    url = login_url or "http://server.shriyashpatil.in:9999/login"

    content_html = f"""
      <h1 style="margin: 0 0 16px 0; font-size: 17px; font-weight: 600; color: #171717; letter-spacing: -0.2px;">
        Welcome to the Closed Beta
      </h1>
      <p style="margin: 0 0 16px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        Hello {name}, you have been granted early access to the ResumeAI Closed Beta.
      </p>
      <p style="margin: 0 0 16px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        As a closed beta tester, you have full access to our AI resume tailor, PDF/Word export studio, cover letter assistant, and job application tracking tools.
      </p>
      <div style="margin: 24px 0 8px 0;">
        <a href="{url}" class="btn">
          Access Closed Beta
        </a>
      </div>
    """

    callout_note = "Your feedback helps shape the platform. If you encounter any issues or have suggestions, please reply directly to this email."

    text_body = f"""Hello {name},

Welcome to the ResumeAI Closed Beta! You have been granted early access.

Access your dashboard here:
{url}

As a closed beta member, you have full access to our AI resume tailor, document export studio, and application tracking pipeline.

If you have any feedback or notice any issues, feel free to reply directly to this email.

— The ResumeAI Team
app@shriyashpatil.in
"""

    html_body = _get_base_template("ResumeAI Closed Beta", content_html, callout_note)
    return _send_mime_email(to_email, subject, text_body, html_body, url)

def send_thank_you_email(to_email: str, recipient_name: str = "", login_url: str = "") -> dict:
    """
    Sends a clean, sincere Thank You email to users.
    """
    subject = "Thank you for being part of ResumeAI"
    name = recipient_name or "there"
    url = login_url or "http://server.shriyashpatil.in:9999/login"

    content_html = f"""
      <h1 style="margin: 0 0 16px 0; font-size: 17px; font-weight: 600; color: #171717; letter-spacing: -0.2px;">
        Thank you for being with us
      </h1>
      <p style="margin: 0 0 16px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        Hello {name},
      </p>
      <p style="margin: 0 0 16px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        We wanted to take a moment to thank you for trying out ResumeAI. Your early support, participation, and feedback mean a great deal as we continue refining the platform.
      </p>
      <p style="margin: 0 0 20px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        If there is ever anything you would like to see added, improved, or customized, feel free to reach out anytime.
      </p>
      <div style="margin: 24px 0 8px 0;">
        <a href="{url}" class="btn">
          Open Workspace
        </a>
      </div>
    """

    callout_note = "You can always reply directly to this email with your feedback or feature requests."

    text_body = f"""Hello {name},

Thank you for being part of ResumeAI.

Your early participation and support mean a lot to us as we continue improving the platform.

Access your workspace:
{url}

If you have any suggestions or feedback, feel free to reply directly to this email.

— The ResumeAI Team
app@shriyashpatil.in
"""

    html_body = _get_base_template("Thank You from ResumeAI", content_html, callout_note)
    return _send_mime_email(to_email, subject, text_body, html_body, url)

def send_admin_promotion_email(to_email: str, recipient_name: str = "", login_url: str = "") -> dict:
    """
    Sends an administrative role assignment notification email.
    """
    subject = "You have been granted Administrator access to ResumeAI"
    name = recipient_name or "there"
    url = login_url or "http://server.shriyashpatil.in:9999/admin"

    content_html = f"""
      <h1 style="margin: 0 0 16px 0; font-size: 17px; font-weight: 600; color: #171717; letter-spacing: -0.2px;">
        Administrator Access Granted
      </h1>
      <p style="margin: 0 0 16px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        Hello {name},
      </p>
      <p style="margin: 0 0 16px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        Your account on ResumeAI has been selected and granted <strong>Administrator privileges</strong>.
      </p>
      <p style="margin: 0 0 20px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        You now have access to the Admin Dashboard, system settings, user management, and platform controls.
      </p>
      <div style="margin: 24px 0 8px 0;">
        <a href="{url}" class="btn">
          Access Admin Dashboard
        </a>
      </div>
    """

    callout_note = "Please ensure your account credentials remain secure."

    text_body = f"""Hello {name},

Your account on ResumeAI has been granted Administrator privileges.

You can access the Admin Dashboard here:
{url}

— The ResumeAI Team
app@shriyashpatil.in
"""

    html_body = _get_base_template("Administrator Access Granted", content_html, callout_note)
    return _send_mime_email(to_email, subject, text_body, html_body, url)

def send_admin_congratulations_email(to_email: str, recipient_name: str = "", login_url: str = "") -> dict:
    """
    Sends a clean congratulations email for the Administrator role appointment.
    """
    subject = "Congratulations on your appointment as Administrator — ResumeAI"
    name = recipient_name or "there"
    url = login_url or "http://server.shriyashpatil.in:9999/admin"

    content_html = f"""
      <h1 style="margin: 0 0 16px 0; font-size: 17px; font-weight: 600; color: #171717; letter-spacing: -0.2px;">
        Congratulations on your new role
      </h1>
      <p style="margin: 0 0 16px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        Hello {name},
      </p>
      <p style="margin: 0 0 16px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        Congratulations! You have been selected and officially appointed as an <strong>Administrator</strong> for ResumeAI.
      </p>
      <p style="margin: 0 0 20px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        We are excited to have you oversee platform operations, review user activities, and manage platform configurations.
      </p>
      <div style="margin: 24px 0 8px 0;">
        <a href="{url}" class="btn">
          Open Admin Portal
        </a>
      </div>
    """

    callout_note = "You can access all administrative controls directly from the Admin Portal link above."

    text_body = f"""Hello {name},

Congratulations! You have been appointed as an Administrator for ResumeAI.

We are excited to have you manage platform operations and configurations.

Access your admin portal here:
{url}

— The ResumeAI Team
app@shriyashpatil.in
"""

    html_body = _get_base_template("Congratulations - Administrator Appointment", content_html, callout_note)
    return _send_mime_email(to_email, subject, text_body, html_body, url)

def send_profile_completion_reminder_email(to_email: str, recipient_name: str = "", profile_url: str = "") -> dict:
    """
    Sends a clean profile completion reminder email.
    """
    subject = "Complete your Master Profile on ResumeAI"
    name = recipient_name or "there"
    url = profile_url or "http://server.shriyashpatil.in:9999/profile"

    content_html = f"""
      <h1 style="margin: 0 0 16px 0; font-size: 17px; font-weight: 600; color: #171717; letter-spacing: -0.2px;">
        Complete your profile
      </h1>
      <p style="margin: 0 0 16px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        Hello {name},
      </p>
      <p style="margin: 0 0 16px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        To get the most accurate AI resume tailoring and personalized career insights, please take a moment to complete your <strong>Master Profile</strong>.
      </p>
      <p style="margin: 0 0 20px 0; font-size: 14px; color: #404040; line-height: 1.6;">
        You can add your work experiences, education, technical skills, and project highlights, or simply upload an existing resume to auto-fill your details.
      </p>
      <div style="margin: 24px 0 8px 0;">
        <a href="{url}" class="btn">
          Complete Profile
        </a>
      </div>
    """

    callout_note = "A complete profile allows the AI generator to tailor bullet points and skill alignments with maximum precision."

    text_body = f"""Hello {name},

Please take a moment to complete your Master Profile on ResumeAI.

Complete your profile here:
{url}

Adding your experiences, education, and skills helps the AI generator tailor your resumes with precision.

— The ResumeAI Team
app@shriyashpatil.in
"""

    html_body = _get_base_template("Complete your Master Profile", content_html, callout_note)
    return _send_mime_email(to_email, subject, text_body, html_body, url)











def _send_mime_email(to_email: str, subject: str, text_body: str, html_body: str, fallback_link: str = "") -> dict:
    """Helper to dispatch email over SMTP SSL / TLS with graceful error handling."""
    if not SMTP_PASSWORD:
        print(f"\n[SMTP SIMULATION] To: {to_email} | Subject: {subject}")
        return {"success": True, "simulated": True, "message": "SMTP password not set.", "reset_link": fallback_link}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg["To"] = to_email

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=15)
        else:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15)
            server.starttls()

        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM_EMAIL, [to_email], msg.as_string())
        server.quit()

        return {"success": True, "simulated": False, "message": f"Email successfully sent to {to_email}."}
    except Exception as e:
        print(f"[SMTP ERROR] Failed to send email via SMTP ({SMTP_SERVER}:{SMTP_PORT}): {str(e)}")
        return {"success": False, "simulated": False, "error": f"Failed to send email: {str(e)}", "reset_link": fallback_link}
