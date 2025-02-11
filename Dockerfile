Dockerfile
# Use official Python image
FROM python:3.9

# Set working directory
WORKDIR /app

# Copy all files into the container
COPY . /app

# Install dependencies
RUN pip install -r requirements.txt

# Expose port 8080 (Digital Ocean requires this)
EXPOSE 8080

# Start the bot server
CMD ["python", "app.py"]

Requirements.txt
ccxt
pandas
python-telegram-bot
requests
flask
