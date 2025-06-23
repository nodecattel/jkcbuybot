docker run -d \
>   --name xbt-telebot-container \
>   --restart unless-stopped \
>   -v "$(pwd)/config.json:/app/config.json" \
>   -v "$(pwd)/logs:/app/logs" \
>   -v "$(pwd)/images:/app/images" \
>   xbt-telebot:latest
