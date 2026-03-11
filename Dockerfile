# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Ensure Python writes unbuffered output for MCP stdio
ENV PYTHONUNBUFFERED=1

# Install system dependencies for Azure CLI
RUN apt-get update && apt-get install -y curl gnupg lsb-release \
    && curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app (includes entrypoint.sh)
COPY . .

# Ensure entrypoint script is executable
RUN chmod +x /usr/src/app/entrypoint.sh

# Set the entrypoint script as the entry point for the container
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
