export LOG_LEVEL=info
export SUPPRESS_NO_IP_WARNING=no
env/bin/python3 build-dns.py
cp out/zone.db /var/named/sites-zone.db
rndc reload