FROM python:3.11.9

# Set the working directory
WORKDIR /app

# Set the environment variable to avoid buffering of output
ENV PYTHONUNBUFFERED 1

# Install PostgreSQL development libraries and build dependencies
RUN apt-get update && apt-get install -y libpq-dev gcc

# Copy the requirements file and install dependencies globally
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 8000 for the application
EXPOSE 8000

# Run the Django development server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
