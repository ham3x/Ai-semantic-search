FROM --platform=linux/amd64 python:3.9-slim

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

COPY app.py /app.py

CMD ["python", "app.py"]