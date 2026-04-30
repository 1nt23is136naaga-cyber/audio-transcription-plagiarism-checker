FROM python:3.11

# Set the working directory
WORKDIR /code

# Install dependencies
COPY ./backend/requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the entire project
COPY . /code

# Hugging Face Spaces expose port 7860 by default
EXPOSE 7860

# Ensure Python can find the voice_module inside the backend folder
ENV PYTHONPATH=/code/backend

# Start the FastAPI server
CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "7860"]
