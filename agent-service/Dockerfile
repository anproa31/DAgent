FROM python:3.11-slim

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY . /usr/src/app/

ENV PYTHONPATH=/usr/src/app/src

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
