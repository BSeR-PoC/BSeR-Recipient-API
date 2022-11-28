FROM python:3.10.4-alpine3.15

WORKDIR /app

COPY requirements.txt requirements.txt

RUN python3 -m pip install -r requirements.txt --no-cache-dir

EXPOSE 8080

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--root-path", "/bser-recipient-api"]