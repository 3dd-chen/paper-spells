FROM python:3.11-slim

WORKDIR /app

# Install uv for fast dependency installation
RUN pip install uv

# Copy project files
COPY pyproject.toml ./

# Install dependencies using uv
# Note: In a real project with uv.lock, you would use `uv sync`
RUN uv pip install --system .

# Copy source code
COPY . .

# Cloud Run injects the PORT environment variable, default to 8080
ENV PORT=8080

# Run the app using uvicorn
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
