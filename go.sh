source /app/license.txt

cat << EOF > /etc/apt/sources.list

deb http://archive.debian.org/debian/ buster main contrib non-free
deb http://archive.debian.org/debian/ buster-updates main contrib non-free
deb http://archive.debian.org/debian/ buster-backports main contrib non-free

EOF

apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 0E98404D386FA1D9 6ED0E7B82643E131

apt update
apt install -y geoip-bin gawk
pip install geoip2-tools

/app/geoip_convert-v2-v1.sh ${LIC}

MYIP=$(curl ifconfig.me/ip)
geoiplookup -f 20*/GeoIP.dat -v ${MYIP}
geoiplookup -f 20*/GeoIP.dat -i ${MYIP}
