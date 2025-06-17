telebot:
    cp telebot_fixed.py telebot.py && \
    docker build -t telebot . && \
    docker compose up -d telebot

telebot-logs:
    docker compose logs -f telebot

telebot-restart:
    docker compose restart telebot

telebot-stop:
    docker compose stop telebot
