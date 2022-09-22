import sqlite3
from works import expand_user
import re

db = "pv.db"
db = sqlite3.connect(db)

arc = "/media/fv/gdtu.sqlite3"
arc = sqlite3.connect(arc)

bl = arc.execute("select entry from archive where entry like 'pixiv%'").fetchall()
bl = (re.match('pixiv([0-9]+)', b[0]) for b in bl)
bl = (b for b in bl if b is not None)
bl = (b.group(1) for b in bl)
bl = set(bl)

outed = set()

for user in db.execute("select id from users where grab = 1").fetchall():
    user = user[0]
    for aurl in expand_user(db, user):
        wid = aurl.split('/')[-1]
        if str(wid) in bl:
            continue
        if str(wid) in outed:
            continue
        outed.add(str(wid))
        print(aurl)

users = set(u[0] for u in db.execute("select id from users where grab = 1").fetchall())

for artwork, user in db.execute("select id, user from artworks where grab = 1").fetchall():
    # Check if already downloaded
    if str(artwork) in bl:
        continue
    if str(artwork) in outed:
        continue
    outed.add(str(artwork))
    # Check if downloaded in user
    if user in users:
        continue
    print("https://pixiv.net/artworks/{}".format(artwork))
