import google.generativeai as genai
import time
import json
from pathlib import Path
from time import sleep

from media_tools import TEMP_DIR, extract_audio_chunk
from models import TranscriptSegment

CHUNK_SECONDS = 10 * 60

def _safe_unlink(path):
    for _ in range(5):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            sleep(0.5)

GEORGIAN_AD_PROMPT = "ბორჯომი, კრემი, ვიტამინი, აფთიაქი, კლინიკა, კანის მოვლა, შეძენა, ფასდაკლება, PSP, ავერსი, საქართველოს ბანკი"

def transcribe_video(video_path, model_name, gemini_key, language="ka", progress=None, initial_prompt=GEORGIAN_AD_PROMPT):
    video_path = Path(video_path)
    TEMP_DIR.mkdir(exist_ok=True)
    segments = []

    if not gemini_key:
        raise ValueError("Gemini API Key აუცილებელია ტრანსკრიპციისთვის!")

    genai.configure(api_key=gemini_key)

    # We process generously sized chunks
    for chunk_index in range(0, 24 * 60 * 60, CHUNK_SECONDS):
        audio_path = TEMP_DIR / f"{video_path.stem}_{chunk_index}.m4a"

        try:
            extract_audio_chunk(video_path, chunk_index, CHUNK_SECONDS, audio_path)
        except Exception:
            break

        if audio_path.stat().st_size < 1024:
            audio_path.unlink(missing_ok=True)
            break

        if progress:
            progress(f"Gemini აუდიო ანალიზი: {chunk_index // 60} წუთიდან...")

        try:
            # Upload file to Gemini
            uploaded_file = genai.upload_file(path=str(audio_path))
            
            # Wait for processing
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(2)
                uploaded_file = genai.get_file(uploaded_file.name)

            # Prompt Gemini to transcribe with timestamps
            model = genai.GenerativeModel(model_name=model_name)
            prompt = f"""
            დაწერე ამ აუდიოს ზუსტი ქართული ტრანსკრიპცია. 
            გამოიყენე შემდეგი საკვანძო სიტყვები სიზუსტისთვის: {initial_prompt}
            დააბრუნე პასუხი JSON ფორმატში, სადაც თითოეულ სეგმენტს ექნება start, end და text.
            მაგალითი: [{{"start": 0.0, "end": 5.0, "text": "გამარჯობა"}}]
            """

            response = model.generate_content([prompt, uploaded_file], generation_config={"response_mime_type": "application/json"})
            
            # Clean up uploaded file from Google servers
            genai.delete_file(uploaded_file.name)

            try:
                data = json.loads(response.text)
                for item in data:
                    text = item.get("text", "").strip()
                    if not text:
                        continue
                    segments.append(
                        TranscriptSegment(
                            start=float(item.get("start", 0)) + chunk_index,
                            end=float(item.get("end", 0)) + chunk_index,
                            text=text,
                        )
                    )
            except Exception as e:
                if progress:
                    progress(f"შეცდომა JSON-ის წაკითხვისას: {str(e)}")
                # Fallback: if Gemini returns plain text instead of JSON
                text = response.text.strip()
                if text:
                    segments.append(
                        TranscriptSegment(
                            start=float(chunk_index),
                            end=float(chunk_index + CHUNK_SECONDS),
                            text=text
                        )
                    )

        except Exception as e:
            if progress:
                progress(f"შეცდომა Gemini ტრანსკრიპციისას: {str(e)}")
            break
        finally:
            _safe_unlink(audio_path)

    return segments
