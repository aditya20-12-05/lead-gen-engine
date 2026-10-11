FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY engine engine
COPY briefs briefs
ENV PORT=8080
CMD python -m engine seed && exec gunicorn "engine:create_app()" --bind 0.0.0.0:$PORT --workers 2 --timeout 120
