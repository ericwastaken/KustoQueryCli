# Use an official Python runtime as a parent image
FROM python:3.8-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Install system dependencies for Azure CLI
RUN apt-get update && apt-get install -y curl gnupg lsb-release \
    && curl -sL https://aka.ms/InstallAzureCLIDeb | bash

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entrypoint script and give it the necessary permissions
COPY entrypoint.sh /usr/src/app
RUN chmod +x /usr/src/app/entrypoint.sh

# Set the entrypoint script as the entry point for the container
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
