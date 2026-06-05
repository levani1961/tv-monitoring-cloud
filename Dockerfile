# გამოიყენე ოფიციალური Python იმიჯი
FROM python:3.10-slim

# გარემო ცვლადების დაყენება
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# სამუშაო დირექტორიის შექმნა
WORKDIR /app

# სისტემური დამოკიდებულებების ინსტალაცია (მხოლოდ FFmpeg)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# დამოკიდებულებების ფაილის კოპირება
COPY requirements.txt .

# ბიბლიოთეკების ინსტალაცია
RUN pip install --no-cache-dir -r requirements.txt

# მთლიანი პროექტის კოპირება
COPY . .

# საჭირო საქაღალდეების შექმნა
RUN mkdir -p downloads extracted_clips screenshots temp_audio reports

# Streamlit-ისთვის პორტის გახსნა (თუ ინტერფეისს გამოიყენებთ)
EXPOSE 8501

# გაშვების ბრძანება (შეგიძლიათ შეცვალოთ python run_monitor.py-ზე თუ მხოლოდ CLI გინდათ)
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
