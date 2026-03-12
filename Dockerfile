# Pull official Python image from Dockerhub
# Check here for specific versions/tags: https://hub.docker.com/_/python/tags
FROM python:slim

# Set the working directory in the container.
WORKDIR /app

# Copy only the requirements first to leverage Docker’s caching mechanism.
COPY requirements.txt .

# Upgrade pip and install Python dependencies in one layer.
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code.
COPY . .

# Expose the port your app runs on.
EXPOSE 8080

# Default command: replace with your application’s entrypoint.
CMD ["python", "-c", "print('Hello, World!')"]

# Metadata labels (update with your project info).
LABEL Name="Project Template" \
      Version="1.0" \
      Description="A template for a Python project with Docker" \
      Maintainer="Your Name"