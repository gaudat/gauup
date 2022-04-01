import requests
import sys
import random

token = "<CloudflareToken>"
wanted_dn = "<YourDomainHere>"
cf_on = False

ses = requests.Session()
ses.headers["Authorization"] = "Bearer {}".format(token)
ses.headers["Content-Type"] = "application/json"

resp = ses.get("https://api.cloudflare.com/client/v4/zones")
if resp.status_code != 200:
    print("Cannot get zones. Maybe wrong token?")
    exit(-1)

zone = [z for z in resp.json()['result'] if z['name'] == wanted_dn]
if len(zone) == 0:
    print("Zone not found.")
    exit(-1)

zone = zone[0]['id']

def update_dns(dns_type, dns_name, dns_content):
    print(dns_type, dns_name, dns_content)
    # Get DNS
    resp = ses.get("https://api.cloudflare.com/client/v4/zones/{}/dns_records?type={}&name={}".format(zone, dns_type, dns_name+'.'+wanted_dn))
    
    if len(resp.json()['result']) == 0:
        print("Create new record")
        resp = ses.post("https://api.cloudflare.com/client/v4/zones/{}/dns_records".format(zone), json={"type": dns_type, "name": dns_name, "content": dns_content, "ttl": 1, "proxied": cf_on})
        record = resp.json()['result']['id']
        # We are done
        return
    else:
        record = resp.json()['result'][0]['id']
    
    # Update DNS
    resp = ses.patch("https://api.cloudflare.com/client/v4/zones/{}/dns_records/{}".format(zone, record), json={"type": dns_type, "name": dns_name, "content": dns_content, "ttl": 1})
    return

if len(sys.argv) == 1 or len(sys.argv) % 3 != 1:
    print("python3 hsddns.py <rec_type> <hostname> <address> [<rec_type> <hostname> <address> [...]]")
    exit(-1)
rts = sys.argv[1::3]
hns = sys.argv[2::3]
ads = sys.argv[3::3]

for (rt, hn, ad) in zip(rts, hns, ads):
    update_dns(rt, hn, ad)
