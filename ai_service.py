import json
import os
import re
import time
import threading
import logging
from datetime import datetime, date
from typing import Dict, Any, Tuple, Optional, List
from google import genai
from google.genai import types
from groq import Groq

logger = logging.getLogger(__name__)

# Model configurations
# Models marked with requires_user_key=True are only accessible when the user provides their own API key.
AVAILABLE_MODELS = {
    "gemini": [
        {"id": "gemini-3.6-flash", "name": "Gemini 3.6 Flash (Fast & Smart)", "requires_user_key": False},
        {"id": "gemini-3.7-flash", "name": "Gemini 3.7 Flash (Next-Gen Reasoning)", "requires_user_key": False},
        {"id": "gemini-3.5-flash", "name": "Gemini 3.5 Flash", "requires_user_key": False}
    ],
    "groq": [
        {"id": "openai/gpt-oss-20b", "name": "GPT OSS 20B (Default Free Key)", "requires_user_key": False},
        # User-Key Required Models (BYOK)
        {"id": "qwen/qwen3.6-27b", "name": "Qwen 3.6 27B (Key Required)", "requires_user_key": True},
        {"id": "qwen/qwen3.8-27b", "name": "Qwen 3.8 27B (Key Required)", "requires_user_key": True},
        {"id": "canopylabs/orpheus-arabic-saudi", "name": "CanopyLabs Orpheus Arabic Saudi (Key Required)", "requires_user_key": True},
        {"id": "canopylabs/orpheus-v1-english", "name": "CanopyLabs Orpheus v1 English (Key Required)", "requires_user_key": True},
        {"id": "groq/compound", "name": "Groq Compound (Key Required)", "requires_user_key": True},
        {"id": "groq/compound-mini", "name": "Groq Compound Mini (Key Required)", "requires_user_key": True},
        {"id": "meta-llama/llama-prompt-guard-2-22m", "name": "Llama Prompt Guard 2 22M (Key Required)", "requires_user_key": True},
        {"id": "meta-llama/llama-prompt-guard-2-86m", "name": "Llama Prompt Guard 2 86M (Key Required)", "requires_user_key": True},
        {"id": "openai/gpt-oss-120b", "name": "GPT OSS 120B (Key Required)", "requires_user_key": True},
        {"id": "openai/gpt-oss-safeguard-20b", "name": "GPT OSS Safeguard 20B (Key Required)", "requires_user_key": True},
        {"id": "whisper-large-v3", "name": "Whisper Large v3 (Key Required)", "requires_user_key": True},
        {"id": "whisper-large-v3-turbo", "name": "Whisper Large v3 Turbo (Key Required)", "requires_user_key": True}
    ]
}

USER_KEY_REQUIRED_MODEL_IDS = {
    m["id"] for provider_models in AVAILABLE_MODELS.values() for m in provider_models if m.get("requires_user_key")
}

def is_model_user_key_required(model_id: str) -> bool:
    return model_id in USER_KEY_REQUIRED_MODEL_IDS


# ---------- THREAD-SAFE CONCURRENCY QUEUE & RATE LIMITER ----------

class GroqRateLimitedQueue:
    """
    Thread-safe FIFO Queue & Concurrency Controller for Groq operations.
    Ensures strictly one single generation executes at a time (Concurrency Limit = 1)
    to respect Groq API limitations, tracks queue placement/tickets, with pacing
    and exponential backoff retry on 429.
    """
    def __init__(self, min_interval_seconds: float = 1.0, max_retries: int = 3):
        self._execution_lock = threading.Lock()
        self._counter_lock = threading.Lock()
        self._min_interval = min_interval_seconds
        self._max_retries = max_retries
        self._last_call_time = 0.0
        self._waiting_tickets: List[str] = []
        self._current_ticket: Optional[str] = None
        self.total_processed = 0

    def register_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """Pre-registers a ticket into the queue for live UI polling."""
        if not ticket_id:
            return self.get_status()
        with self._counter_lock:
            if ticket_id not in self._waiting_tickets and self._current_ticket != ticket_id:
                self._waiting_tickets.append(ticket_id)
        return self.get_ticket_status(ticket_id)

    def execute(self, func, *args, ticket_id: Optional[str] = None, **kwargs):
        if ticket_id:
            with self._counter_lock:
                if ticket_id not in self._waiting_tickets and self._current_ticket != ticket_id:
                    self._waiting_tickets.append(ticket_id)

        try:
            with self._execution_lock:
                with self._counter_lock:
                    if ticket_id and ticket_id in self._waiting_tickets:
                        self._waiting_tickets.remove(ticket_id)
                    self._current_ticket = ticket_id

                # Enforce pacing between consecutive executions
                now = time.time()
                elapsed = now - self._last_call_time
                if elapsed < self._min_interval:
                    time.sleep(self._min_interval - elapsed)

                retries = 0
                while True:
                    try:
                        result = func(*args, **kwargs)
                        self._last_call_time = time.time()
                        with self._counter_lock:
                            self.total_processed += 1
                        return result
                    except Exception as exc:
                        error_str = str(exc).lower()
                        is_rate_limit = "429" in error_str or "rate limit" in error_str or "too many requests" in error_str
                        if is_rate_limit and retries < self._max_retries:
                            retries += 1
                            backoff = (2 ** retries) + 1.0
                            logger.warning(f"[Groq Queue] Rate limit encountered. Retrying {retries}/{self._max_retries} in {backoff:.1f}s...")
                            time.sleep(backoff)
                        else:
                            raise
        finally:
            with self._counter_lock:
                if ticket_id and self._current_ticket == ticket_id:
                    self._current_ticket = None
                elif not ticket_id and self._current_ticket is None:
                    pass
                if ticket_id and ticket_id in self._waiting_tickets:
                    self._waiting_tickets.remove(ticket_id)

    def get_ticket_status(self, ticket_id: str) -> Dict[str, Any]:
        """Calculates exact live queue position and estimated wait time for a ticket."""
        with self._counter_lock:
            active = 1 if self._current_ticket else 0
            waiting = len(self._waiting_tickets)
            
            if self._current_ticket and self._current_ticket == ticket_id:
                return {
                    "ticket_id": ticket_id,
                    "status": "processing",
                    "position": 0,
                    "active_count": active,
                    "waiting_count": waiting,
                    "estimated_wait_seconds": 0,
                    "message": "Generating your resume right now..."
                }
            elif ticket_id in self._waiting_tickets:
                pos = self._waiting_tickets.index(ticket_id) + 1
                est_wait = (pos * 10) + (6 if self._current_ticket else 0)
                msg = f"Position #{pos} in queue ({pos - 1} ahead of you)" if pos > 1 else "Position #1 in queue (You are next in line!)"
                return {
                    "ticket_id": ticket_id,
                    "status": "queued",
                    "position": pos,
                    "active_count": active,
                    "waiting_count": waiting,
                    "estimated_wait_seconds": est_wait,
                    "message": msg
                }
            else:
                return {
                    "ticket_id": ticket_id,
                    "status": "processing" if self._current_ticket else "idle_or_done",
                    "position": 0,
                    "active_count": active,
                    "waiting_count": waiting,
                    "estimated_wait_seconds": 0,
                    "message": "Ready"
                }

    def get_status(self) -> Dict[str, Any]:
        with self._counter_lock:
            return {
                "active_count": 1 if self._current_ticket else 0,
                "waiting_count": len(self._waiting_tickets),
                "total_processed": self.total_processed,
                "concurrency_limit": 1,
                "min_interval_seconds": self._min_interval
            }

groq_queue = GroqRateLimitedQueue(min_interval_seconds=1.0, max_retries=3)

def get_groq_queue_status() -> Dict[str, Any]:
    return groq_queue.get_status()

def register_queue_ticket(ticket_id: str) -> Dict[str, Any]:
    return groq_queue.register_ticket(ticket_id)

def get_ticket_queue_status(ticket_id: str) -> Dict[str, Any]:
    return groq_queue.get_ticket_status(ticket_id)

SYSTEM_PROMPT = """
You are an elite, executive-level Resume Architect and ATS (Applicant Tracking System) Optimization Specialist.
Your task is to take a User's Master Profile and a target Job Description (JD), then engineer a complete, tailored, highly impactful resume that maximizes ATS compatibility, highlights relevant keywords, quantifies achievements (using the Google X-Y-Z formula: Accomplished [X] as measured by [Y], by doing [Z]), and structures the resume cleanly.

CRITICAL INSTRUCTIONS:
1. You MUST ALWAYS include and fully populate ALL sections in the "resume" object: "personal_info", "summary", "core_competencies", "experience", "education", "projects", "certifications", and "custom_sections".
2. NEVER leave "summary", "core_competencies", "experience", "education", or "projects" empty or omitted. Adapt the candidate's master profile experiences and projects to highlight relevant JD skills.
3. You MUST output ONLY a valid JSON object matching the exact schema specified. Do not include markdown code block backticks around the json unless it is strictly valid JSON format.
"""

RESUME_SCHEMA_INSTRUCTION = """
The JSON response MUST adhere to this exact structure:
{
  "target_role": "Target Job Title",
  "target_company": "Target Company (if detected in JD, else empty)",
  "match_score": 88, // integer from 0 to 100 assessing alignment
  "match_analysis": {
    "strengths": ["List of key matched strengths"],
    "keyword_matches": ["Key tech/hard skills matched directly to JD"],
    "missing_or_recommended_skills": ["Skills mentioned in JD that could be strengthened"],
    "ats_tips": ["Actionable tips for this specific application"]
  },
  "resume": {
    "personal_info": {
      "full_name": "Full Name",
      "professional_title": "Tailored Professional Title matching JD",
      "email": "email@example.com",
      "phone": "+1 ...",
      "location": "City, State/Country",
      "linkedin_url": "linkedin.com/in/...",
      "github_url": "github.com/...",
      "portfolio_url": "portfolio link"
    },
    "summary": "A 3-4 sentence high-impact executive summary directly tailored to the JD requirements.",
    "core_competencies": [
      "Categorized skills matching JD keywords, e.g. Python, MariaDB, Docker, System Architecture, etc."
    ],
    "experience": [
      {
        "title": "Role Title",
        "company": "Company Name",
        "location": "Location / Remote",
        "start_date": "MM/YYYY",
        "end_date": "MM/YYYY or Present",
        "highlights": [
          "Accomplished [X] measured by [Y] by doing [Z] tailored to JD keywords."
        ]
      }
    ],
    "education": [
      {
        "degree": "Degree and Major",
        "institution": "University / College",
        "location": "Location",
        "graduation_date": "YYYY",
        "details": "GPA, honors, relevant coursework if applicable"
      }
    ],
    "projects": [
      {
        "name": "Project Name",
        "technologies": ["Tech 1", "Tech 2"],
        "link": "URL if available",
        "description": "Tailored description emphasizing relevant impact and tools."
      }
    ],
    "certifications": [
      {
        "name": "Certification Name",
        "issuer": "Issuing Org",
        "date": "YYYY"
      }
    ],
    "custom_sections": [
      {
        "heading": "Awards & Publications",
        "items": ["Item description"]
      }
    ]
  }
}
"""

def extract_json(raw_text: str) -> Dict[str, Any]:
    raw_text = raw_text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    elif raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        # Try to find { ... } block
        match = re.search(r'(\{[\s\S]*\})', raw_text)
        if match:
            return json.loads(match.group(1))
        raise ValueError(f"Could not parse valid JSON from model output: {raw_text[:200]}...")

def get_effective_api_key(provider: str, user_api_key: Optional[str] = None, model_name: Optional[str] = None, is_admin: bool = False) -> str:
    from db import get_system_setting
    provider = (provider or "gemini").lower().strip()
    
    # If custom user key is explicitly provided, always use it
    if user_api_key and user_api_key.strip():
        return user_api_key.strip()

    # Check if model explicitly requires the user to enter their own API key (Admins bypass this and have universal key access)
    if model_name and is_model_user_key_required(model_name) and not is_admin:
        raise ValueError(f"The model '{model_name}' is a BYOK (Bring Your Own Key) model. Please enter your personal {provider.upper()} API key in Settings or on the generation page to use it.")

    if provider == "gemini":
        db_key = get_system_setting("universal_gemini_api_key", "")
        if db_key:
            return db_key
        env_key = os.environ.get("GEMINI_API_KEY", "")
        if env_key:
            return env_key
    elif provider == "groq":
        db_key = get_system_setting("universal_groq_api_key", "")
        if db_key:
            return db_key
        env_key = os.environ.get("GROQ_API_KEY", "")
        if env_key:
            return env_key
            
    raise ValueError(f"No universal API key configured for {provider.capitalize()}. Please configure it in the Admin Console or settings.")




def generate_resume_with_gemini(
    api_key: str,
    model_name: str,
    profile_data: Dict[str, Any],
    job_description: str,
    additional_notes: str = ""
) -> Tuple[Dict[str, Any], str]:
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
{SYSTEM_PROMPT}

{RESUME_SCHEMA_INSTRUCTION}

--- MASTER USER PROFILE DATA ---
{json.dumps(profile_data, indent=2, default=str)}

--- TARGET JOB DESCRIPTION ---
{job_description}

--- USER INSTRUCTIONS / TARGETING EMPHASIS ---
{additional_notes if additional_notes else "Tailor the resume to match the JD keywords and required qualifications perfectly."}

Generate the complete JSON response now:
"""
    if not model_name:
        model_name = "gemini-3.6-flash"

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        )
    )
    
    raw_text = response.text
    parsed_json = extract_json(raw_text)
    return parsed_json, raw_text

def _groq_resume_call(
    api_key: str,
    model_name: str,
    profile_data: Dict[str, Any],
    job_description: str,
    additional_notes: str = ""
) -> Tuple[Dict[str, Any], str]:
    client = Groq(api_key=api_key)
    
    prompt = f"""
{SYSTEM_PROMPT}

{RESUME_SCHEMA_INSTRUCTION}

--- MASTER USER PROFILE DATA ---
{json.dumps(profile_data, indent=2, default=str)}

--- TARGET JOB DESCRIPTION ---
{job_description}

--- USER INSTRUCTIONS / TARGETING EMPHASIS ---
{additional_notes if additional_notes else "Tailor the resume to match the JD keywords and required qualifications perfectly."}

Generate the complete JSON response now:
"""
    if not model_name:
        model_name = "openai/gpt-oss-20b"

    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are an ATS Resume Optimizer that returns only strict JSON."},
            {"role": "user", "content": prompt}
        ],
        model=model_name,
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    
    raw_text = chat_completion.choices[0].message.content
    parsed_json = extract_json(raw_text)
    return parsed_json, raw_text

def generate_resume_with_groq(
    api_key: str,
    model_name: str,
    profile_data: Dict[str, Any],
    job_description: str,
    additional_notes: str = "",
    ticket_id: Optional[str] = None
) -> Tuple[Dict[str, Any], str]:
    return groq_queue.execute(
        _groq_resume_call,
        api_key=api_key,
        model_name=model_name,
        profile_data=profile_data,
        job_description=job_description,
        additional_notes=additional_notes,
        ticket_id=ticket_id
    )

def generate_tailored_resume(
    provider: str,
    model_name: str,
    user_api_key: Optional[str],
    profile_data: Dict[str, Any],
    job_description: str,
    additional_notes: str = "",
    queue_ticket_id: Optional[str] = None,
    is_admin: bool = False
) -> Tuple[Dict[str, Any], str]:
    provider = provider.lower().strip()
    effective_api_key = get_effective_api_key(provider, user_api_key, model_name=model_name, is_admin=is_admin)

    if provider == "gemini":
        return generate_resume_with_gemini(effective_api_key, model_name, profile_data, job_description, additional_notes)
    elif provider == "groq":
        return generate_resume_with_groq(effective_api_key, model_name, profile_data, job_description, additional_notes, ticket_id=queue_ticket_id)
    else:
        raise ValueError(f"Unsupported AI provider: {provider}. Choose 'gemini' or 'groq'.")

# ---------- AI COVER LETTER GENERATOR ----------

COVER_LETTER_PROMPT = """
You are an expert executive recruiter and professional career copywriter.
Write a compelling, bespoke, high-converting Cover Letter tailored directly to the target role and company using the candidate's background and resume.

Tone guidelines:
- Modern, authentic, confident, professional, and free of generic corporate clichés.
- Structure:
  1. Professional Header & Greeting
  2. The Hook: Enthusiastic opening stating the exact position and why the candidate is drawn to this company/mission.
  3. The Core Value Proposition: 2 paragraphs detailing 2-3 specific, quantified achievements from their background that directly map to the JD's key requirements.
  4. Cultural Alignment & Impact: How they will contribute immediately to the team.
  5. Confident Call to Action & Sign-off.

Output ONLY the complete cover letter text in clean markdown format (do not wrap in markdown code blocks).
"""

def generate_cover_letter(
    provider: str,
    model_name: str,
    user_api_key: Optional[str],
    resume_data: Dict[str, Any],
    job_description: str,
    company: str = "",
    role: str = "",
    tone: str = "Professional & Persuasive",
    is_admin: bool = False
) -> str:
    provider = (provider or "gemini").lower().strip()
    api_key = get_effective_api_key(provider, user_api_key, model_name=model_name, is_admin=is_admin)

    prompt = f"""
{COVER_LETTER_PROMPT}

Target Company: {company or 'Hiring Organization'}
Target Role: {role or 'Target Position'}
Desired Tone: {tone}

--- CANDIDATE RESUME & PROFILE DATA ---
{json.dumps(resume_data, indent=2, default=str)}

--- JOB DESCRIPTION ---
{job_description}

Write the complete tailored cover letter now:
"""

    if provider == "gemini":
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name or "gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3)
        )
        return response.text.strip()
    elif provider == "groq":
        def _call_groq_cover():
            client = Groq(api_key=api_key)
            chat = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a professional cover letter writer."},
                    {"role": "user", "content": prompt}
                ],
                model=model_name or "openai/gpt-oss-20b",
                temperature=0.3
            )
            return chat.choices[0].message.content.strip()
        return groq_queue.execute(_call_groq_cover)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

# ---------- AI INTERVIEW PREP & MOCK QUESTIONS ----------

INTERVIEW_PREP_SCHEMA = """
Return ONLY a valid JSON object with the following structure:
{
  "summary_pitch": "A 60-second 'Tell me about yourself' elevator pitch connecting background to this specific role.",
  "top_talking_points": [
    "Key talking point 1 with quantifiable impact",
    "Key talking point 2 highlighting exact tech match",
    "Key talking point 3 emphasizing leadership/collaboration"
  ],
  "technical_questions": [
    {
      "question": "Realistic technical or architectural question based on JD",
      "why_asked": "What the interviewer is probing for",
      "key_points_to_cover": ["Point A", "Point B", "Point C"],
      "sample_star_answer": "Situation: ... Task: ... Action: ... Result: ..."
    }
  ],
  "behavioral_questions": [
    {
      "question": "Behavioral question (e.g., handling conflicts, tight deadlines)",
      "competency": "Leadership / Problem Solving / Adaptability",
      "star_framework": {
        "situation": "Context from candidate's past projects",
        "task": "Specific challenge",
        "action": "Concrete actions taken",
        "result": "Measurable outcome"
      }
    }
  ],
  "role_specific_scenarios": [
    {
      "scenario": "Real-world job scenario the candidate will likely face in this role",
      "ideal_approach": "Strategic step-by-step approach to solve it"
    }
  ],
  "smart_questions_to_ask_interviewer": [
    "Thoughtful question 1 showing deep industry/tech curiosity",
    "Thoughtful question 2 about team goals and architecture",
    "Thoughtful question 3 about metrics of success in the first 90 days"
  ]
}
"""

def generate_interview_prep(
    provider: str,
    model_name: str,
    user_api_key: Optional[str],
    resume_data: Dict[str, Any],
    job_description: str,
    is_admin: bool = False
) -> Dict[str, Any]:
    provider = (provider or "gemini").lower().strip()
    api_key = get_effective_api_key(provider, user_api_key, model_name=model_name, is_admin=is_admin)

    prompt = f"""
You are a Principal Engineering Director and Executive Hiring Manager at a top tech company.
Generate an exhaustive, high-value Interview Preparation Kit tailored specifically to this candidate's resume and target Job Description.

{INTERVIEW_PREP_SCHEMA}

--- CANDIDATE RESUME DATA ---
{json.dumps(resume_data, indent=2, default=str)}

--- TARGET JOB DESCRIPTION ---
{job_description}

Return strictly valid JSON:
"""

    if provider == "gemini":
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name or "gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )
        return extract_json(response.text)
    elif provider == "groq":
        def _call_groq_interview():
            client = Groq(api_key=api_key)
            chat = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You generate interview preparation kits formatted strictly as JSON."},
                    {"role": "user", "content": prompt}
                ],
                model=model_name or "openai/gpt-oss-20b",
                response_format={"type": "json_object"},
                temperature=0.2
            )
            return extract_json(chat.choices[0].message.content)
        return groq_queue.execute(_call_groq_interview)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

# ---------- RESUME PDF/DOCX/TEXT PARSER (IMPORTER) ----------

PROFILE_IMPORT_SCHEMA = """
Extract and structure all candidate details into this EXACT Master Profile JSON format:
{
  "full_name": "Full Name",
  "professional_title": "Primary Title / Domain",
  "email": "Email address",
  "phone": "Phone number",
  "location": "City, State/Country",
  "linkedin_url": "URL or empty",
  "github_url": "URL or empty",
  "portfolio_url": "URL or empty",
  "summary": "Professional summary or bio paragraph",
  "skills": ["Skill 1", "Skill 2", "Skill 3", "Skill 4", "Skill 5"],
  "experiences": [
    {
      "title": "Job Title",
      "company": "Company Name",
      "location": "City, State / Remote",
      "start_date": "MM/YYYY",
      "end_date": "MM/YYYY or Present",
      "highlights": [
        "Quantified accomplishment bullet point",
        "Key responsibility bullet point"
      ]
    }
  ],
  "educations": [
    {
      "degree": "Degree and Major",
      "institution": "University / College",
      "location": "Location",
      "graduation_date": "YYYY",
      "details": "Honors / GPA / Coursework"
    }
  ],
  "projects": [
    {
      "name": "Project Name",
      "technologies": ["Tech 1", "Tech 2"],
      "link": "URL",
      "description": "Project overview and outcomes"
    }
  ],
  "certifications": [
    {
      "name": "Certification Title",
      "issuer": "Issuing Entity",
      "date": "YYYY"
    }
  ],
  "custom_sections": [
    {
      "heading": "Awards / Publications / Languages",
      "items": ["Item description"]
    }
  ]
}
"""

def parse_uploaded_resume_text(
    provider: str,
    model_name: str,
    user_api_key: Optional[str],
    raw_resume_text: str,
    is_admin: bool = False
) -> Dict[str, Any]:
    provider = (provider or "gemini").lower().strip()
    api_key = get_effective_api_key(provider, user_api_key, model_name=model_name, is_admin=is_admin)

    prompt = f"""
You are an expert Resume Parser and Data Extraction AI.
Analyze the raw text extracted from a user's uploaded resume document and accurately convert it into our clean Master Profile JSON schema.
Clean up formatting, standardize dates (MM/YYYY or YYYY), preserve all achievements and bullet points, and normalize skills.

{PROFILE_IMPORT_SCHEMA}

--- RAW RESUME DOCUMENT TEXT ---
{raw_resume_text[:15000]}

Return strictly valid JSON:
"""

    if provider == "gemini":
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name or "gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        return extract_json(response.text)
    elif provider == "groq":
        def _call_groq_parse():
            client = Groq(api_key=api_key)
            chat = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a resume parser that outputs structured JSON only."},
                    {"role": "user", "content": prompt}
                ],
                model=model_name or "openai/gpt-oss-20b",
                response_format={"type": "json_object"},
                temperature=0.1
            )
            return extract_json(chat.choices[0].message.content)
        return groq_queue.execute(_call_groq_parse)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

# ---------- BULLET POINT AI RE-WRITER ----------

def rewrite_bullet_point(
    provider: str,
    model_name: str,
    user_api_key: Optional[str],
    bullet_text: str,
    mode: str = "xyz",
    custom_instruction: str = "",
    is_admin: bool = False
) -> str:
    provider = (provider or "gemini").lower().strip()
    api_key = get_effective_api_key(provider, user_api_key, model_name=model_name, is_admin=is_admin)

    instructions = {
        "xyz": "Rewrite this bullet point following Google's X-Y-Z formula: 'Accomplished [X], as measured by [Y], by doing [Z]'. Keep it impactful and professional.",
        "quantify": "Rewrite this bullet point adding realistic placeholders or quantified metrics (%, $, time saved, users scaled, latency reduced) to highlight measurable business ROI.",
        "action": "Rewrite this bullet point starting with a high-impact active power verb (e.g., Engineered, Spearheaded, Orchestrated, Optimized, Architected) and eliminating passive voice.",
        "concise": "Condense this bullet point into a punchy, ultra-concise single-line statement without losing key technical achievements.",
        "leadership": "Rewrite this bullet point to emphasize leadership, team mentorship, cross-functional stakeholder management, and architectural ownership.",
        "custom": custom_instruction or "Enhance and polish this resume bullet point for maximum recruiter appeal."
    }

    selected_instruction = instructions.get(mode, instructions["xyz"])

    prompt = f"""
You are an expert resume editor.
{selected_instruction}

Original Bullet Point:
"{bullet_text}"

Return ONLY the rewritten bullet point text with no quotes, no markdown prefixes like '- ', and no conversational commentary.
"""

    if provider == "gemini":
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name or "gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3)
        )
        return response.text.strip().lstrip("-*• ").strip("\"'")
    elif provider == "groq":
        def _call_groq_bullet():
            client = Groq(api_key=api_key)
            chat = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a resume bullet point editor. Return only the single improved bullet point."},
                    {"role": "user", "content": prompt}
                ],
                model=model_name or "openai/gpt-oss-20b",
                temperature=0.3
            )
            return chat.choices[0].message.content.strip().lstrip("-*• ").strip("\"'")
        return groq_queue.execute(_call_groq_bullet)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

# ---------- DEEP ATS & READABILITY & SKILL GAP ANALYZER ----------

CLICHES_AND_WEAK_WORDS = [
    "hardworking", "team player", "detail-oriented", "go-getter", "dynamic", "synergy",
    "thought leader", "self-starter", "results-driven", "fast learner", "people person",
    "passionate", "think outside the box", "proven track record", "duties included",
    "responsible for", "helped with", "assisted in", "worked on"
]

def analyze_resume_deep(resume_data: Dict[str, Any], job_description: str = "") -> Dict[str, Any]:
    res = resume_data.get("resume", resume_data)
    bullets = []
    
    # Collect all bullets
    for exp in res.get("experience", []):
        for hl in exp.get("highlights", []):
            if isinstance(hl, str):
                bullets.append(hl)
                
    for proj in res.get("projects", []):
        desc = proj.get("description", "")
        if desc:
            bullets.append(desc)

    # Check clichés and weak phrases
    found_cliches = []
    total_words = 0
    passive_voice_candidates = []

    for b in bullets:
        b_lower = b.lower()
        words = b.split()
        total_words += len(words)
        
        for c in CLICHES_AND_WEAK_WORDS:
            if c in b_lower and c not in found_cliches:
                found_cliches.append(c)
                
        # Simple passive detection heuristic ("was created", "were implemented", "been done")
        if re.search(r'\b(was|were|is|are|been|being)\s+\w+ed\b', b_lower):
            if len(passive_voice_candidates) < 5:
                passive_voice_candidates.append(b)

    avg_bullet_words = round(total_words / max(len(bullets), 1), 1)

    # Categorize skills
    raw_skills = res.get("core_competencies", [])
    if isinstance(raw_skills, str):
        raw_skills = [s.strip() for s in raw_skills.split(",")]
    
    # Analyze match against JD if present
    jd_lower = job_description.lower() if job_description else ""
    matched_skills = []
    missing_jd_keywords = []

    if jd_lower:
        for skill in raw_skills:
            if skill.lower() in jd_lower:
                matched_skills.append(skill)

    # Readability score metric (0-100)
    readability_score = 95
    if avg_bullet_words > 30:
        readability_score -= 15
    elif avg_bullet_words < 8:
        readability_score -= 10
    readability_score -= min(len(found_cliches) * 5, 25)
    readability_score -= min(len(passive_voice_candidates) * 4, 20)
    readability_score = max(min(readability_score, 100), 40)

    return {
        "readability_score": readability_score,
        "total_bullets_analyzed": len(bullets),
        "avg_bullet_word_count": avg_bullet_words,
        "cliches_detected": found_cliches,
        "passive_voice_count": len(passive_voice_candidates),
        "passive_voice_examples": passive_voice_candidates[:3],
        "total_skills_count": len(raw_skills),
        "matched_skills_count": len(matched_skills)
    }

# ---------- MARKDOWN CONVERTER & AI CHAT ASSISTANT ----------

def json_to_markdown(resume_data: Dict[str, Any]) -> str:
    res = resume_data.get("resume", resume_data)
    info = res.get("personal_info", {})
    
    md_lines = []
    # Header
    name = info.get("full_name", "Resume")
    title = info.get("professional_title", "")
    md_lines.append(f"# {name}")
    if title:
        md_lines.append(f"### {title}")
    
    contact_parts = []
    if info.get("email"): contact_parts.append(info['email'])
    if info.get("phone"): contact_parts.append(info['phone'])
    if info.get("location"): contact_parts.append(info['location'])
    if info.get("linkedin_url"): contact_parts.append(f"[LinkedIn]({info['linkedin_url']})")
    if info.get("github_url"): contact_parts.append(f"[GitHub]({info['github_url']})")
    if info.get("portfolio_url"): contact_parts.append(f"[Portfolio]({info['portfolio_url']})")
    
    if contact_parts:
        md_lines.append(" | ".join(contact_parts))
    md_lines.append("\n---")
    
    # Summary
    if res.get("summary"):
        md_lines.append("\n## Executive Summary")
        md_lines.append(res["summary"])
        
    # Skills
    if res.get("core_competencies"):
        md_lines.append("\n## Core Competencies & Skills")
        skills = res["core_competencies"]
        if isinstance(skills, list):
            md_lines.append(" • ".join(str(s) for s in skills))
        else:
            md_lines.append(str(skills))
            
    # Experience
    if res.get("experience"):
        md_lines.append("\n## Professional Experience")
        for exp in res["experience"]:
            role_line = f"**{exp.get('title', '')}** | {exp.get('company', '')}"
            date_line = f"*{exp.get('start_date', '')} – {exp.get('end_date', '')}* | *{exp.get('location', '')}*"
            md_lines.append(f"\n{role_line}\n{date_line}")
            for hl in exp.get("highlights", []):
                md_lines.append(f"- {hl}")

    # Education
    if res.get("education"):
        md_lines.append("\n## Education")
        for edu in res["education"]:
            md_lines.append(f"\n**{edu.get('degree', '')}** — {edu.get('institution', '')} ({edu.get('graduation_date', '')})")
            if edu.get("details"):
                md_lines.append(f"- {edu['details']}")

    # Projects
    if res.get("projects"):
        md_lines.append("\n## Key Projects")
        for proj in res["projects"]:
            tech = f" *({', '.join(proj.get('technologies', []))})*" if proj.get('technologies') else ""
            link = f" [Link]({proj['link']})" if proj.get('link') else ""
            md_lines.append(f"\n**{proj.get('name', '')}**{tech}{link}")
            if proj.get("description"):
                md_lines.append(f"- {proj['description']}")

    # Certifications
    if res.get("certifications"):
        md_lines.append("\n## Certifications")
        for cert in res["certifications"]:
            date_str = f" ({cert.get('date')})" if cert.get('date') else ""
            md_lines.append(f"- **{cert.get('name')}** - {cert.get('issuer')}{date_str}")

    # Custom sections
    if res.get("custom_sections"):
        for sec in res["custom_sections"]:
            md_lines.append(f"\n## {sec.get('heading', 'Additional')}")
            for item in sec.get("items", []):
                md_lines.append(f"- {item}")

    return "\n".join(md_lines)

def ai_chat_assistant(
    provider: str,
    model_name: str,
    user_api_key: Optional[str],
    user_message: str,
    resume_context: Dict[str, Any],
    chat_history: list = None,
    is_admin: bool = False
) -> str:
    provider = provider.lower().strip()
    effective_api_key = get_effective_api_key(provider, user_api_key, model_name=model_name, is_admin=is_admin)

    system_instruction = f"""You are an elite AI Career Coach & Resume Specialist assisting the user with their resume.
Resume context currently open:
Title: {resume_context.get('title', 'Resume')}
Target Role: {resume_context.get('target_role', 'Not specified')}
Target Company: {resume_context.get('target_company', 'Not specified')}
ATS Match Score: {resume_context.get('match_score', 'N/A')}%
Resume Content JSON:
{json.dumps(resume_context.get('generated_json', {}), indent=2)[:3500]}

Your role:
- Answer questions directly, concisely, and helpfully.
- When asked to improve/rephrase bullets, apply the Google X-Y-Z formula ("Accomplished [X] measured by [Y], by doing [Z]").
- Give actionable ATS advice, interview prep pointers, or phrasing suggestions.
- Keep responses sharp, practical, and in clean markdown formatting without excessive pleasantries.
"""

    if provider == "gemini":
        client = genai.Client(api_key=effective_api_key)
        contents = [system_instruction]
        if chat_history:
            for msg in chat_history[-6:]:
                role = "user" if msg.get("role") == "user" else "model"
                contents.append(f"{role.upper()}: {msg.get('content')}")
        contents.append(f"USER: {user_message}")
        response = client.models.generate_content(
            model=model_name or "gemini-3.6-flash",
            contents="\n\n".join(contents),
            config=types.GenerateContentConfig(
                temperature=0.3,
            )
        )
        return response.text.strip()
    elif provider == "groq":
        def _call_groq_chat():
            client = Groq(api_key=effective_api_key)
            messages = [{"role": "system", "content": system_instruction}]
            if chat_history:
                for msg in chat_history[-6:]:
                    messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
            messages.append({"role": "user", "content": user_message})
            chat_completion = client.chat.completions.create(
                messages=messages,
                model=model_name or "openai/gpt-oss-20b",
                temperature=0.3,
            )
            return chat_completion.choices[0].message.content.strip()
        return groq_queue.execute(_call_groq_chat)
    else:
        raise ValueError(f"Unsupported AI provider: {provider}")

