import io
import re
from collections import OrderedDict

import pdfplumber

class ResumeParser:
    SECTION_HEADERS = {
        "summary": ["summary", "professional summary", "profile", "about"],
        "experience": ["experience", "work experience", "professional experience", "employment history"],
        "projects": ["projects", "personal projects", "selected projects"],
        "education": ["education", "academic background"],
        "skills": ["skills", "technical skills", "core competencies", "technologies"],
        "certifications": ["certifications", "certificates", "licenses"],
        "achievements": ["achievements", "awards", "accomplishments"]
    }

    SKILL_ALIASES = OrderedDict([
        ("python", ["python"]),
        ("java", ["java"]),
        ("javascript", ["javascript", "js"]),
        ("typescript", ["typescript", "ts"]),
        ("c++", ["c++"]),
        ("go", ["go", "golang"]),
        ("rust", ["rust"]),
        ("react", ["react", "reactjs", "react.js"]),
        ("next.js", ["next.js", "nextjs"]),
        ("node.js", ["node", "node.js"]),
        ("fastapi", ["fastapi"]),
        ("django", ["django"]),
        ("flask", ["flask"]),
        ("spring boot", ["spring boot", "springboot"]),
        ("sql", ["sql"]),
        ("postgresql", ["postgresql", "postgres"]),
        ("mysql", ["mysql"]),
        ("mongodb", ["mongodb", "mongo"]),
        ("redis", ["redis"]),
        ("docker", ["docker"]),
        ("kubernetes", ["kubernetes", "k8s"]),
        ("aws", ["aws", "amazon web services"]),
        ("gcp", ["gcp", "google cloud"]),
        ("azure", ["azure", "microsoft azure"]),
        ("terraform", ["terraform"]),
        ("ci/cd", ["ci/cd", "cicd", "github actions", "jenkins", "gitlab ci"]),
        ("machine learning", ["machine learning", "ml"]),
        ("nlp", ["nlp", "natural language processing"]),
        ("llm", ["llm", "large language model", "gpt", "rag"]),
        ("tensorflow", ["tensorflow"]),
        ("pytorch", ["pytorch"]),
        ("pandas", ["pandas"]),
        ("numpy", ["numpy"]),
        ("airflow", ["airflow"]),
        ("spark", ["spark", "pyspark"]),
        ("kafka", ["kafka"]),
        ("microservices", ["microservices", "microservice"]),
        ("system design", ["system design", "distributed systems"]),
        ("testing", ["pytest", "junit", "testing", "unit testing", "integration testing"])
    ])

    def extract_text(self, file_path):
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
        return text

    def extract_text_from_bytes(self, file_bytes, filename=""):
        if filename.lower().endswith(".pdf"):
            text = ""
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n"
            return text

        return file_bytes.decode("utf-8", errors="ignore")

    def _normalize_line(self, line):
        return re.sub(r"\s+", " ", line).strip()

    def _clean_lines(self, text):
        return [self._normalize_line(line) for line in text.split("\n") if self._normalize_line(line)]

    def _header_to_section(self, line):
        lowered = re.sub(r"[^a-z\s]", "", line.lower()).strip()
        lowered = re.sub(r"\s+", " ", lowered)
        for section, candidates in self.SECTION_HEADERS.items():
            if lowered in candidates:
                return section
        return None

    def _sectionize(self, text):
        lines = self._clean_lines(text)
        sections = {
            "general": []
        }
        active = "general"

        for line in lines:
            section = self._header_to_section(line)
            if section:
                active = section
                sections.setdefault(section, [])
                continue
            sections.setdefault(active, []).append(line)

        return sections

    def _dedupe_keep_order(self, items, limit=None):
        seen = set()
        ordered = []
        for item in items:
            key = item.lower().strip()
            if key and key not in seen:
                seen.add(key)
                ordered.append(item)
        if limit is None:
            return ordered
        return ordered[:limit]

    def _strip_bullet_prefix(self, line):
        return re.sub(r"^\s*[-•*]\s*", "", line).strip()

    def _is_bullet_line(self, line):
        return bool(re.match(r"^\s*[-•*]\s+", line))

    def _has_date_range(self, line):
        return bool(re.search(r"\b(?:19|20)\d{2}\b\s*(?:-|–|to)\s*(?:\b(?:19|20)\d{2}\b|present|current|now)", line, re.IGNORECASE))

    def _looks_like_experience_header(self, line):
        role_pattern = r"engineer|developer|manager|scientist|intern|analyst|consultant|architect|lead|director|specialist"
        if self._has_date_range(line):
            return True
        has_role = re.search(role_pattern, line, re.IGNORECASE)
        has_company_joiner = re.search(r"\bat\b|\||-|–|,", line, re.IGNORECASE)
        return bool(has_role and has_company_joiner and len(line.split()) <= 20)

    def _looks_like_project_title(self, line):
        if self._has_date_range(line):
            return False
        if len(line.split()) > 14:
            return False

        marker = r"project|platform|system|app|tool|engine|dashboard|pipeline|portal|assistant|capstone"
        if re.search(marker, line, re.IGNORECASE):
            return True

        # Title-like short line (e.g., "Realtime Analytics Platform")
        return len(line.split()) >= 2 and line[:1].isupper()

    def extract_skills(self, text, sections):
        skill_source = "\n".join(sections.get("skills", [])) + "\n" + text
        lower_text = skill_source.lower()
        found = []

        for canonical, aliases in self.SKILL_ALIASES.items():
            for alias in aliases:
                pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
                if re.search(pattern, lower_text, re.IGNORECASE):
                    found.append(canonical)
                    break

        return self._dedupe_keep_order(found, limit=18)

    def extract_projects(self, sections, all_lines):
        section_lines = list(sections.get("projects", []))
        entries = []

        if section_lines:
            current_title = None
            for raw in section_lines:
                cleaned = self._strip_bullet_prefix(raw)
                if not cleaned:
                    continue

                if not self._is_bullet_line(raw) and self._looks_like_project_title(cleaned):
                    current_title = cleaned
                    entries.append(cleaned)
                    continue

                if self._is_bullet_line(raw):
                    if current_title:
                        entries.append(f"{current_title} — {cleaned}")
                    elif re.search(r"built|developed|designed|implemented|launched|created", cleaned, re.IGNORECASE):
                        entries.append(cleaned)

            if entries:
                return self._dedupe_keep_order(entries, limit=8)

        fallback_lines = [
            line for line in all_lines
            if re.search(r"project|capstone|case study|portfolio", line, re.IGNORECASE)
            and len(line.split()) >= 2
            and len(line.split()) <= 20
        ]
        return self._dedupe_keep_order(fallback_lines, limit=6)

    def extract_experience(self, sections, all_lines):
        section_lines = list(sections.get("experience", []))
        entries = []

        if section_lines:
            for raw in section_lines:
                cleaned = self._strip_bullet_prefix(raw)
                if not cleaned:
                    continue
                if self._is_bullet_line(raw):
                    continue
                if self._looks_like_experience_header(cleaned):
                    entries.append(cleaned)

            if entries:
                return self._dedupe_keep_order(entries, limit=8)

        fallback_lines = []
        for line in all_lines:
            cleaned = self._strip_bullet_prefix(line)
            if not cleaned:
                continue
            if self._looks_like_experience_header(cleaned):
                fallback_lines.append(cleaned)

        return self._dedupe_keep_order(fallback_lines, limit=8)

    def extract_achievements(self, sections, all_lines):
        source_lines = sections.get("achievements", []) + sections.get("experience", []) + sections.get("projects", [])
        if not source_lines:
            source_lines = all_lines

        achievements = []
        metric_pattern = r"\b\d+(?:\.\d+)?%\b|\$\s?\d+[\d,]*|\b\d+x\b|\b\d+\s?(?:million|billion|k|m|ms|sec|seconds|mins?|hours?|users?|customers?|requests?)\b"
        action_pattern = r"improved|reduced|increased|optimized|launched|shipped|delivered|built|designed|led|scaled|migrated|automated"

        for line in source_lines:
            has_metric = re.search(metric_pattern, line, re.IGNORECASE)
            has_action = re.search(action_pattern, line, re.IGNORECASE)
            if has_metric and has_action and len(line.split()) >= 6:
                achievements.append(line)

        return self._dedupe_keep_order(achievements, limit=8)

    def extract_education(self, sections, all_lines):
        source = sections.get("education", []) if sections.get("education") else all_lines
        edu = []
        edu_pattern = r"b\.?(s|a|tech)|m\.?(s|a|tech|ba)|ph\.?d|bachelor|master|university|college|institute|gpa"
        for line in source:
            if re.search(edu_pattern, line, re.IGNORECASE):
                edu.append(line)
        return self._dedupe_keep_order(edu, limit=5)

    def extract_keywords(self, text):
        keyword_bank = [
            "scalability", "performance", "distributed", "microservices", "api",
            "data pipeline", "analytics", "experimentation", "leadership", "mentoring",
            "testing", "ci/cd", "observability", "security", "product", "reliability",
            "incident response", "cost optimization"
        ]
        text_lower = text.lower()
        return [k for k in keyword_bank if k in text_lower][:10]

    def extract_contact(self, text):
        email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        phone_match = re.search(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s-]?)\d{3}[\s-]?\d{4}", text)
        linkedin_match = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9\-_/]+", text, re.IGNORECASE)
        github_match = re.search(r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9\-_/]+", text, re.IGNORECASE)

        return {
            "email": email_match.group(0) if email_match else None,
            "phone": phone_match.group(0) if phone_match else None,
            "linkedin": linkedin_match.group(0) if linkedin_match else None,
            "github": github_match.group(0) if github_match else None
        }

    def estimate_years_experience(self, text):
        ranges = re.findall(r"\b((?:19|20)\d{2})\b\s*(?:-|–|to)\s*(\b(?:19|20)\d{2}\b|present|current|now)", text, re.IGNORECASE)
        if not ranges:
            return None

        years = []
        for start, end in ranges:
            start_year = int(start)
            if re.search(r"present|current|now", end, re.IGNORECASE):
                end_year = 2026
            else:
                end_year = int(end)
            if end_year >= start_year:
                years.append((start_year, end_year))

        if not years:
            return None

        earliest = min(year[0] for year in years)
        latest = max(year[1] for year in years)
        return max(0, latest - earliest)

    def summarize(self, text, skills, projects, achievements, experience, keywords, education, years_experience):
        bullets = []
        cleaned = re.sub(r"\s+", " ", text).strip()

        if cleaned:
            bullets.append(f"- Snapshot: {cleaned[:180]}")
        if skills:
            bullets.append(f"- Skills: {', '.join(skills[:8])}")
        if years_experience is not None:
            bullets.append(f"- Estimated experience span: {years_experience}+ years")
        if experience:
            bullets.append(f"- Experience highlights: {' | '.join(experience[:2])}")
        if projects:
            bullets.append(f"- Projects: {' | '.join(projects[:3])}")
        if achievements:
            bullets.append(f"- Quantified wins: {' | '.join(achievements[:2])}")
        if education:
            bullets.append(f"- Education: {' | '.join(education[:2])}")
        if keywords:
            bullets.append(f"- Focus areas: {', '.join(keywords[:5])}")
        if re.search(r"led|managed|mentored|owned", text, re.IGNORECASE):
            bullets.append("- Leadership signals present in the resume.")
        if re.search(r"improved|reduced|increased|launched|built", text, re.IGNORECASE):
            bullets.append("- Impact-oriented achievements detected.")

        return "\n".join(bullets[:8])

    def parse_text(self, text):
        cleaned_text = text.strip()
        all_lines = self._clean_lines(cleaned_text)
        sections = self._sectionize(cleaned_text)

        skills = self.extract_skills(cleaned_text, sections)
        projects = self.extract_projects(sections, all_lines)
        experience = self.extract_experience(sections, all_lines)
        achievements = self.extract_achievements(sections, all_lines)
        education = self.extract_education(sections, all_lines)
        keywords = self.extract_keywords(cleaned_text)
        contact = self.extract_contact(cleaned_text)
        years_experience = self.estimate_years_experience(cleaned_text)

        return {
            "skills": skills,
            "projects": projects,
            "experience": experience,
            "achievements": achievements,
            "education": education,
            "keywords": keywords,
            "contact": contact,
            "years_experience": years_experience,
            "sections_detected": [name for name in sections.keys() if name != "general"],
            "raw_text": cleaned_text[:2000],
            "summary": self.summarize(
                cleaned_text,
                skills,
                projects,
                achievements,
                experience,
                keywords,
                education,
                years_experience
            )
        }

    def parse_upload(self, file_bytes, filename=""):
        text = self.extract_text_from_bytes(file_bytes, filename)
        return self.parse_text(text)

    def parse(self, file_path):
        text = self.extract_text(file_path)
        return self.parse_text(text)