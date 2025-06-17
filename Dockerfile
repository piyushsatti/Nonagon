FROM python:3.11
WORKDIR /root/nonagon
COPY . .
EXPOSE 8080
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN pip install -r requirements.txt
CMD [ "python", "-m", "app.bot.main", "--port", "8080"]