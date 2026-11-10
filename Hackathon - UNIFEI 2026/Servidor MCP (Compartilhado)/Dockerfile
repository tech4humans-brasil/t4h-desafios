FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 TEMA=triagem
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8765
ENTRYPOINT ["python", "mundo.py", "--host", "0.0.0.0", "--sem-navegador"]
