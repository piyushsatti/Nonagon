FROM python:3.11-slim
WORKDIR /nonagon
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .