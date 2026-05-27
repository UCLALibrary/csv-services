FROM python:3.12-slim

WORKDIR /app

COPY web/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ ./core/
COPY web/app/ ./web/app/

EXPOSE 8000
CMD ["uvicorn", "web.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
