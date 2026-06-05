import json
import google.generativeai as genai

from models import Violation

# აქ შეგიძლიათ ჩასვათ თქვენი ახალი Gemini API Key, თუ config.ini-ში არ გიწერიათ:
GEMINI_API_KEY = "AQ.Ab8RN6JnMzNGqDqTcO_7RwM-PraHQ5cDQDWdiCRSOi0j-ILtHw"

# ... (rest of the genres and TARGET_GENRES remain the same)


TARGET_GENRES = [
    "Morning Show",
    "Daily TV Show",
    "Talk Show",
    "Podcast",
    "Cooking Show",
    "Entertainment/Reality Project",
]

IGNORED_GENRES = [
    "Movie",
    "TV Series",
    "Fiction Sitcom",
    "Sports Commentary/Match",
    "Daily News",
    "Official Commercial Block",
]

ANALYSIS_SCHEMA = {
    "name": "enterprise_hidden_ad_detection",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "content_genre": {"type": "string"},
            "ignored": {"type": "boolean"},
            "ignored_reason": {"type": "string"},
            "violations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "start": {"type": "number"},
                        "end": {"type": "number"},
                        "georgian_transcript": {"type": "string"},
                        "brand_name": {"type": "string"},
                        "probability_score": {"type": "integer"},
                        "risk_status": {
                            "type": "string",
                            "enum": ["High Risk", "Review Needed"],
                        },
                        "reason": {"type": "string"},
                    },
                    "required": [
                        "start",
                        "end",
                        "georgian_transcript",
                        "brand_name",
                        "probability_score",
                        "risk_status",
                        "reason",
                    ],
                },
            },
        },
        "required": ["content_genre", "ignored", "ignored_reason", "violations"],
    },
}


def _segments_to_text(segments):
    return "\n".join(f"[{segment.start:.2f}-{segment.end:.2f}] {segment.text}" for segment in segments)


def _risk_status(score):
    if score > 85:
        return "High Risk"
    if 50 <= score <= 85:
        return "Review Needed"
    return ""


def analyze_hidden_ads(gemini_key, segments, model_name, channel, broadcast_date, progress=None):
    if not segments:
        return [], {"content_genre": "Unknown", "ignored": True, "ignored_reason": "No transcript"}

    if progress:
        progress("Gemini AI აანალიზებს ჟანრს და ფარული რეკლამის კონტექსტს...")

    # პრიორიტეტი ენიჭება გადმოცემულ key-ს, შემდეგ ფაილში არსებულს
    actual_key = gemini_key or GEMINI_API_KEY
    if not actual_key or "აქ_ჩავსვამ" in actual_key:
        raise ValueError("Gemini API Key არ არის მითითებული config.ini-ში ან ai_analysis.py-ში!")

    genai.configure(api_key=actual_key)
    
    transcript_text = _segments_to_text(segments)

    system_prompt = f"""
You are an institutional Georgian TV monitoring compliance analyst. Your task is to distinguish between neutral information (news) and hidden advertising (covert ads/product placement).

CRITICAL DISTINCTION RULES:
1. NEUTRAL NEWS (Do NOT flag):
   - Reporting facts without commercial intent. 
   - Example: 'ბორჯომში ცივა' (It is cold in Borjomi) - this is a geographical fact/weather report.

2. COVERT ADVERTISING (MUST flag):
   - Promoting a brand, product, or service within entertainment, morning, or talk shows.
   - Example: 'ეს კრემი საუკეთესოა' (This cream is the best) - this is an ad.

Output requirements:
- Return JSON strictly following this structure:
{{
  "content_genre": "string",
  "ignored": boolean,
  "ignored_reason": "string",
  "violations": [
    {{
      "is_covert_ad": boolean,
      "start": number,
      "end": number,
      "georgian_transcript": "string",
      "brand_name": "string",
      "probability_score": number,
      "risk_status": "High Risk" | "Review Needed",
      "reason": "string"
    }}
  ]
}}
""".strip()

    user_prompt = f"""
Analyze this Georgian transcript with timestamps.
Return JSON only.

Transcript:
{transcript_text}
""".strip()

    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config={"response_mime_type": "application/json"}
    )
    
    response = model.generate_content([system_prompt, user_prompt])
    
    try:
        data = json.loads(response.text)
    except Exception:
        # Fallback if the response is not clean JSON
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        data = json.loads(text)
    metadata = {
        "content_genre": data.get("content_genre", "Unknown"),
        "ignored": bool(data.get("ignored", False)),
        "ignored_reason": data.get("ignored_reason", ""),
    }

    if metadata["ignored"]:
        return [], metadata

    violations = []
    for item in data.get("violations", []):
        # მხოლოდ იმ შემთხვევაში ვიწერთ, თუ AI-მ დაადასტურა, რომ ეს ფარული რეკლამაა
        if not item.get("is_covert_ad", False):
            continue

        score = max(0, min(100, int(item.get("probability_score", 0))))
        status = _risk_status(score)
        if not status:
            continue

        start = max(0.0, float(item["start"]))
        end = max(start + 1, float(item["end"]))

        violations.append(
            Violation(
                start=start,
                end=end,
                transcript=item["georgian_transcript"].strip(),
                brand_name=item["brand_name"].strip() or "Context-inferred commercial entity",
                probability_score=score,
                risk_status=status,
                reason=item["reason"].strip(),
                channel=channel,
                broadcast_date=broadcast_date,
                genre=metadata["content_genre"],
            )
        )

    return violations, metadata
