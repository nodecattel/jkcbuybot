# Use official Python 3.10 image
FROM python:3.10-slim

# Set working directory in container
WORKDIR /mnt/vagrant/app

# Copy requirements.txt to container
COPY requirements.txt requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code to container
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the fixed version of the bot
CMD ["python", "telebot_fixed.py"]
