#!/bin/bash
DATE_TODAY=$(date +"%Y%m%d")

/usr/local/bin/geoip_convert-v2-v1.sh "$@"

if [ -d "$DATE_TODAY" ]; then
    echo "Processing complete. Moving files to /output...."
    mv "$DATE_TODAY"/*.dat /output/ 2>/dev/null
    echo "Files moved successfully."
else
    echo "Error: Output directory $DATE_TODAT not found."
    exit 1
fi