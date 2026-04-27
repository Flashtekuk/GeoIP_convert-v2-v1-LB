# Use the specific Python 2.7 image 
FROM python:2.7.18-slim-buster

# Set the working directory inside the container 
WORKDIR /app

# Fix sources for archived Debian Buster 
RUN echo "deb http://archive.debian.org/debian buster main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://archive.debian.org/debian-security buster/updates main" >> /etc/apt/sources.list && \
    echo "deb http://archive.debian.org/debian buster-backports main contrib non-free" >> /etc/apt/sources.list

# Install Keys and system dependencies 
RUN apt-get update -o Acquire::Check-Valid-Until=false || true && \
    apt-get install -y --no-install-recommends --allow-unauthenticated gnupg2 curl && \
    apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 0E98404D386FA1D9 6ED0E7B82643E131 && \
    apt-get update -o Acquire::Check-Valid-Until=false && \
    apt-get install -y --no-install-recommends geoip-bin gawk && \
    rm -rf /var/lib/apt/lists/*

# Install Python depenendencies
RUN pip install --no-cache-dir geoip2-tools

# Copy scripts
COPY geoip_convert-v2-v1.sh /usr/local/bin/geoip_convert-v2-v1.sh
COPY launcher.sh /usr/local/bin/launcher.sh

RUN chmod +x /usr/local/bin/geoip_convert-v2-v1.sh /usr/local/bin/launcher.sh

# Create the output directory inside the container
RUN mkdir /output

# The launcher is now the entrypoint
ENTRYPOINT [ "/usr/local/bin/launcher.sh" ]


# Build Command 
# docker build -t geoip_convert-v2-v1 .