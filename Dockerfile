# Use official Python image
FROM python:3.10-slim

# Set work directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Expose TCP port
EXPOSE 8765

# Set environment variables for production (optional)
# ENV TWITTER_AUTH_TOKEN=your_token
# ENV TWITTER_CT0=your_ct0

# Run the MCP server on TCP (host 0.0.0.0, port 8765)
CMD ["python", "server.py"] 