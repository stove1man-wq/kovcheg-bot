FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY kovcheg_bot ./kovcheg_bot
ENV DB_PATH=/data/bot.db
VOLUME /data
CMD ["python", "-m", "kovcheg_bot"]
