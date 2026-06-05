# Enterprise AI-Powered TV Monitoring System

Streamlit-ზე აგებული სამუშაო სისტემა ფარული რეკლამის / product placement / native marketing ნიშნების სამართლებრივი მონიტორინგისთვის.

აპლიკაცია იყენებს:

- Streamlit dashboard-ს
- OpenAI ტრანსკრიპციას ქართული აუდიოსთვის
- GPT ანალიზს ჟანრის მკაცრი ფილტრით
- FFmpeg-ს დინამიკური ხანგრძლივობის legal proof კლიპებისთვის
- openpyxl-ს Excel ანგარიშისთვის

## საქაღალდეები

- `downloads/` - Myvideo.ge-დან მიღებული დროებითი სამუშაო ვიდეოები
- `extracted_clips/` - საბოლოო სამართლებრივი MP4 მტკიცებულებები
- `screenshots/` - დარღვევის სქრინშოთები
- `reports/` - საბოლოო Excel ანგარიში
- `temp_audio/` - დროებითი აუდიო chunk-ები, რომლებიც ავტომატურად იწმინდება
- `config.ini` ან `.env` - OpenAI API გასაღები

## 1. კონფიგურაცია

დააკოპირეთ `config.ini.example` და დაარქვით:

```text
config.ini
```

შემდეგ ჩაწერეთ თქვენი OpenAI API key:

```ini
[openai]
api_key = თქვენი_api_key_აქ
transcription_model = gpt-4o-transcribe
analysis_model = gpt-4o-mini
```

API key არ ჩაიწერება Python კოდში.

## 2. პაკეტების დაყენება

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

FFmpeg უნდა მუშაობდეს:

```powershell
ffmpeg -version
```

## 3. აპლიკაციის გაშვება

```powershell
streamlit run app.py
```

გექნებათ ორი წყარო:

- `Myvideo.ge Archive` - არხი, თარიღების დიაპაზონი, საათები და URL/URL შაბლონი
- `Local Disk / Flash Drive / Disc` - ლოკალური ვიდეოების საქაღალდე

## Myvideo.ge URL შაბლონი

Myvideo.ge-ს არქივის ზუსტი URL ფორმატი შეიძლება არხების მიხედვით იცვლებოდეს. ველში შეგიძლიათ ჩაწეროთ პირდაპირი URL ან შაბლონი:

```text
https://example.ge/archive/{channel}/{date}/{hour}
```

აპი `{channel}`, `{date}`, `{hour}` მნიშვნელობებს ავტომატურად ჩასვამს.

## სამართლებრივი მტკიცებულება

ყველა აღმოჩენილი კლიპი იჭრება AI-ის მიერ დაბრუნებული რეალური `start/end` დროებით. კლიპზე FFmpeg მუდმივად აწერს:

```text
CHANNEL_NAME | YYYY-MM-DD HH:MM:SS
```

ფაილის სახელი იქმნება ფორმატით:

```text
[Channel]_[YYYY-MM-DD]_[HH-MM-SS]_Hidden_Ad.mp4
```

## ჟანრის ფილტრი

AI მკაცრად იგნორირებს ფილმებს, სერიალებს, სიტკომებს, სპორტს, ყოველდღიურ ნიუსს და ოფიციალურ სარეკლამო ბლოკებს. ანალიზდება მხოლოდ შოუები, დილის გადაცემები, talk show, podcast, cooking show და entertainment/reality ფორმატები.

თუ გვერდი მოითხოვს ავტორიზაციას, captcha-ს ან დამატებით დაცვას, აპლიკაცია ამას გვერდს არ აუვლის. ასეთ შემთხვევაში საჭიროა ოფიციალური წვდომა ან პირდაპირი HLS URL.

## ლიცენზიის ვადა

კოდში ჩადებულია:

```python
LICENSE_EXPIRATION_DATE = "2026-06-30"
```

ამ თარიღის შემდეგ პროგრამა დაბლოკავს AI ანალიზს და აჩვენებს:

```text
License expired. Please contact the administrator.
```
