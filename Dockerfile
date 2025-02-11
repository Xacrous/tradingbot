# Use official Python image
FROM python:3.9

# Set working directory
WORKDIR /app

# Install system dependencies required for TA-Lib
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    libffi-dev \
    python3-dev \
    libssl-dev \
    wget \
    curl \
    tar

# Manually install TA-Lib from source (fixes missing package issue)
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xvzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Copy all files into the container
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8080 (Digital Ocean requires this)
EXPOSE 8080

# Start the bot server
CMD ["python", "app.py"]
