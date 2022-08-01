# Triarom NOC (c) 2022
# Netbox DNS Zone Generator

# By Cameron Fleming cpfleming.co.uk - MIT License

import dns.zone
import dns.rdataset
import dns.rdataclass
import dns.rdata
import dns.rdtypes
import dns.rdtypes.IN.A
import dns.rdtypes.ANY.NS

import yaml
import logging
import os
from pathlib import Path
import pynetbox
import ipaddress

zone = {}

def find_config():
    # Find the configuration file on the host
    home_dir = Path.home()
    
    if os.path.exists(os.path.join(home_dir, ".nocconfig.yaml")):
      logging.debug("using .nocconfig in ~/")
      return os.path.join(home_dir, ".nocconfig.yaml")
    
    if os.path.exists(os.path.join(os.getcwd(), ".nocconfig.yaml")):
      logging.debug("using .nocconfig in pwd")
      return os.path.join(os.getcwd(), ".nocconfig.yaml")

    if os.path.exists("/etc/.nocconfig.yaml"):
      logging.debug("using .nocconfig in /etc (global)")
      return "/etc/.nocconfig.yaml"

    logging.error(f"no .nocconfig.yaml found, checked ~/.nocconfig.yaml, " +
    f"{os.path.join(os.getcwd(), '.nocconfig.yaml')} and /etc/.nocconfig.yaml")
    exit(1)

def get_serial():
  serial_num_path = os.path.join(os.getcwd(), ".serial")
  serial = config['serial']['start_at']

  if os.path.exists(serial_num_path):
    with open(serial_num_path, "r+") as f:
      serial = int(f.read()) + 1

  if config['serial']['auto_increment']:
    with open(serial_num_path, "w+") as f:
      f.write(str(serial))

  logging.debug(f"incremented serial to {serial}")
  return serial

  
if __name__ == "__main__":
  # Setup logging 
  log_level = os.environ.get("LOG_LEVEL", "info").upper()
  suppress_no_ip = False
  if os.environ.get("SUPPRESS_NO_IP_WARNING", "NO").upper() == "YES":
    suppress_no_ip = True

  logging.basicConfig(level=log_level)

  # Read in yaml .nocconfig file
  logging.debug("reading configuration")
  config_path = find_config()
  config = {}

  with open(config_path, "r") as stream:
    try:
      config = yaml.safe_load(stream)
    except yaml.YAMLError as e:
      logging.error(f"failed to read yaml, {e}")

  # Connect to Netbox server
  nb = pynetbox.api(
    config['netbox']['server'],
    token = config['netbox']['token']
  )

  devices = nb.dcim.devices.all()
  zone_devices = []
  for d in devices:
    if not d.primary_ip4:
      if not suppress_no_ip: logging.warning(f"{d.site.slug}/{d.asset_tag} has no primary address")
      continue
    
    logging.debug(f"{d.primary_ip4} - {d.site.slug}/{d.asset_tag} ({d.status})")
    # TODO: Refactor the CIDR stripping technique, there must be a better way.
    # probably.
    # TODO: We're only handling IPv4 here, there is currently no v6 in the mgmt network
    # This will be refactoring!

    # Check the status of the device's deployment, possible states are handled by Netbox.
    # The states should be set within .nocconfig
    states = ["ACTIVE"]
    if not config['zone']['include_states']:
      logging.warning("no include_states found in .nocconfig/zone, adding only actives.")
    else:
      states = config['zone']['include_states']

    if str(d.status).upper() not in states:
      logging.debug(f"skipping {d.site.slug}/{d.asset_tag} - not in a permitted state ({d.status})")
      continue

    # Device status is approved, continue to zone setup
    addr = ipaddress.ip_address(str(d.primary_ip4).split("/")[0])

    zone_devices.append(
      {
        "asset": str(d.asset_tag).lower(),
        "site": str(d.site.slug).lower(),
        "address": addr
      }
    )

  # Finished processing devices, create the zone.
  logging.info(f"found {len(zone_devices)} devices to add to zone.")

  zone = dns.zone.Zone(config['zone']['soa'])
  
  # Create SOA record
  soa_rdataset = zone.find_rdataset("@", dns.rdatatype.SOA, create=True)
  soa_rdata = dns.rdtypes.ANY.SOA.SOA(dns.rdataclass.IN, dns.rdatatype.SOA, 
    mname = config['zone']['soa'],
    rname = config['zone']['soa_admin'],
    serial = get_serial(),
    refresh = config['zone']['zone_refresh_time'],
    retry = config['zone']['zone_retry_interval'],
    expire = config['zone']['expiry_period'],
    minimum = config['zone']['ns_cache_time']
  )
  soa_rdataset.add(soa_rdata, ttl=config['zone']['ttl'])

  # Create NS records
  ns_rdataset = zone.find_rdataset('@', dns.rdatatype.NS, create=True)
  for ns in config['zone']['nameservers']:
    ns_rdataset.add(dns.rdtypes.ANY.NS.NS(dns.rdataclass.IN, dns.rdatatype.NS, ns['name']), config['zone']['ttl'])

  # Create A record for NS
  for ns in config['zone']['nameservers']:
    nsa_rdataset = zone.find_rdataset(ns['name'], dns.rdatatype.A, create=True)
    nsa_rdata = dns.rdtypes.IN.A.A(dns.rdataclass.IN, dns.rdatatype.A, str(ns['address']))
    nsa_rdataset.add(nsa_rdata, config['zone']['ttl'])
    

  # Add A records for all zone devices.
  for device in zone_devices:
    # Register a new A record for the device in the zone.
    hostname = f"{device['asset']}.{device['site']}"

    rdataset = zone.find_rdataset(hostname, dns.rdatatype.A, create=True)
    rdata = dns.rdtypes.IN.A.A(dns.rdataclass.IN, dns.rdatatype.A, str(device['address']))
    rdataset.add(rdata, config['zone']['ttl'])

  logging.debug(f"created zone: \n{zone.to_text()}")

  with open(os.path.join("out", "zone.db"), "w+") as f:
    # TODO: maybe use zone.to_file?
    f.write(zone.to_text())
  
  logging.info("written new zone file.")