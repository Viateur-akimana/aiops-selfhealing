FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY remediation_service.py .
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=5s CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1
CMD ["python", "remediation_service.py"]
