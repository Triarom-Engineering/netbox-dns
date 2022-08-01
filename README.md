# netbox-dns

This tool is used to generate a BIND9 DNS configuration from Netbox. It's fairly specific
to our use of Netbox, but the concept should apply to most setups.

Parts of this script are derrived from the tools used by Electromagnetic Field Camp's NOC team in the [emfnoc](https://github.com/emfcamp/emfnoc) repo.

## Configuring

An example copy of the configuration file `.nocconfig.yaml` has been provided. Copy this to any of the following locations: `~/.nocconfig.yaml`, `{pwd}/.nocconfig.yaml` and `/etc/.nocconfig.yaml`.

Most zone settings can be left default, but remember to change `soa` to the domain (or subdomain in our case) used at your site, and change `soa_admin` to an email address where the @ is replaced by a .

You must also change the netbox configuration, setting the server and add a token from the Netbox admin page.

A file called .serial is created in the pwd to track incremental changes to the zone file - this may change to just using a timestamp.

## Operation

Once started, the script will find all devices registered in Netbox and take the primary IPv4 address and create an A record for it. It combines the asset tag of the device and the slug of the site, for example

`A gateway1.my-test-site.sites.mycompany.net 172.16.22.1`

A zone db file is placed in out/zone.db, which can be copied into the BIND9 databases directory.

A script, `update-zone.sh` is provided to automatically run the script and update the zone file in BIND9.