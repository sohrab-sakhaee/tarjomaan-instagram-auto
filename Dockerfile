FROM python:3.11-slim

WORKDIR /app

# نصب کتابخانه‌ها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کردن کد
COPY app.py .
COPY Procfile .

# اجرا
CMD ["python", "app.py"]
