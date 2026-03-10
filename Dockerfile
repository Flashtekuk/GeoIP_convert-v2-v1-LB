# 1. Start with Python 3 for the Web UI
FROM python:3.10-slim-buster

# 2. Set the working directory
WORKDIR /app

# 3. Fix sources for archived Debian Buster
RUN echo "deb http://archive.debian.org/debian buster main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://archive.debian.org/debian-security buster/updates main" >> /etc/apt/sources.list && \
    echo "deb http://archive.debian.org/debian buster-backports main contrib non-free" >> /etc/apt/sources.list

# 4. Install Legacy Python 2.7, dos2unix, and system dependencies
RUN apt-get update -o Acquire::Check-Valid-Until=false || true && \
    apt-get install -y --no-install-recommends --allow-unauthenticated gnupg2 curl && \
    apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 0E98404D386FA1D9 6ED0E7B82643E131 && \
    apt-get update -o Acquire::Check-Valid-Until=false && \
    apt-get install -y --no-install-recommends \
    openssh-client \
    python2.7 \
    geoip-bin \
    gawk \
    dos2unix && \
    rm -rf /var/lib/apt/lists/*

# 5. Install Python 3 dependencies (for the Web UI)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Install Python 2 dependencies
RUN curl https://bootstrap.pypa.io/pip/2.7/get-pip.py -o get-pip.py && \
    python2.7 get-pip.py && \
    python2.7 -m pip install --no-cache-dir geoip2-tools && \
    rm get-pip.py

# 7. Copy project files
COPY . .

# --- THE FIX ---
# Run dos2unix on the legacy scripts to strip any invisible \r characters
# then ensure they are executable.
RUN dos2unix legacy/geoip_convert-v2-v1.sh && \
    chmod +x legacy/geoip_convert-v2-v1.sh

# Add the current directory to the Python Path
ENV PYTHONPATH=/app

# 8. Expose Streamlit port
EXPOSE 8501

# 9. Start the Web UI
ENTRYPOINT ["streamlit", "run", "app/ui/main.py", "--server.port=8501", "--server.address=0.0.0.0"]