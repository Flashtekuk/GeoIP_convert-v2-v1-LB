# GeoIP_convert-v2-v1
Convert GeoLite2-Country v2 DB to GeoIP v1 Country Edition .dat file

> ### ⚠️ Disclaimer 
> This tool is provided "as-is" under the **Apache License 2.0**. While it facilitates the conversion of GeoIP data, we do not provide the underlying GeoIP database files or the required API keys.

### User Responsibilities:
* Obtaining a valid MaxMind License Key.
* Complying with the MaxMind EULA and data privacy regulations (such as GDPR or CCPA) regarding the storage and processing of IP-related data.
* Ensuring the security of their own API Keys and Credentials. 

Access to the MaxMind GeoLite databases requires a (freely available) license key, as of 2019-12-30.  
For more details, see: [MaxMind Blog - Significant Changes to GeoLite2](https://blog.maxmind.com/2019/12/18/significant-changes-to-accessing-and-using-geolite2-databases/)

---

## Installation & Usage

Follow these steps to load the image and run the conversion tool on your local machine.

### 1. Load the Docker Image
After downloading the `geoip_convert-v2-v1.tar` file, restore it to your local Docker engine by running:

```bash
docker load -i /path/to/geoip_convert-v2-v1.tar

### 2. Prep the Docker Compose file 
Download the docker-compose.yml from the repo and configure it with you MaxMind API key


### 3. Run the conversion 
run the Docker Compose file to start the conversion 

```bash
docker compose up 


### 4. clean up Docker 
after you have your file clean up Docker of the exited container 

```bash 
dockr compose down





## License
This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.