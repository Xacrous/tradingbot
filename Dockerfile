# Use official Python image
FROM python:3.9

# Set working directory
WORKDIR /app

# Copy all files into the container
COPY . /app

# Install Python dependencies (Fix NumPy issue)
RUN pip install --no-cache-dir numpy==1.23.5 && \
    pip install --no-cache-dir -r requirements.txt

# Expose port 8080 (Digital Ocean requires this)
EXPOSE 8080

# Start the bot server
CMD ["python", "app.py"]
