import json

from models import Violation


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


def analyze_hidden_ads(client, segments, model_name, channel, broadcast_date, progress=None):
    if not segments:
        return [], {"content_genre": "Unknown", "ignored": True, "ignored_reason": "No transcript"}

    if progress:
        progress("AI აანალიზებს ჟანრს და ფარული რეკლამის კონტექსტს...")

    transcript_text = _segments_to_text(segments)

    system_prompt = f"""
You are an institutional Georgian TV monitoring compliance analyst preparing evidence for legal review.

Your first duty is genre classification. Apply these rules strictly:

ABSOLUTELY IGNORE these genres and return ignored=true with zero violations:
- Movies
- TV Series
- Fiction sitcoms
- Sports commentary, sports matches, 90-minute football/basketball/etc. broadcasts
- Daily news and standard news packages
- Official multi-minute commercial blocks or obvious ad breaks

TARGET AND ANALYZE only these genres:
- Daily TV Shows
- Morning Shows, including დილის გადაცემები
- Talk Shows
- Podcasts
- Cooking Shows
- Big entertainment or reality projects such as Dancing with the Stars, Got Talent, talent contests, studio entertainment blocks

Hidden advertising / product placement legal logic:
- In target show formats, hidden ads can sound natural, friendly, casual, or scripted into the host's conversation.
- Flag ANY moment where a TV host, presenter, studio guest, jury member, celebrity participant, or invited expert mentions, reviews, discusses, presents, praises, recommends, demonstrates, or encourages use of a specific commercial brand, product, company, clinic, hotel, shop, service, bank, medicine, food, cosmetic, makeup, skincare item, construction company, telecom, restaurant, app, website, or paid service.
- If a specific commercial brand/product/service is named, discussed, or promoted inside a target show format, flag it for human review even when it sounds natural or unforced.
- Do NOT flag fictional dialogue in movies/series, sports commentary, ordinary news reporting, or official ad blocks.

Dynamic duration:
- A violation may last 5 seconds or 20 minutes.
- Use the exact full advertising context start and end timestamps from the transcript.
- Do not compress the evidence to a fixed duration.
- Merge adjacent transcript lines when they are part of the same brand/product/service discussion.

Scoring:
- >85% = High Risk
- 50%-85% = Review Needed
- Return only probability_score >= 50.

Channel under review: {channel}
Broadcast date: {broadcast_date}
""".strip()

    user_prompt = f"""
Analyze this Georgian transcript with timestamps.
Return JSON only.

Transcript:
{transcript_text}
""".strip()

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_schema", "json_schema": ANALYSIS_SCHEMA},
    )

    data = json.loads(response.choices[0].message.content)
    metadata = {
        "content_genre": data.get("content_genre", "Unknown"),
        "ignored": bool(data.get("ignored", False)),
        "ignored_reason": data.get("ignored_reason", ""),
    }

    if metadata["ignored"]:
        return [], metadata

    violations = []
    for item in data.get("violations", []):
        score = max(0, min(100, int(item["probability_score"])))
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
