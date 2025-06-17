FROM python:3.11-slim
WORKDIR /root/nonagon
COPY . .
RUN pip install -r requirements.txt
CMD [ "python", "-m", "app.bot.main" ]