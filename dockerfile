# ---- Base Stage ----
# Use a specific, slim version of Python for a smaller and more secure image.
FROM python:3.11.9-slim-bullseye as base

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# Configure Poetry to create the virtual environment inside the project directory
ENV POETRY_VIRTUALENVS_IN_PROJECT=true

# Set the working directory
WORKDIR /app

# Install system dependencies required for packages like psycopg2 (PostgreSQL adapter)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*


# ---- Builder Stage ----
# This stage is dedicated to installing Python dependencies
FROM base as builder

# Install Poetry
RUN pip install poetry

# Copy only the dependency definition files to leverage Docker's layer caching.
# The layer will only be rebuilt if these files change.
COPY poetry.lock pyproject.toml ./

# Install dependencies into the project's .venv directory.
# --no-root prevents installing the project package itself.
# --no-interaction and --no-ansi are good for CI/CD environments.
RUN poetry install --no-root --no-interaction --no-ansi


# ---- Final Stage ----
# This is the final, lean image that will be deployed.
FROM base as final

# Create a non-root user for better security
RUN useradd --system --create-home --shell /bin/bash appuser

# Copy the virtual environment with all dependencies from the builder stage
COPY --from=builder /app/.venv ./.venv

# Copy the application source code
COPY . .

# Change ownership of the app directory to the new non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Add the virtual environment's bin directory to the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose the port the app will run on.
# Railway will automatically map its internal port to this.
EXPOSE 8000

# The default command to run the application using the Daphne ASGI server.
# Note: Railway's "Start Command" will override this.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "Handcrafts.asgi:application"]

