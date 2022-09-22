import sqlite3
import json
import subprocess as sp

db = "pv.db"
db = sqlite3.connect(db)
def execute_noexcept(db, q):
    try:
        db.execute(q)
        db.commit()
    except sqlite3.OperationalError:
        pass

schema = """
create table artworks (id integer primary key, user integer, count integer, grab integer);
create index art_user_index on artworks(user);
create table users (id integer primary key, grab integer);
"""

def setup_db(db):
    for s in schema.strip().splitlines():
        execute_noexcept(db, s)
    db.commit()

setup_db(db)

def preload(rootdir):
    res = sp.check_output("find '{}' -type f | egrep -v '\.json$' | sed -E 's,^.*/([0-9]+)_.*$,\\1,' | uniq".format(rootdir), shell=True)
    res = res.decode().strip().splitlines()
    res = [int(r) for r in res]
    res = set(res)
    return res

dirs = [
        "/media/fv/gd/pixiv",
        "/media/fv/gallery-dl/pixiv"
        ]

def main():
    res = set()
    for d in dirs:
        res |= preload(d)
    db.executemany("insert or ignore into artworks (id, count, grab) values (?, 1, 1)", [[x] for x in res])
    db.commit()

if __name__ == "__main__":
    main()
