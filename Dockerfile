# Pull official Python image from Dockerhub
# Check here for specific versions/tags: https://hub.docker.com/_/python/tags
FROM python:slim

# Set the working directory in the container.
WORKDIR /app

# Copy only the requirements first to leverage Docker's caching mechanism.
COPY requirements.txt .

# Upgrade pip and install Python dependencies in one layer.
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code.
COPY . .

# Expose the port the FastAPI app runs on.
EXPOSE 8080

# Run the FastAPI application with uvicorn.
CMD ["uvicorn", "splash_links.main:app", "--host", "0.0.0.0", "--port", "8080"]

# Metadata labels (update with your project info).
LABEL Name="splash_links" \
      Version="0.1.0" \
      Description="A FastAPI triplestore service for storing and searching links" \
      Maintainer="ALS Computing"
