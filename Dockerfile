# Use a lightweight Python Linux image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy your dependency file and install libraries
COPY pyproject.toml .
RUN pip install .

# Copy your entire application code into the container
COPY . /app

# Expose the port FastAPI runs on
EXPOSE 8000

# The command to boot the server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]