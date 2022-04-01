# Update dns by web

import re

def save(resp, outfn="resp.html"):
    return
    with open(outfn, "wb") as f:
        f.write(resp.content)

def login(ses):
    save(ses.post(
        "https://hostingspeed.net/account/aLogIn.php",
        data={
        "new_uid": "<Username>",
        "password1": "<Password>",
        "action": "login",
        "rtype": "",
        "subaction": "managedomains",
        "cSld": "",
        "cTld": "",
        "id": "",
        "crsf_token": "",
        "crsfcheck": "0"
    }
    ))

def set_cookie_policy(ses):
    ses.cookies["cookiepolicy"] = "Cookies policy accepted"

def go_dnsmgmt_page(ses, sld, tld):
    ses.get("https://hostingspeed.net/account/DomainMain.php?cSld={sld}&cTld={tld}".format(sld=sld,tld=tld))
    save(ses.get("https://hostingspeed.net/account/dnsmgmt.php"))

def crsf_token(resp):
    return re.search("crsf_token.*?value=\"(.*?)\"",resp.text).group(1)

def check_rec_num(resp_text, rec_type, hostname):
    hostnames = re.findall("OldHostName(\d+).*?\"{hostname}\"".format(hostname=hostname), resp_text)
    rec_types = re.findall("OldRecordType(\d+).*?\"{rec_type}\"".format(rec_type=rec_type), resp_text)
    rec_nums = list(set(hostnames) & set(rec_types))
    if len(rec_nums) == 0:
        rec_num = re.search("OldAddress(\d+).*?\"\"", resp_text)
        if rec_num is None:
            # Return one higher than current ones
            rec_nums = re.findall("OldAddress(\d+).*?\"", resp_text)
            rec_nums = [int(i) for i in rec_nums]
            return max(rec_nums) + 1
        else:
            # Use first one with empty entry
            return rec_num.group(1)
    else:
        # Use first one in matching ones
        return rec_nums[0]

def update_dns_multi(ses, rec_types, hostnames, addresses):
    resp = ses.get("https://hostingspeed.net/account/dnsmgmt.php")
    entries = dict(re.findall("Old([A-Za-z]+\d+)\" value=\"(.*?)\"",resp.content.decode()))
    token = crsf_token(resp)
    payload = {
        **{
        "action": "modify",
        "FormType": "FullForm",
        "crsf_token": token,
        "crsfcheck": "1",
        "HostCount": str(int(len(entries)/4)),
        }, **entries}
    for rt, hn, ad in zip(rec_types, hostnames, addresses):
        rec_num = check_rec_num(resp.text, rt, hn)
        print(rt, hn, ad, rec_num)
        payload = {**payload, **{
            f"RecordType{rec_num}": rt,
            f"HostName{rec_num}": hn,
            f"Address{rec_num}": ad,
            f"MXPref{rec_num}": "0"
        }}
    payload = fix_dkim(payload)
    print(payload)
    save(ses.post("https://hostingspeed.net/account/dnsmgmt.php",data=payload))

def fix_dkim(payload):
    # Fix dkim
    dkim_k = [k for k in payload if payload[k] == "mail._domainkey"]
    print(dkim_k)
    dkim_k = dkim_k[0].replace("HostName","Address")
    dkim_v = payload[dkim_k]
    dkim_v = dkim_v.replace(" ","+")
    dkim_v = dkim_v.replace(";+", "; ")
    payload[dkim_k] = dkim_v
    return payload

import sys
if len(sys.argv) == 1 or len(sys.argv) % 3 != 1:
    print("python3 hsddns.py <rec_type> <hostname> <address> [<rec_type> <hostname> <address> [...]]")
    exit(-1)
rts = sys.argv[1::3]
hns = sys.argv[2::3]
ads = sys.argv[3::3]

import requests

ses = requests.Session()
set_cookie_policy(ses)
login(ses)
go_dnsmgmt_page(ses, "<YourDomainName>", "<TLD>")

update_dns_multi(ses, rts, hns, ads)

