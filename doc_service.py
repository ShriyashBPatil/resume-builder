import io
import os
import base64
from typing import Dict, Any, Optional
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
import pypdf
import qrcode
from jinja2 import Template
from weasyprint import HTML, CSS

# ---------- TEXT EXTRACTION FROM UPLOADS ----------

def extract_text_from_file(file_stream: io.BytesIO, filename: str) -> str:
    """Extract raw text from PDF, DOCX, or TXT file uploads."""
    ext = os.path.splitext(filename)[1].lower()
    
    if ext == ".pdf":
        reader = pypdf.PdfReader(file_stream)
        text_parts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        return "\n".join(text_parts)
        
    elif ext in [".docx", ".doc"]:
        doc = docx.Document(file_stream)
        text_parts = []
        for p in doc.paragraphs:
            if p.text.strip():
                text_parts.append(p.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text_parts.append(cell.text)
        return "\n".join(text_parts)
        
    elif ext in [".txt", ".md", ".json"]:
        content = file_stream.read()
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("latin-1", errors="ignore")
            
    else:
        raise ValueError(f"Unsupported file format '{ext}'. Please upload a PDF, DOCX, or TXT file.")

# ---------- QR CODE GENERATION ----------

def generate_qr_code_base64(data: str) -> str:
    """Generate a Base64 PNG QR code string for embedding in HTML/PDF."""
    if not data:
        return ""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=1,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"

# ---------- DOCX RESUME EXPORT ----------

def hex_to_rgb(hex_str: str) -> RGBColor:
    hex_str = hex_str.lstrip("#")
    if len(hex_str) != 6:
        hex_str = "2563EB"
    return RGBColor(int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))

DOCX_FONTS = {
    "inter": "Calibri",
    "roboto": "Arial",
    "merriweather": "Georgia",
    "jetbrains": "Consolas",
    "playfair": "Times New Roman",
    "lato": "Calibri"
}

def generate_docx_from_resume_data(resume_payload: Dict[str, Any], accent_color_hex: str = "#2563eb", font_name: str = "inter") -> bytes:
    """Generates an ATS-compliant, beautifully styled Microsoft Word (.docx) document."""
    res = resume_payload.get("resume", resume_payload)
    info = res.get("personal_info", {})
    docx_font = DOCX_FONTS.get(font_name, "Calibri")
    
    doc = docx.Document()
    
    # Page setup (Standard Letter / A4 with 0.6 in margins)
    for section in doc.sections:
        section.top_margin = Inches(0.6)
        section.bottom_margin = Inches(0.6)
        section.left_margin = Inches(0.65)
        section.right_margin = Inches(0.65)

    primary_color = hex_to_rgb(accent_color_hex)
    dark_text = RGBColor(30, 41, 59)
    subtle_text = RGBColor(100, 116, 139)

    # Candidate Header
    name_p = doc.add_paragraph()
    name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_p.paragraph_format.space_before = Pt(0)
    name_p.paragraph_format.space_after = Pt(2)
    name_run = name_p.add_run(info.get("full_name", "Professional Resume"))
    name_run.bold = True
    name_run.font.size = Pt(22)
    name_run.font.name = docx_font
    name_run.font.color.rgb = primary_color

    if info.get("professional_title"):
        title_p = doc.add_paragraph()
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_p.paragraph_format.space_before = Pt(0)
        title_p.paragraph_format.space_after = Pt(4)
        title_run = title_p.add_run(info["professional_title"].upper())
        title_run.bold = True
        title_run.font.size = Pt(11)
        title_run.font.name = docx_font
        title_run.font.color.rgb = subtle_text

    # Contact line
    contacts = []
    if info.get("email"): contacts.append(info["email"])
    if info.get("phone"): contacts.append(info["phone"])
    if info.get("location"): contacts.append(info["location"])
    if info.get("linkedin_url"): contacts.append(info["linkedin_url"])
    if info.get("github_url"): contacts.append(info["github_url"])
    if info.get("portfolio_url"): contacts.append(info["portfolio_url"])

    if contacts:
        contact_p = doc.add_paragraph()
        contact_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        contact_p.paragraph_format.space_before = Pt(0)
        contact_p.paragraph_format.space_after = Pt(12)
        contact_run = contact_p.add_run("  •  ".join(contacts))
        contact_run.font.size = Pt(9.5)
        contact_run.font.name = docx_font
        contact_run.font.color.rgb = subtle_text

    def add_section_heading(title: str):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(title.upper())
        run.bold = True
        run.font.size = Pt(11.5)
        run.font.name = docx_font
        run.font.color.rgb = primary_color
        
        # Add bottom border via XML
        pPr = p._element.get_or_add_pPr()
        pBdr = parse_xml(r'<w:pBdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                         r'<w:bottom w:val="single" w:sz="6" w:space="1" w:color="CBD5E1"/>'
                         r'</w:pBdr>')
        pPr.append(pBdr)

    # Executive Summary
    if res.get("summary"):
        add_section_heading("Executive Summary")
        sum_p = doc.add_paragraph()
        sum_p.paragraph_format.space_before = Pt(2)
        sum_p.paragraph_format.space_after = Pt(6)
        sum_run = sum_p.add_run(res["summary"])
        sum_run.font.size = Pt(10)
        sum_run.font.name = docx_font
        sum_run.font.color.rgb = dark_text

    # Core Competencies / Skills
    if res.get("core_competencies"):
        add_section_heading("Core Competencies & Skills")
        skills_p = doc.add_paragraph()
        skills_p.paragraph_format.space_before = Pt(2)
        skills_p.paragraph_format.space_after = Pt(6)
        skills = res["core_competencies"]
        skills_text = " • ".join(skills) if isinstance(skills, list) else str(skills)
        sk_run = skills_p.add_run(skills_text)
        sk_run.font.size = Pt(10)
        sk_run.font.name = docx_font
        sk_run.font.color.rgb = dark_text

    # Professional Experience
    if res.get("experience"):
        add_section_heading("Professional Experience")
        for exp in res["experience"]:
            job_p = doc.add_paragraph()
            job_p.paragraph_format.space_before = Pt(6)
            job_p.paragraph_format.space_after = Pt(1)
            job_p.paragraph_format.keep_with_next = True
            
            # Left: Role & Company, Right: Date & Location
            r_title = job_p.add_run(exp.get("title", ""))
            r_title.bold = True
            r_title.font.size = Pt(10.5)
            r_title.font.name = docx_font
            r_title.font.color.rgb = dark_text
            
            r_comp = job_p.add_run(f" | {exp.get('company', '')}")
            r_comp.font.size = Pt(10.5)
            r_comp.font.name = docx_font
            r_comp.font.color.rgb = primary_color
            
            date_loc = []
            if exp.get("start_date") or exp.get("end_date"):
                date_loc.append(f"{exp.get('start_date', '')} – {exp.get('end_date', '')}")
            if exp.get("location"):
                date_loc.append(exp["location"])
            
            if date_loc:
                r_date = job_p.add_run(f"  ({', '.join(date_loc)})")
                r_date.italic = True
                r_date.font.size = Pt(9.5)
                r_date.font.name = docx_font
                r_date.font.color.rgb = subtle_text

            for hl in exp.get("highlights", []):
                hl_p = doc.add_paragraph(style='List Bullet')
                hl_p.paragraph_format.space_before = Pt(1)
                hl_p.paragraph_format.space_after = Pt(2)
                hl_run = hl_p.add_run(hl)
                hl_run.font.size = Pt(9.5)
                hl_run.font.name = docx_font
                hl_run.font.color.rgb = dark_text

    # Education
    if res.get("education"):
        add_section_heading("Education")
        for edu in res["education"]:
            edu_p = doc.add_paragraph()
            edu_p.paragraph_format.space_before = Pt(4)
            edu_p.paragraph_format.space_after = Pt(1)
            edu_p.paragraph_format.keep_with_next = True
            
            deg_run = edu_p.add_run(edu.get("degree", ""))
            deg_run.bold = True
            deg_run.font.size = Pt(10)
            deg_run.font.name = docx_font
            deg_run.font.color.rgb = dark_text
            
            inst_run = edu_p.add_run(f" — {edu.get('institution', '')}")
            inst_run.font.size = Pt(10)
            inst_run.font.name = docx_font
            inst_run.font.color.rgb = primary_color
            
            if edu.get("graduation_date"):
                d_run = edu_p.add_run(f" ({edu['graduation_date']})")
                d_run.italic = True
                d_run.font.size = Pt(9.5)
                d_run.font.name = docx_font
                d_run.font.color.rgb = subtle_text

            if edu.get("details"):
                det_p = doc.add_paragraph(style='List Bullet')
                det_p.paragraph_format.space_before = Pt(0)
                det_p.paragraph_format.space_after = Pt(2)
                det_run = det_p.add_run(edu["details"])
                det_run.font.size = Pt(9)
                det_run.font.name = docx_font
                det_run.font.color.rgb = dark_text

    # Projects
    if res.get("projects"):
        add_section_heading("Key Projects")
        for proj in res["projects"]:
            pr_p = doc.add_paragraph()
            pr_p.paragraph_format.space_before = Pt(4)
            pr_p.paragraph_format.space_after = Pt(1)
            pr_p.paragraph_format.keep_with_next = True
            
            p_name = pr_p.add_run(proj.get("name", ""))
            p_name.bold = True
            p_name.font.size = Pt(10)
            p_name.font.name = docx_font
            p_name.font.color.rgb = dark_text
            
            if proj.get("technologies"):
                tech_run = pr_p.add_run(f" ({', '.join(proj['technologies'])})")
                tech_run.italic = True
                tech_run.font.size = Pt(9)
                tech_run.font.name = docx_font
                tech_run.font.color.rgb = subtle_text
                
            if proj.get("link"):
                link_run = pr_p.add_run(f" [{proj['link']}]")
                link_run.font.size = Pt(9)
                link_run.font.name = docx_font
                link_run.font.color.rgb = primary_color

            if proj.get("description"):
                desc_p = doc.add_paragraph(style='List Bullet')
                desc_p.paragraph_format.space_before = Pt(0)
                desc_p.paragraph_format.space_after = Pt(2)
                desc_run = desc_p.add_run(proj["description"])
                desc_run.font.size = Pt(9.5)
                desc_run.font.name = docx_font
                desc_run.font.color.rgb = dark_text

    # Certifications
    if res.get("certifications"):
        add_section_heading("Certifications")
        for cert in res["certifications"]:
            cert_p = doc.add_paragraph(style='List Bullet')
            cert_p.paragraph_format.space_before = Pt(1)
            cert_p.paragraph_format.space_after = Pt(2)
            c_name = cert_p.add_run(cert.get("name", ""))
            c_name.bold = True
            c_name.font.size = Pt(9.5)
            c_name.font.name = docx_font
            
            c_iss = cert_p.add_run(f" – {cert.get('issuer', '')}")
            c_iss.font.size = Pt(9.5)
            c_iss.font.name = docx_font
            
            if cert.get("date"):
                c_dt = cert_p.add_run(f" ({cert['date']})")
                c_dt.italic = True
                c_dt.font.size = Pt(9)
                c_dt.font.name = docx_font
                c_dt.font.color.rgb = subtle_text

    # Custom sections
    if res.get("custom_sections"):
        for sec in res["custom_sections"]:
            add_section_heading(sec.get("heading", "Additional Information"))
            for item in sec.get("items", []):
                item_p = doc.add_paragraph(style='List Bullet')
                item_p.paragraph_format.space_before = Pt(1)
                item_p.paragraph_format.space_after = Pt(2)
                i_run = item_p.add_run(item)
                i_run.font.size = Pt(9.5)
                i_run.font.name = docx_font
                i_run.font.color.rgb = dark_text

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()

# ---------- COVER LETTER EXPORT (PDF & DOCX) ----------

def generate_cover_letter_docx(
    candidate_name: str,
    candidate_info: Dict[str, Any],
    company: str,
    job_title: str,
    letter_text: str,
    accent_color_hex: str = "#2563eb",
    font_name: str = "inter"
) -> bytes:
    doc = docx.Document()
    docx_font = DOCX_FONTS.get(font_name, "Calibri")
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    primary_color = hex_to_rgb(accent_color_hex)
    dark_text = RGBColor(30, 41, 59)
    subtle_text = RGBColor(100, 116, 139)

    # Header
    name_p = doc.add_paragraph()
    name_run = name_p.add_run(candidate_name)
    name_run.bold = True
    name_run.font.size = Pt(18)
    name_run.font.name = docx_font
    name_run.font.color.rgb = primary_color

    contacts = []
    if candidate_info.get("email"): contacts.append(candidate_info["email"])
    if candidate_info.get("phone"): contacts.append(candidate_info["phone"])
    if candidate_info.get("location"): contacts.append(candidate_info["location"])
    if candidate_info.get("linkedin_url"): contacts.append(candidate_info["linkedin_url"])

    if contacts:
        c_p = doc.add_paragraph()
        c_p.paragraph_format.space_after = Pt(16)
        c_run = c_p.add_run("  •  ".join(contacts))
        c_run.font.size = Pt(9.5)
        c_run.font.name = docx_font
        c_run.font.color.rgb = subtle_text

    # Body paragraphs
    paragraphs = letter_text.split("\n\n")
    for para in paragraphs:
        cleaned = para.strip()
        if not cleaned:
            continue
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(10)
        p.paragraph_format.line_spacing = 1.15
        run = p.add_run(cleaned)
        run.font.size = Pt(10.5)
        run.font.name = docx_font
        run.font.color.rgb = dark_text

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()

COVER_LETTER_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {
    size: A4;
    margin: 20mm 22mm 20mm 22mm;
  }
  body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    color: #1e293b;
    line-height: 1.6;
    font-size: 10.5pt;
    background-color: #ffffff;
  }
  .header {
    border-bottom: 2px solid {{ accent_color }};
    padding-bottom: 12px;
    margin-bottom: 24px;
  }
  .candidate-name {
    font-size: 20pt;
    font-weight: 700;
    color: {{ accent_color }};
  }
  .candidate-title {
    font-size: 11pt;
    font-weight: 600;
    color: #64748b;
    margin-top: 2px;
  }
  .contacts {
    font-size: 9pt;
    color: #64748b;
    margin-top: 6px;
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }
  .letter-content {
    font-size: 10.5pt;
    color: #334155;
    text-align: justify;
  }
  .letter-content p {
    margin-bottom: 14px;
  }
</style>
</head>
<body>
  <div class="header">
    <div class="candidate-name">{{ name }}</div>
    {% if title %}<div class="candidate-title">{{ title }}</div>{% endif %}
    <div class="contacts">
      {% if email %}<span>Email: {{ email }}</span>{% endif %}
      {% if phone %}<span>Tel: {{ phone }}</span>{% endif %}
      {% if location %}<span>Loc: {{ location }}</span>{% endif %}
      {% if linkedin %}<span>LinkedIn: {{ linkedin }}</span>{% endif %}
    </div>
  </div>

  <div class="letter-content">
    {% for paragraph in paragraphs %}
      {% if paragraph.strip() %}
        <p>{{ paragraph.strip() }}</p>
      {% endif %}
    {% endfor %}
  </div>
</body>
</html>
"""

def generate_cover_letter_pdf(
    candidate_name: str,
    candidate_info: Dict[str, Any],
    letter_text: str,
    accent_color_hex: str = "#2563eb"
) -> bytes:
    paragraphs = letter_text.split("\n\n")
    tmpl = Template(COVER_LETTER_HTML_TEMPLATE)
    html_content = tmpl.render(
        name=candidate_name,
        title=candidate_info.get("professional_title", ""),
        email=candidate_info.get("email", ""),
        phone=candidate_info.get("phone", ""),
        location=candidate_info.get("location", ""),
        linkedin=candidate_info.get("linkedin_url", ""),
        accent_color=accent_color_hex,
        paragraphs=paragraphs
    )
    return HTML(string=html_content).write_pdf()
