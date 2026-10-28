FROM python:3.13-slim
WORKDIR /app
RUN useradd -m app
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir
COPY . .
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
RUN mkdir data cache && chown app data cache
USER app
CMD ["uvicorn", "main:app","--host", "0.0.0.0","--port", "8000"]
