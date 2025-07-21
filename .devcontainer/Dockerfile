# Dockerfile

# Use the official Python 3.11 image as the base
FROM python:3.11-slim-buster

# Install required packages
RUN apt-get update && \
    apt-get install -y \
    unzip \
    curl \
    less \
    groff \
    build-essential \
    libssl-dev \
    libffi-dev \
    libgmp-dev \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf awscliv2.zip aws

# Install AWS SAM CLI
RUN curl -Lo sam_installation.zip https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip && \
    unzip sam_installation.zip -d sam-installation && \
    ./sam-installation/install && \
    rm -rf sam_installation.zip sam-installation

# Install Docker (Docker-in-Docker)
RUN curl -fsSL https://get.docker.com | sh

# Install project dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Expose ports if necessary
EXPOSE 3000

# Set the default working directory
WORKDIR /workspace

# Start Docker daemon in the background
CMD ["bash", "-c", "dockerd & sleep 1 && exec ${SHELL:-bash}"]
