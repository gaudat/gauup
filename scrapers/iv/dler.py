import sqlite3
import re
import subprocess as sp
import time
import random

delay_min = 30
delay_max = 120

db = sqlite3.connect("iwara.db")
db.execute("pragma synchronous = 0")
db.execute("pragma journal_mode = wal")

def db_res_gen(stmt):
    res = stmt.fetchone()
    while res is not None:
        yield res
        res = stmt.fetchone()

def normalize_vid_count(db, colname):
    instr = db.execute(f"select rowid, {colname} from videos")
    norm_count = 0
    for rowid, views in db_res_gen(instr):
        if re.match('^[0-9]+$', views):
            # Do nothing
            pass
        elif re.match('^[0-9.]+k$', views):
            # Convert k to one
            views_new = int(float(views[:-1]) * 1000)
            print(f"{views} -> {views_new}")
            db.execute(f"update videos set {colname} = (?) where rowid = (?)", (views_new, rowid))
            norm_count += 1
        else:
            # Unknown
            print("Unknown views / likes: {views}")
    db.commit()
    print(f"Normalized {norm_count} {colname} fields")

def update_backlog_table(db):
    db.execute("create table if not exists backlog (num integer, url text, atime real, views integer, likes integer, state text)")
    db.execute("create unique index if not exists backlog_url_index on backlog(url)")
    db.execute("create index if not exists backlog_views_index on backlog(views)")
    db.execute("create index if not exists backlog_likes_index on backlog(likes)")
    db.execute("create index if not exists backlog_state_index on backlog(state)")
    db.commit()
    rows = db.execute("select sum(1) from backlog").fetchone()
    if rows[0] == 0 or rows[0] is None:
        print("Backlog table is empty. Copying from videos table")
        populate_backlog_table(db)

def populate_backlog_table(db):
    db.execute("insert into backlog (num, url, atime, views, likes, state) select num, url, atime, views, likes, 0 from videos")
    db.commit()

def backlog_length(db):
    return db.execute("select count(1) from backlog where state = 0").fetchone()[0]

def backlog_item(db):
    url = db.execute("select url from backlog where state = 0 order by views, likes desc").fetchone()[0]
    if url is None:
        print("No next item")
        return
    # Fetch title
    title = db.execute("select title from videos where url = (?)", (url,)).fetchone()
    if title is None:
        print(f"Fixme: url in backlog is not in videos. url = {url}")
    print(f"Next item: {title[0]} {url}")
    return url

def done_item(db, url):
    print(f"Done {url}")
    db.execute("update backlog set state = 1 where url = (?)", (url,))
    db.commit()

def fail_item(db, url):
    print(f"Fail {url}")
    db.execute("update backlog set state = 2 where url = (?)", (url,))
    db.commit()

def process_item(db, url):
    # Chunk prefix by first 2 character of url
    prefix = url.split('/')[-1][:2]
    # Add host
    rurl = f"https://ecchi.iwara.tv{url}"
    print(f"url: {rurl}")
    if prefix is not None:
        sp.check_call(["mkdir", "-p", prefix])
    try:
        res = speed_check(["yt-dlp", "-f", "best", "--write-description", "--write-info-json", "--write-subs","--sub-langs","all","--", rurl], cwd=prefix)
        if not res:
            fail_item(db, url)
            return False
    except sp.CalledProcessError as e:
        fail_item(db, url)
        return False
    done_item(db, url)
    return True

def speed_check(*args, **kwargs):
    # Wraps sp.run
    kwargs["stdout"] = sp.PIPE
    p = sp.Popen(*args, **kwargs)
    line = b""
    deadline = random.random() * 20 + 20
    slow_thres = 100000
    slow_start = None
    while p.poll() is None:
        ch = p.stdout.read(1)
        line += ch
        if len(line) > 0 and line[-1] in b"\r\n":
            # line = ... at [speed]KiB/s ...
            line = line.decode()
            m = re.search(" at +([0-9.]+)(.).*?/s ", line)
            if m is not None:
                print("\rSpeed",m.group(1),m.group(2),end="")
                s = float(m.group(1))
                if m.group(2) == "K":
                    s *= 1024
                elif m.group(2) == "M":
                    s *= 1024
                    s *= 1024
                if s < slow_thres and slow_start is None:
                    print("Getting slow. Waiting {:.2f} seconds before retrying.".format(deadline))
                    slow_start = time.time()
                if s > slow_thres and slow_start is not None:
                    # Reset timer
                    print("Speed is back to normal.")
                    slow_start = None
                if slow_start is not None and time.time() - slow_start > deadline:
                    print("Retrying due to download being too slow.")
                    p.terminate()
                    p.communicate()
                    return False
            else:
                print(line, end="")
            line = b""
    print("")
    p.communicate()
    return True

normalize_vid_count(db, "views")
normalize_vid_count(db, "likes")
update_backlog_table(db)
print("backlog_item ret " + backlog_item(db))

def loop():
    print("Backlog length: {}".format(backlog_length(db)))
    bi = backlog_item(db)
    return process_item(db, bi)

while True:
    if backlog_length(db) <= 0:
        exit()
    good =loop()
    delay_dur = (random.random()*(delay_max - delay_min) + delay_min)
    if not good:
        delay_dur = 5
    print("Sleeping for {:.2f}s".format(delay_dur))
    time.sleep(delay_dur)
