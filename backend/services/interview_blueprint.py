ROLE_FOCUS = {
    "SWE": [
        "designing maintainable services",
        "debugging production incidents",
        "making pragmatic architecture tradeoffs"
    ],
    "Product Manager": [
        "prioritizing roadmap decisions",
        "aligning stakeholders around outcomes",
        "making product calls with incomplete data"
    ],
    "Data Scientist": [
        "validating model performance",
        "translating analysis into business decisions",
        "handling noisy or biased data"
    ],
    "ML Engineer": [
        "deploying models reliably",
        "monitoring model drift in production",
        "balancing experimentation with delivery speed"
    ],
    "Frontend Engineer": [
        "building accessible user interfaces",
        "improving client-side performance",
        "structuring reusable component systems"
    ],
    "Backend Engineer": [
        "designing APIs that scale",
        "maintaining data consistency under load",
        "improving observability and resilience"
    ],
    "DevOps": [
        "automating delivery pipelines",
        "improving reliability during incidents",
        "reducing operational toil through tooling"
    ],
    "Engineering Manager": [
        "growing engineers through feedback",
        "balancing execution with team health",
        "managing delivery risk across priorities"
    ],
    "Full-Stack Engineer": [
        "making frontend-backend integration tradeoffs",
        "shipping end-to-end features under constraints",
        "balancing UX quality with system reliability"
    ],
    "Platform Engineer": [
        "improving developer productivity with platform primitives",
        "designing reusable infrastructure capabilities",
        "reducing operational risk through tooling"
    ],
    "Security Engineer": [
        "identifying and mitigating critical threat vectors",
        "balancing security controls with developer velocity",
        "designing secure-by-default architectures"
    ]
}

QUESTION_TYPE_TEMPLATES = {
    "Behavioral": [
        "Tell me about a time you were {focus} in a real team setting.",
        "Describe a situation where you were responsible for {focus}. What happened?"
    ],
    "Technical": [
        "Walk me through how you would approach {focus} for this role.",
        "What technical tradeoffs do you consider when {focus}?"
    ],
    "System Design": [
        "Design a lightweight system for {focus}. What components matter most?",
        "If you had to scale a platform around {focus}, where would you start?"
    ],
    "LeetCode/DSA": [
        "What data structure choices help when {focus}?",
        "How would you reason about runtime and memory while {focus}?"
    ],
    "Culture Fit": [
        "How does your working style show up when {focus}?",
        "What team behaviors matter most to you while {focus}?"
    ],
    "Mixed": [
        "Give me both the technical and business angle on {focus}.",
        "What is the hardest part of {focus}, and how do you communicate it to others?"
    ],
    "Leadership & Management": [
        "Describe a leadership decision you made while {focus}. What tradeoff did you manage?",
        "How did you align stakeholders when {focus} under conflicting priorities?"
    ],
    "Product Sense": [
        "How would you frame user value and business impact while {focus}?",
        "What product tradeoff would you make first when {focus}, and why?"
    ],
    "Domain Knowledge": [
        "What domain-specific risks appear when {focus}, and how would you mitigate them?",
        "Which domain constraints most influence your decisions while {focus}?"
    ]
}

ROLE_ALIASES = {
    "swe": "SWE",
    "software engineer": "SWE",
    "frontend engineer": "Frontend Engineer",
    "backend engineer": "Backend Engineer",
    "full-stack engineer": "Full-Stack Engineer",
    "full stack engineer": "Full-Stack Engineer",
    "platform engineer": "Platform Engineer",
    "security engineer": "Security Engineer",
    "engineering manager": "Engineering Manager",
    "product manager": "Product Manager",
    "data scientist": "Data Scientist",
    "ml engineer": "ML Engineer",
    "devops": "DevOps",
    "devops / sre": "DevOps",
}

QUESTION_TYPE_ALIASES = {
    "behavioral": "Behavioral",
    "technical": "Technical",
    "system design": "System Design",
    "leetcode/dsa": "LeetCode/DSA",
    "culture fit": "Culture Fit",
    "mixed": "Mixed",
    "leadership & management": "Leadership & Management",
    "product sense": "Product Sense",
    "domain knowledge": "Domain Knowledge",
    "situational (star)": "Behavioral",
    "conflict resolution": "Behavioral",
    "case study": "Mixed",
    "open-ended / vision": "Mixed",
    "estimation / fermi": "Technical",
}

INTERVIEWER_PROFILES = {
    "Friendly HR": {
        "name": "Friendly HR",
        "role": "HR Partner",
        "style": "warm, structured, encouraging",
        "agent": "HR Interviewer",
        "lead": "Let's make this practical.",
        "followup": "Focus on situation, action, and result."
    },
    "Neutral Recruiter": {
        "name": "Neutral Recruiter",
        "role": "Recruiter",
        "style": "balanced, direct, concise",
        "agent": "HR Interviewer",
        "lead": "Keep it clear and relevant.",
        "followup": "Anchor your answer to scope and impact."
    },
    "Senior Engineer": {
        "name": "Senior Engineer",
        "role": "Senior Engineer",
        "style": "technical, precise, skeptical",
        "agent": "Technical Interviewer",
        "lead": "I care about how you think.",
        "followup": "Be explicit about the tradeoffs you made."
    },
    "Hiring Manager": {
        "name": "Hiring Manager",
        "role": "Hiring Manager",
        "style": "outcome-oriented, leadership-aware",
        "agent": "HR Interviewer",
        "lead": "Tie your answer to ownership and execution.",
        "followup": "Show me why your choice mattered to the business."
    },
    "Tough Critic": {
        "name": "Tough Critic",
        "role": "Adversarial Interviewer",
        "style": "challenging, skeptical, demanding",
        "agent": "Skeptic",
        "lead": "Assume I disagree until you prove otherwise.",
        "followup": "I want specifics, not broad claims."
    },
    "Silent Evaluator": {
        "name": "Silent Evaluator",
        "role": "Evaluator",
        "style": "minimal, cold, exacting",
        "agent": "Skeptic",
        "lead": "Answer directly.",
        "followup": "Cut the filler and get to the point."
    },
    "Devil's Advocate": {
        "name": "Devil's Advocate",
        "role": "Critical Reviewer",
        "style": "pushback-heavy, contrarian",
        "agent": "Skeptic",
        "lead": "I will push on your assumptions.",
        "followup": "Defend the downside and the alternative path."
    },
    "Timer Mode": {
        "name": "Timer Mode",
        "role": "Rapid Interviewer",
        "style": "fast, compressed, blunt",
        "agent": "Technical Interviewer",
        "lead": "Short answers only.",
        "followup": "One strong point is enough."
    },
    "Rapid Fire": {
        "name": "Rapid Fire",
        "role": "Quick-Fire Interviewer",
        "style": "high-pace, terse, focused",
        "agent": "Technical Interviewer",
        "lead": "Give me the sharp version.",
        "followup": "Answer in one or two clean points."
    }
}

PANEL_STYLES = {
    "3-Person Panel": [
        {
            "name": "Alex",
            "role": "Senior Engineer",
            "style": "technical, precise, skeptical",
            "focus": "architecture and engineering judgment",
            "agent": "Technical Interviewer"
        },
        {
            "name": "Maya",
            "role": "HR Director",
            "style": "behavioral, empathetic, thorough",
            "focus": "communication and collaboration",
            "agent": "HR Interviewer"
        },
        {
            "name": "Sam",
            "role": "Engineering Manager",
            "style": "strategic, leadership-focused, big-picture",
            "focus": "ownership and prioritization",
            "agent": "HR Interviewer"
        }
    ],
    "Cross-functional Panel": [
        {
            "name": "Riya",
            "role": "Product Manager",
            "style": "customer-aware, outcome-driven",
            "focus": "product judgment and prioritization",
            "agent": "HR Interviewer"
        },
        {
            "name": "Noah",
            "role": "Staff Engineer",
            "style": "deeply technical, systems-focused",
            "focus": "technical depth and tradeoffs",
            "agent": "Technical Interviewer"
        },
        {
            "name": "Elena",
            "role": "Data Partner",
            "style": "analytical, detail-aware",
            "focus": "measurement and decision quality",
            "agent": "Skeptic"
        }
    ],
    "All-Engineer Panel": [
        {
            "name": "Chris",
            "role": "Frontend Lead",
            "style": "user-focused, performance-aware",
            "focus": "client architecture and UX tradeoffs",
            "agent": "Technical Interviewer"
        },
        {
            "name": "Dana",
            "role": "Backend Lead",
            "style": "scalability-focused, exact",
            "focus": "APIs, data flow, and resilience",
            "agent": "Technical Interviewer"
        },
        {
            "name": "Victor",
            "role": "Principal Engineer",
            "style": "critical, high-bar, systems thinking",
            "focus": "tradeoffs under ambiguity",
            "agent": "Skeptic"
        }
    ]
}


def normalize_role(role):
    if role in ROLE_FOCUS:
        return role
    key = (role or "").strip().lower()
    mapped = ROLE_ALIASES.get(key)
    return mapped if mapped in ROLE_FOCUS else "SWE"


def normalize_question_type(question_type):
    if question_type in QUESTION_TYPE_TEMPLATES:
        return question_type
    key = (question_type or "").strip().lower()
    mapped = QUESTION_TYPE_ALIASES.get(key)
    return mapped if mapped in QUESTION_TYPE_TEMPLATES else "Behavioral"


def default_interviewer_for_mode(mode):
    if mode == "panel":
        return "3-Person Panel"
    if mode == "stress":
        return "Tough Critic"
    if mode == "speed_round":
        return "Timer Mode"
    return "Friendly HR"


def get_role_questions(role, question_type):
    role_key = normalize_role(role)
    question_key = normalize_question_type(question_type)
    focuses = ROLE_FOCUS[role_key]
    templates = QUESTION_TYPE_TEMPLATES[question_key]

    return [template.format(role=role_key, focus=focus) for focus in focuses for template in templates]


def get_interviewer_profile(name):
    if name in INTERVIEWER_PROFILES:
        return INTERVIEWER_PROFILES[name].copy()

    raw = (name or "").strip()
    key = raw.lower()

    if "principal" in key or "staff" in key or "architect" in key:
        return {
            "name": raw or "Principal Engineer",
            "role": "Principal Engineer",
            "style": "deep technical, systems-thinking, exacting",
            "agent": "Technical Interviewer",
            "lead": "Let's go deep on technical judgment and tradeoffs.",
            "followup": "Be concrete about architecture choices, constraints, and measurable outcomes.",
        }
    if "engineer" in key or "technical" in key:
        return {
            "name": raw or "Technical Interviewer",
            "role": "Senior Engineer",
            "style": "technical, precise, rigorous",
            "agent": "Technical Interviewer",
            "lead": "Let's focus on your technical decision quality.",
            "followup": "Explain tradeoffs and why your approach wins under constraints.",
        }
    if "product" in key:
        return {
            "name": raw or "Product Interviewer",
            "role": "Product Partner",
            "style": "outcome-driven, user-focused",
            "agent": "HR Interviewer",
            "lead": "Tie your answer to user impact and business outcomes.",
            "followup": "Prioritize clearly and justify the decision with evidence.",
        }

    profile = INTERVIEWER_PROFILES["Friendly HR"].copy()
    if raw:
        profile["name"] = raw
    return profile


def get_panel_members(panel_style):
    return [member.copy() for member in PANEL_STYLES.get(panel_style, PANEL_STYLES["3-Person Panel"])]