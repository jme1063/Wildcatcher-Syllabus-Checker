# Makes sure we are using python 3.11, as needed for program to work.
# eventually we may be able to update this.
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements from text file and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy all files in current dir (which will be everything)
COPY . .

# Default command to run, in this case runs chatbot.py to start program
CMD ["python", "main.py"]
