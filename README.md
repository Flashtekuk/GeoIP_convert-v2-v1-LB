# GeoIP_convert-v2-v1
convert GeoLite2-Country v2 DB to GeoIP v1 Country Edition .dat file

<br>
git clone https://github.com/Flashtekuk/GeoIP_convert-v2-v1-LB<br>
cd GeoIP_convert-v2-v1-LB <br>
chmod +x geoip_convert-v2-v1.sh <br>
<br>

  docker run -it -v ${PWD}:/app python:2.7.18 bash -c /app/go.sh

<br>
./geoip_convert-v2-v1.sh LicenceKey [CustomName] <br>
<br>
Access to the MaxMind GeoLite databases requires a (freely available) licence key, as of 2019-12-30 <br>
For more details, see: https://blog.maxmind.com/2019/12/18/significant-changes-to-accessing-and-using-geolite2-databases/
