FROM python:3.12-slim

WORKDIR /app

# Отключаем буферизацию вывода Python (чтобы логи сразу были видны)
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
