import os
from typing import Dict, Any, Optional
from jinja2 import Template
from weasyprint import HTML, CSS
from doc_service import generate_qr_code_base64

# ---------- FONT DEFINITIONS & GOOGLE FONTS ----------
FONTS = {
    "inter": {
        "name": "Inter (Clean & Modern)",
        "font_family": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "google_font": "Inter:wght@300;400;500;600;700;800",
        "docx_font": "Calibri"
    },
    "roboto": {
        "name": "Roboto (Crisp & Technical)",
        "font_family": "'Roboto', -apple-system, BlinkMacSystemFont, sans-serif",
        "google_font": "Roboto:wght@300;400;500;700;900",
        "docx_font": "Arial"
    },
    "merriweather": {
        "name": "Merriweather (Classic Editorial Serif)",
        "font_family": "'Merriweather', 'Georgia', serif",
        "google_font": "Merriweather:ital,wght@0,300;0,400;0,700;1,300;1,400",
        "docx_font": "Georgia"
    },
    "jetbrains": {
        "name": "JetBrains Mono (Developer Terminal)",
        "font_family": "'JetBrains Mono', 'Consolas', 'Courier New', monospace",
        "google_font": "JetBrains+Mono:wght@300;400;500;700",
        "docx_font": "Consolas"
    },
    "playfair": {
        "name": "Playfair Display (Executive Luxury)",
        "font_family": "'Playfair Display', 'Times New Roman', serif",
        "google_font": "Playfair+Display:ital,wght@0,400;0,600;0,700;1,400",
        "docx_font": "Times New Roman"
    },
    "lato": {
        "name": "Lato (Warm & Balanced)",
        "font_family": "'Lato', 'Helvetica Neue', Arial, sans-serif",
        "google_font": "Lato:wght@300;400;700;900",
        "docx_font": "Calibri"
    }
}

# ---------- 1. MODERN TEMPLATE ----------
MODERN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{% if google_font %}
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={{ google_font }}&display=swap">
{% endif %}
<style>
  @page {
    size: A4;
    {% if single_page %}
    margin: 8mm 10mm 8mm 10mm;
    {% else %}
    margin: 12mm 15mm 12mm 15mm;
    {% endif %}
  }
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  body {
    font-family: {{ font_family }};
    color: #1e293b;
    line-height: {% if single_page %}1.25{% else %}1.45{% endif %};
    font-size: {% if single_page %}8.5pt{% else %}10pt{% endif %};
    background-color: #ffffff;
  }
  .header {
    border-bottom: 2px solid {{ accent_color }};
    padding-bottom: {% if single_page %}4px{% else %}6px{% endif %};
    margin-bottom: {% if single_page %}6px{% else %}10px{% endif %};
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .header-left {
    flex: 1;
  }
  .header-with-photo {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .profile-photo {
    width: {% if single_page %}48px{% else %}60px{% endif %};
    height: {% if single_page %}48px{% else %}60px{% endif %};
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid {{ accent_color }};
    flex-shrink: 0;
  }
  .header-badges {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .qr-box {
    text-align: center;
    margin-left: 12px;
  }
  .qr-img {
    width: {% if single_page %}40px{% else %}50px{% endif %};
    height: {% if single_page %}40px{% else %}50px{% endif %};
  }
  .qr-label {
    font-size: 6.5pt;
    color: #64748b;
    margin-top: 1px;
  }
  .name {
    font-size: {% if single_page %}16pt{% else %}20pt{% endif %};
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -0.5px;
    line-height: 1.15;
  }
  .title {
    font-size: {% if single_page %}9.5pt{% else %}11pt{% endif %};
    font-weight: 600;
    color: {{ accent_color }};
    margin-top: 2px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .contacts {
    margin-top: 3px;
    font-size: {% if single_page %}7.5pt{% else %}8.5pt{% endif %};
    color: #475569;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .section {
    margin-bottom: {% if single_page %}8px{% else %}12px{% endif %};
  }
  .section-title {
    font-size: {% if single_page %}9.5pt{% else %}11pt{% endif %};
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #0f172a;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 2px;
    margin-bottom: {% if single_page %}4px{% else %}6px{% endif %};
  }
  .summary-text {
    font-size: {% if single_page %}8.5pt{% else %}9.5pt{% endif %};
    color: #334155;
    text-align: justify;
  }
  .skills-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .skill-badge {
    background-color: #f1f5f9;
    color: #1e293b;
    border: 1px solid #e2e8f0;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: {% if single_page %}7.5pt{% else %}8.5pt{% endif %};
    font-weight: 500;
  }
  .job, .edu-item, .proj-item {
    margin-bottom: {% if single_page %}5px{% else %}8px{% endif %};
    page-break-inside: avoid;
  }
  .job-header, .edu-header, .proj-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  .job-role {
    font-weight: 700;
    font-size: {% if single_page %}9pt{% else %}10pt{% endif %};
    color: #0f172a;
  }
  .job-company {
    font-weight: 600;
    color: {{ accent_color }};
  }
  .job-meta, .edu-meta {
    font-size: {% if single_page %}7.5pt{% else %}8.5pt{% endif %};
    color: #64748b;
    text-align: right;
  }
  ul.highlights {
    margin-top: 2px;
    margin-left: 14px;
  }
  ul.highlights li {
    font-size: {% if single_page %}8pt{% else %}9.5pt{% endif %};
    color: #334155;
    margin-bottom: {% if single_page %}1.5px{% else %}3px{% endif %};
  }
</style>
</head>
<body>
  <div class="header">
    <div class="header-left">
      {% if photo_base64 %}
      <div class="header-with-photo">
        <img src="{{ photo_base64 }}" class="profile-photo" alt="{{ resume.personal_info.full_name }}" />
        <div>
          <div class="name">{{ resume.personal_info.full_name }}</div>
          {% if resume.personal_info.professional_title %}
            <div class="title">{{ resume.personal_info.professional_title }}</div>
          {% endif %}
          <div class="contacts">
            {% if resume.personal_info.email %}<span>Email: {{ resume.personal_info.email }}</span>{% endif %}
            {% if resume.personal_info.phone %}<span>Tel: {{ resume.personal_info.phone }}</span>{% endif %}
            {% if resume.personal_info.location %}<span>Loc: {{ resume.personal_info.location }}</span>{% endif %}
            {% if resume.personal_info.linkedin_url %}<span>LinkedIn: {{ resume.personal_info.linkedin_url }}</span>{% endif %}
            {% if resume.personal_info.github_url %}<span>GitHub: {{ resume.personal_info.github_url }}</span>{% endif %}
            {% if resume.personal_info.portfolio_url %}<span>Web: {{ resume.personal_info.portfolio_url }}</span>{% endif %}
          </div>
        </div>
      </div>
      {% else %}
      <div>
        <div class="name">{{ resume.personal_info.full_name }}</div>
        {% if resume.personal_info.professional_title %}
          <div class="title">{{ resume.personal_info.professional_title }}</div>
        {% endif %}
        <div class="contacts">
          {% if resume.personal_info.email %}<span>Email: {{ resume.personal_info.email }}</span>{% endif %}
          {% if resume.personal_info.phone %}<span>Tel: {{ resume.personal_info.phone }}</span>{% endif %}
          {% if resume.personal_info.location %}<span>Loc: {{ resume.personal_info.location }}</span>{% endif %}
          {% if resume.personal_info.linkedin_url %}<span>LinkedIn: {{ resume.personal_info.linkedin_url }}</span>{% endif %}
          {% if resume.personal_info.github_url %}<span>GitHub: {{ resume.personal_info.github_url }}</span>{% endif %}
          {% if resume.personal_info.portfolio_url %}<span>Web: {{ resume.personal_info.portfolio_url }}</span>{% endif %}
        </div>
      </div>
      {% endif %}
    </div>
    {% if qr_code_base64 %}
    <div class="qr-box">
      <img src="{{ qr_code_base64 }}" class="qr-img" />
      <div class="qr-label">Digital Profile</div>
    </div>
    {% endif %}
  </div>

  {% if resume.summary %}
  <div class="section">
    <div class="section-title">Executive Summary</div>
    <div class="summary-text">{{ resume.summary }}</div>
  </div>
  {% endif %}

  {% if resume.core_competencies %}
  <div class="section">
    <div class="section-title">Core Competencies & Skills</div>
    <div class="skills-grid">
      {% if resume.core_competencies is string %}
        <span class="skill-badge">{{ resume.core_competencies }}</span>
      {% else %}
        {% for skill in resume.core_competencies %}
          <span class="skill-badge">{{ skill }}</span>
        {% endfor %}
      {% endif %}
    </div>
  </div>
  {% endif %}

  {% if resume.experience %}
  <div class="section">
    <div class="section-title">Professional Experience</div>
    {% for job in resume.experience %}
      <div class="job">
        <div class="job-header">
          <div>
            <span class="job-role">{{ job.title }}</span>
            {% if job.company %}<span class="job-company"> • {{ job.company }}</span>{% endif %}
          </div>
          <div class="job-meta">
            {% if job.start_date or job.end_date %}<span>{{ job.start_date }} – {{ job.end_date }}</span>{% endif %}
            {% if job.location %} | <span>{{ job.location }}</span>{% endif %}
          </div>
        </div>
        {% if job.highlights %}
        <ul class="highlights">
          {% for hl in job.highlights %}
            <li>{{ hl }}</li>
          {% endfor %}
        </ul>
        {% endif %}
      </div>
    {% endfor %}
  </div>
  {% endif %}

  {% if resume.education %}
  <div class="section">
    <div class="section-title">Education</div>
    {% for edu in resume.education %}
      <div class="edu-item">
        <div class="edu-header">
          <div>
            <span class="job-role">{{ edu.degree }}</span>
            <span class="job-company"> • {{ edu.institution }}</span>
          </div>
          <div class="edu-meta">
            {% if edu.graduation_date %}<span>{{ edu.graduation_date }}</span>{% endif %}
            {% if edu.location %} | <span>{{ edu.location }}</span>{% endif %}
          </div>
        </div>
        {% if edu.details %}
          <div class="summary-text" style="font-size: 8.5pt; margin-top: 1px;">{{ edu.details }}</div>
        {% endif %}
      </div>
    {% endfor %}
  </div>
  {% endif %}

  {% if resume.projects %}
  <div class="section">
    <div class="section-title">Key Projects</div>
    {% for proj in resume.projects %}
      <div class="proj-item">
        <div class="proj-header">
          <div>
            <span class="job-role">{{ proj.name }}</span>
            {% if proj.technologies %}
              <span style="font-size: 8pt; color: #64748b;"> ({{ proj.technologies|join(', ') }})</span>
            {% endif %}
          </div>
          {% if proj.link %}
            <div class="edu-meta">{{ proj.link }}</div>
          {% endif %}
        </div>
        {% if proj.description %}
          <div class="summary-text" style="font-size: 8.5pt; margin-top: 1px;">{{ proj.description }}</div>
        {% endif %}
      </div>
    {% endfor %}
  </div>
  {% endif %}

  {% if resume.certifications %}
  <div class="section">
    <div class="section-title">Certifications</div>
    <div class="skills-grid">
      {% for cert in resume.certifications %}
        <span class="skill-badge">{{ cert.name }} - {{ cert.issuer }} {% if cert.date %}({{ cert.date }}){% endif %}</span>
      {% endfor %}
    </div>
  </div>
  {% endif %}

  {% if resume.custom_sections %}
    {% for sec in resume.custom_sections %}
      <div class="section">
        <div class="section-title">{{ sec.heading }}</div>
        {% if sec.get('items') or sec['items'] %}
        <ul class="highlights">
          {% for item in sec['items'] %}
            <li>{{ item }}</li>
          {% endfor %}
        </ul>
        {% endif %}
      </div>
    {% endfor %}
  {% endif %}
</body>
</html>
"""

# ---------- 2. EXECUTIVE TEMPLATE ----------
EXECUTIVE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{% if google_font %}
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={{ google_font }}&display=swap">
{% endif %}
<style>
  @page {
    size: A4;
    {% if single_page %}
    margin: 8mm 12mm 8mm 12mm;
    {% else %}
    margin: 14mm 16mm 14mm 16mm;
    {% endif %}
  }
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  body {
    font-family: {{ font_family }};
    color: #1a1a1a;
    line-height: {% if single_page %}1.28{% else %}1.45{% endif %};
    font-size: {% if single_page %}8.5pt{% else %}10pt{% endif %};
  }
  .header {
    border-bottom: 2px solid {{ accent_color }};
    padding-bottom: {% if single_page %}4px{% else %}6px{% endif %};
    margin-bottom: {% if single_page %}6px{% else %}10px{% endif %};
    {% if photo_base64 or qr_code_base64 %}
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    {% else %}
    text-align: center;
    {% endif %}
  }
  .header-center {
    flex: 1;
    text-align: center;
  }
  .profile-photo {
    width: {% if single_page %}48px{% else %}60px{% endif %};
    height: {% if single_page %}48px{% else %}60px{% endif %};
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid {{ accent_color }};
    flex-shrink: 0;
  }
  .name {
    font-size: {% if single_page %}18pt{% else %}22pt{% endif %};
    font-weight: bold;
    color: #000000;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    line-height: 1.15;
  }
  .title {
    font-size: {% if single_page %}9.5pt{% else %}11pt{% endif %};
    color: {{ accent_color }};
    font-style: italic;
    margin-top: 2px;
  }
  .contacts {
    margin-top: 3px;
    font-size: 8pt;
    color: #555555;
  }
  .qr-box {
    text-align: center;
    flex-shrink: 0;
  }
  .qr-img {
    width: {% if single_page %}36px{% else %}45px{% endif %};
    height: {% if single_page %}36px{% else %}45px{% endif %};
  }
  .qr-label {
    font-size: 6pt;
    color: #64748b;
  }
  .section {
    margin-bottom: {% if single_page %}8px{% else %}12px{% endif %};
  }
  .section-title {
    font-size: 10.5pt;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: {{ accent_color }};
    border-bottom: 1px solid #d1d5db;
    padding-bottom: 2px;
    margin-bottom: 5px;
  }
  .summary-text {
    font-size: 9pt;
    color: #222222;
    text-align: justify;
  }
  .skills-container {
    font-size: 8.5pt;
    line-height: 1.4;
  }
  .job, .edu-item, .proj-item {
    margin-bottom: 6px;
    page-break-inside: avoid;
  }
  .job-header {
    display: flex;
    justify-content: space-between;
    font-weight: bold;
  }
  .job-company {
    font-style: italic;
    color: #444;
  }
  ul.highlights {
    margin-top: 2px;
    margin-left: 14px;
  }
  ul.highlights li {
    font-size: 8.5pt;
    margin-bottom: 2px;
  }
</style>
</head>
<body>
  <div class="header">
    {% if photo_base64 %}
      <img src="{{ photo_base64 }}" class="profile-photo" alt="{{ resume.personal_info.full_name }}" />
    {% endif %}
    <div class="header-center">
      <div class="name">{{ resume.personal_info.full_name }}</div>
      {% if resume.personal_info.professional_title %}
        <div class="title">{{ resume.personal_info.professional_title }}</div>
      {% endif %}
      <div class="contacts">
        {% set c_list = [] %}
        {% if resume.personal_info.email %}{% set _ = c_list.append(resume.personal_info.email) %}{% endif %}
        {% if resume.personal_info.phone %}{% set _ = c_list.append(resume.personal_info.phone) %}{% endif %}
        {% if resume.personal_info.location %}{% set _ = c_list.append(resume.personal_info.location) %}{% endif %}
        {% if resume.personal_info.linkedin_url %}{% set _ = c_list.append(resume.personal_info.linkedin_url) %}{% endif %}
        {{ c_list|join('  •  ') }}
      </div>
    </div>
    {% if qr_code_base64 %}
    <div class="qr-box">
      <img src="{{ qr_code_base64 }}" class="qr-img" />
      <div class="qr-label">Digital Profile</div>
    </div>
    {% endif %}
  </div>

  {% if resume.summary %}
  <div class="section">
    <div class="section-title">Executive Profile</div>
    <div class="summary-text">{{ resume.summary }}</div>
  </div>
  {% endif %}

  {% if resume.core_competencies %}
  <div class="section">
    <div class="section-title">Areas of Expertise</div>
    <div class="skills-container">
      {% if resume.core_competencies is string %}
        {{ resume.core_competencies }}
      {% else %}
        {{ resume.core_competencies|join('  •  ') }}
      {% endif %}
    </div>
  </div>
  {% endif %}

  {% if resume.experience %}
  <div class="section">
    <div class="section-title">Professional Experience</div>
    {% for job in resume.experience %}
      <div class="job">
        <div class="job-header">
          <span>{{ job.title }}</span>
          <span>{% if job.start_date or job.end_date %}{{ job.start_date }} – {{ job.end_date }}{% endif %}</span>
        </div>
        <div style="font-size: 8.5pt; color: #444; display: flex; justify-content: space-between;">
          <span>{{ job.company }}</span>
          <span>{{ job.location }}</span>
        </div>
        {% if job.highlights %}
        <ul class="highlights">
          {% for hl in job.highlights %}
            <li>{{ hl }}</li>
          {% endfor %}
        </ul>
        {% endif %}
      </div>
    {% endfor %}
  </div>
  {% endif %}

  {% if resume.education %}
  <div class="section">
    <div class="section-title">Education</div>
    {% for edu in resume.education %}
      <div class="edu-item">
        <div class="job-header">
          <span>{{ edu.degree }}</span>
          <span>{{ edu.graduation_date }}</span>
        </div>
        <div style="font-size: 8.5pt; color: #444;">{{ edu.institution }}{% if edu.location %} • {{ edu.location }}{% endif %}</div>
        {% if edu.details %}<div style="font-size: 8pt; margin-top: 1px;">{{ edu.details }}</div>{% endif %}
      </div>
    {% endfor %}
  </div>
  {% endif %}

  {% if resume.projects %}
  <div class="section">
    <div class="section-title">Key Projects</div>
    {% for proj in resume.projects %}
      <div class="proj-item">
        <div class="job-header">
          <span>{{ proj.name }}</span>
          {% if proj.link %}<span style="font-size: 8pt; font-weight: normal;">{{ proj.link }}</span>{% endif %}
        </div>
        {% if proj.description %}<div style="font-size: 8.5pt;">{{ proj.description }}</div>{% endif %}
      </div>
    {% endfor %}
  </div>
  {% endif %}

  {% if resume.certifications %}
  <div class="section">
    <div class="section-title">Certifications</div>
    <ul class="highlights">
      {% for cert in resume.certifications %}
        <li><strong>{{ cert.name }}</strong> – {{ cert.issuer }} {% if cert.date %}({{ cert.date }}){% endif %}</li>
      {% endfor %}
    </ul>
  </div>
  {% endif %}

  {% if resume.custom_sections %}
    {% for sec in resume.custom_sections %}
      <div class="section">
        <div class="section-title">{{ sec.heading }}</div>
        {% if sec.get('items') or sec['items'] %}
        <ul class="highlights">
          {% for item in sec['items'] %}
            <li>{{ item }}</li>
          {% endfor %}
        </ul>
        {% endif %}
      </div>
    {% endfor %}
  {% endif %}
</body>
</html>
"""

# ---------- 3. CREATIVE TWO-COLUMN SIDEBAR TEMPLATE ----------
CREATIVE_SIDEBAR_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{% if google_font %}
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={{ google_font }}&display=swap">
{% endif %}
<style>
  @page {
    size: A4;
    margin: 0;
  }
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  body {
    font-family: {{ font_family }};
    color: #1e293b;
    display: table;
    width: 100%;
    height: 100%;
    background-color: #ffffff;
  }
  .sidebar {
    display: table-cell;
    width: 32%;
    background-color: #f8fafc;
    border-right: 2px solid #e2e8f0;
    padding: {% if single_page %}8mm 8mm{% else %}10mm 8mm{% endif %};
    vertical-align: top;
  }
  .main-content {
    display: table-cell;
    width: 68%;
    padding: {% if single_page %}8mm 10mm{% else %}10mm 10mm{% endif %};
    vertical-align: top;
  }
  .profile-photo {
    width: 65px;
    height: 65px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid {{ accent_color }};
    margin-bottom: 8px;
    display: block;
  }
  .name {
    font-size: 18pt;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.15;
  }
  .title {
    font-size: 9.5pt;
    font-weight: 600;
    color: {{ accent_color }};
    margin-top: 3px;
    margin-bottom: 10px;
  }
  .side-section-title {
    font-size: 8.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: {{ accent_color }};
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 3px;
    margin-top: 14px;
    margin-bottom: 8px;
  }
  .main-section-title {
    font-size: 10.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: {{ accent_color }};
    border-bottom: 1.5px solid {{ accent_color }};
    padding-bottom: 3px;
    margin-bottom: 8px;
    margin-top: 12px;
  }
  .main-section-title:first-child {
    margin-top: 0;
  }
  .side-item {
    font-size: 8pt;
    color: #334155;
    margin-bottom: 5px;
    word-break: break-word;
  }
  .skill-tag {
    display: inline-block;
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    color: #1e293b;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 7.5pt;
    margin: 2px 2px 2px 0;
  }
  .job {
    margin-bottom: 8px;
    page-break-inside: avoid;
  }
  .job-header {
    display: flex;
    justify-content: space-between;
    font-size: 9.5pt;
    font-weight: 700;
    color: #0f172a;
  }
  .job-sub {
    font-size: 8pt;
    color: #64748b;
    margin-bottom: 3px;
  }
  ul.highlights {
    margin-left: 14px;
  }
  ul.highlights li {
    font-size: 8.5pt;
    color: #334155;
    margin-bottom: 2px;
    line-height: 1.35;
  }
  .qr-center {
    text-align: center;
    margin-top: 15px;
  }
  .qr-center img {
    width: 60px;
    height: 60px;
  }
</style>
</head>
<body>
  <div class="sidebar">
    {% if photo_base64 %}
      <img src="{{ photo_base64 }}" class="profile-photo" alt="{{ resume.personal_info.full_name }}" />
    {% endif %}
    <div class="name">{{ resume.personal_info.full_name }}</div>
    {% if resume.personal_info.professional_title %}
      <div class="title">{{ resume.personal_info.professional_title }}</div>
    {% endif %}

    <div class="side-section-title">Contact</div>
    {% if resume.personal_info.email %}<div class="side-item">Email: {{ resume.personal_info.email }}</div>{% endif %}
    {% if resume.personal_info.phone %}<div class="side-item">Tel: {{ resume.personal_info.phone }}</div>{% endif %}
    {% if resume.personal_info.location %}<div class="side-item">Loc: {{ resume.personal_info.location }}</div>{% endif %}
    {% if resume.personal_info.linkedin_url %}<div class="side-item">LinkedIn: {{ resume.personal_info.linkedin_url }}</div>{% endif %}
    {% if resume.personal_info.github_url %}<div class="side-item">GitHub: {{ resume.personal_info.github_url }}</div>{% endif %}

    {% if resume.core_competencies %}
    <div class="side-section-title">Skills & Tools</div>
    <div>
      {% if resume.core_competencies is string %}
        <span class="skill-tag">{{ resume.core_competencies }}</span>
      {% else %}
        {% for s in resume.core_competencies %}
          <span class="skill-tag">{{ s }}</span>
        {% endfor %}
      {% endif %}
    </div>
    {% endif %}

    {% if resume.education %}
    <div class="side-section-title">Education</div>
    {% for edu in resume.education %}
      <div class="side-item" style="margin-bottom: 6px;">
        <strong>{{ edu.degree }}</strong><br>
        {{ edu.institution }} ({{ edu.graduation_date }})
        {% if edu.details %}<br><span style="font-size: 7pt; color: #64748b;">{{ edu.details }}</span>{% endif %}
      </div>
    {% endfor %}
    {% endif %}

    {% if resume.certifications %}
    <div class="side-section-title">Certifications</div>
    {% for cert in resume.certifications %}
      <div class="side-item">{{ cert.name }}</div>
    {% endfor %}
    {% endif %}

    {% if qr_code_base64 %}
    <div class="qr-center">
      <img src="{{ qr_code_base64 }}" />
      <div style="font-size: 6.5pt; color: #64748b; margin-top: 2px;">Scan Profile</div>
    </div>
    {% endif %}
  </div>

  <div class="main-content">
    {% if resume.summary %}
    <div class="main-section-title">Summary</div>
    <div style="font-size: 9pt; line-height: 1.4; color: #334155; margin-bottom: 8px;">{{ resume.summary }}</div>
    {% endif %}

    {% if resume.experience %}
    <div class="main-section-title">Experience</div>
    {% for job in resume.experience %}
      <div class="job">
        <div class="job-header">
          <span>{{ job.title }}</span>
          <span style="font-size: 8pt; font-weight: normal; color: #64748b;">{{ job.start_date }} – {{ job.end_date }}</span>
        </div>
        <div class="job-sub">{{ job.company }} {% if job.location %}| {{ job.location }}{% endif %}</div>
        {% if job.highlights %}
        <ul class="highlights">
          {% for hl in job.highlights %}
            <li>{{ hl }}</li>
          {% endfor %}
        </ul>
        {% endif %}
      </div>
    {% endfor %}
    {% endif %}

    {% if resume.projects %}
    <div class="main-section-title">Projects</div>
    {% for proj in resume.projects %}
      <div class="job">
        <div class="job-header">
          <span>{{ proj.name }}</span>
          {% if proj.link %}<span style="font-size: 7.5pt; font-weight: normal;">{{ proj.link }}</span>{% endif %}
        </div>
        {% if proj.description %}
          <div style="font-size: 8.5pt; color: #334155;">{{ proj.description }}</div>
        {% endif %}
      </div>
    {% endfor %}
    {% endif %}

    {% if resume.custom_sections %}
      {% for sec in resume.custom_sections %}
        <div class="main-section-title">{{ sec.heading }}</div>
        {% if sec.get('items') or sec['items'] %}
        <ul class="highlights">
          {% for item in sec['items'] %}
            <li>{{ item }}</li>
          {% endfor %}
        </ul>
        {% endif %}
      {% endfor %}
    {% endif %}
  </div>
</body>
</html>
"""

# ---------- 4. TECH TEAL TEMPLATE ----------
TECH_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{% if google_font %}
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={{ google_font }}&display=swap">
{% endif %}
<style>
  @page {
    size: A4;
    margin: 10mm 14mm 10mm 14mm;
  }
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  body {
    font-family: {{ font_family }};
    color: #1e293b;
    line-height: 1.35;
    font-size: 9pt;
  }
  .header {
    background-color: #0f172a;
    color: #ffffff;
    padding: {% if single_page %}8px 12px{% else %}10px 14px{% endif %};
    border-radius: 4px;
    margin-bottom: {% if single_page %}8px{% else %}10px{% endif %};
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .header-left {
    flex: 1;
    {% if photo_base64 %}
    display: flex;
    align-items: center;
    gap: 12px;
    {% endif %}
  }
  .profile-photo {
    width: {% if single_page %}45px{% else %}55px{% endif %};
    height: {% if single_page %}45px{% else %}55px{% endif %};
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid #38bdf8;
    flex-shrink: 0;
  }
  .qr-box {
    text-align: center;
    margin-left: 12px;
    background: #ffffff;
    padding: 3px;
    border-radius: 4px;
  }
  .qr-img {
    width: {% if single_page %}36px{% else %}45px{% endif %};
    height: {% if single_page %}36px{% else %}45px{% endif %};
    display: block;
  }
  .qr-label {
    font-size: 6pt;
    color: #0f172a;
    font-weight: bold;
  }
  .name {
    font-size: {% if single_page %}16pt{% else %}18pt{% endif %};
    font-weight: 700;
    color: #38bdf8;
    line-height: 1.15;
  }
  .title {
    font-size: 9.5pt;
    color: #94a3b8;
    margin-top: 1px;
  }
  .contacts {
    font-size: 8pt;
    color: #cbd5e1;
    margin-top: 3px;
  }
  .section-title {
    font-size: 10pt;
    font-weight: 700;
    color: {{ accent_color }};
    border-bottom: 1px solid {{ accent_color }};
    padding-bottom: 2px;
    margin-top: 10px;
    margin-bottom: 6px;
    text-transform: uppercase;
  }
  .skill-badge {
    background-color: #e0f2fe;
    color: #0369a1;
    border: 1px solid #bae6fd;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 8pt;
    display: inline-block;
    margin: 1px;
  }
  .job-header {
    display: flex;
    justify-content: space-between;
    font-weight: bold;
    font-size: 9.5pt;
  }
  ul.highlights {
    margin-left: 14px;
  }
  ul.highlights li {
    font-size: 8.5pt;
    margin-bottom: 2px;
  }
</style>
</head>
<body>
  <div class="header">
    <div class="header-left">
      {% if photo_base64 %}
        <img src="{{ photo_base64 }}" class="profile-photo" alt="{{ resume.personal_info.full_name }}" />
      {% endif %}
      <div>
        <div class="name">&gt; {{ resume.personal_info.full_name }}</div>
        {% if resume.personal_info.professional_title %}
          <div class="title">// {{ resume.personal_info.professional_title }}</div>
        {% endif %}
        <div class="contacts">
          {% if resume.personal_info.email %}email: {{ resume.personal_info.email }} | {% endif %}
          {% if resume.personal_info.phone %}phone: {{ resume.personal_info.phone }} | {% endif %}
          {% if resume.personal_info.github_url %}github: {{ resume.personal_info.github_url }}{% endif %}
        </div>
      </div>
    </div>
    {% if qr_code_base64 %}
    <div class="qr-box">
      <img src="{{ qr_code_base64 }}" class="qr-img" />
      <div class="qr-label">PROFILE</div>
    </div>
    {% endif %}
  </div>

  {% if resume.summary %}
  <div class="section-title">## 01. Overview</div>
  <div style="font-size: 8.5pt; color: #334155;">{{ resume.summary }}</div>
  {% endif %}

  {% if resume.core_competencies %}
  <div class="section-title">## 02. Stack & Capabilities</div>
  <div>
    {% if resume.core_competencies is string %}
      <span class="skill-badge">{{ resume.core_competencies }}</span>
    {% else %}
      {% for s in resume.core_competencies %}
        <span class="skill-badge">{{ s }}</span>
      {% endfor %}
    {% endif %}
  </div>
  {% endif %}

  {% if resume.experience %}
  <div class="section-title">## 03. Engineering Experience</div>
  {% for job in resume.experience %}
    <div style="margin-bottom: 6px;">
      <div class="job-header">
        <span>{{ job.title }} @ {{ job.company }}</span>
        <span style="font-size: 8pt; color: #64748b;">{{ job.start_date }} - {{ job.end_date }}</span>
      </div>
      {% if job.highlights %}
      <ul class="highlights">
        {% for hl in job.highlights %}
          <li>{{ hl }}</li>
        {% endfor %}
      </ul>
      {% endif %}
    </div>
  {% endfor %}
  {% endif %}

  {% if resume.projects %}
  <div class="section-title">## 04. Systems & Projects</div>
  {% for proj in resume.projects %}
    <div style="margin-bottom: 5px;">
      <strong>{{ proj.name }}</strong> {% if proj.technologies %}<span style="color:#0369a1;">[{{ proj.technologies|join(', ') }}]</span>{% endif %}
      {% if proj.description %}<div style="font-size: 8.5pt;">{{ proj.description }}</div>{% endif %}
    </div>
  {% endfor %}
  {% endif %}

  {% if resume.education %}
  <div class="section-title">## 05. Education</div>
  {% for edu in resume.education %}
    <div style="font-size: 8.5pt; margin-bottom: 3px;">
      <strong>{{ edu.degree }}</strong> - {{ edu.institution }} ({{ edu.graduation_date }})
      {% if edu.details %}<span style="color:#0369a1; margin-left: 6px;">// {{ edu.details }}</span>{% endif %}
    </div>
  {% endfor %}
  {% endif %}

  {% if resume.custom_sections %}
    {% for sec in resume.custom_sections %}
      <div class="section-title">## {{ sec.heading }}</div>
      {% if sec.get('items') or sec['items'] %}
      <ul class="highlights">
        {% for item in sec['items'] %}
          <li>{{ item }}</li>
        {% endfor %}
      </ul>
      {% endif %}
    {% endfor %}
  {% endif %}
</body>
</html>
"""

TEMPLATES = {
    "modern": {"name": "Modern Blue (Clean & ATS-Optimized)", "template": MODERN_TEMPLATE},
    "executive": {"name": "Executive Serif (Classic & Elegant)", "template": EXECUTIVE_TEMPLATE},
    "creative_sidebar": {"name": "Creative Sidebar (Modern Two-Column)", "template": CREATIVE_SIDEBAR_TEMPLATE},
    "tech": {"name": "Tech Terminal (Developer & Systems)", "template": TECH_TEMPLATE}
}

def render_resume_html(
    resume_payload: dict,
    template_name: str = "modern",
    accent_color: str = "#2563eb",
    font_name: str = "inter",
    single_page: bool = False,
    include_qr: bool = True,
    qr_target_url: str = "",
    include_photo: bool = True,
    photo_url: str = ""
) -> str:
    res_data = resume_payload.get("resume", resume_payload)
    selected_tmpl = TEMPLATES.get(template_name, TEMPLATES["modern"])["template"]
    font_config = FONTS.get(font_name, FONTS["inter"])
    
    qr_code_b64 = ""
    if include_qr and qr_target_url:
        qr_code_b64 = generate_qr_code_base64(qr_target_url)

    # Determine photo to display
    photo_b64 = ""
    if include_photo:
        p_info = res_data.get("personal_info", {})
        photo_b64 = photo_url or p_info.get("photo_url") or p_info.get("profile_photo_url") or ""

    template = Template(selected_tmpl)
    return template.render(
        resume=res_data,
        accent_color=accent_color or "#2563eb",
        font_family=font_config["font_family"],
        google_font=font_config["google_font"],
        single_page=single_page,
        qr_code_base64=qr_code_b64,
        photo_base64=photo_b64
    )

def generate_pdf_from_resume_data(
    resume_payload: dict,
    template_name: str = "modern",
    accent_color: str = "#2563eb",
    font_name: str = "inter",
    single_page: bool = False,
    include_qr: bool = True,
    qr_target_url: str = "",
    include_photo: bool = True,
    photo_url: str = ""
) -> bytes:
    rendered_html = render_resume_html(
        resume_payload=resume_payload,
        template_name=template_name,
        accent_color=accent_color,
        font_name=font_name,
        single_page=single_page,
        include_qr=include_qr,
        qr_target_url=qr_target_url,
        include_photo=include_photo,
        photo_url=photo_url
    )
    return HTML(string=rendered_html).write_pdf()


