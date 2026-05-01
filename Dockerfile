FROM python:3.11-slim

# Set the working directory
WORKDIR /code

# Install dependencies
COPY ./backend/requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the entire project
COPY . /code

# Hugging Face Spaces expose port 7860
EXPOSE 7860

# Start the FastAPI server — workdir is /code, server.py is at /code/backend/server.py
# voice_module is a sibling package inside backend/, so we set PYTHONPATH to backend/
CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "7860"]
