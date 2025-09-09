FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install -U pip \
 && pip install "uvicorn[standard]" \
 && pip install .
EXPOSE 8000
CMD ["uvicorn","app.api.main:app","--host","0.0.0.0","--port","8000"]