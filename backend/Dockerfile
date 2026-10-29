FROM python:3.13-slim
WORKDIR /app
RUN useradd -m app
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir
COPY . .
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
RUN mkdir data && chown app data
USER app
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]