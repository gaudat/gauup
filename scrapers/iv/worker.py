import requests
import time
import logging
import pathlib
import os
import sqlite3
import bs4
import random
import argparse
import sys

parser = argparse.ArgumentParser(description='Iwara metadata scraper')
parser.add_argument('--newest', action='store_const', const=1, help='Get newest videos and exit')
parser.add_argument('--newest_limit', type=int, default=100, help='Maximum number of videos to skip')
parser.add_argument('--start', type=int, default=-1, help='Start at this page')

args = parser.parse_args(sys.argv[1:])

default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.67 Safari/537.36"
default_outdir = "."

debug = True

log = logging.getLogger("iwarascraper")

logging.basicConfig(filename="iwarascraper.log", filemode="a", encoding="utf-8", format="%(asctime)s %(levelname)s %(message)s")

if debug:
    logging.getLogger().setLevel(logging.DEBUG)
    log.setLevel(logging.DEBUG)

class ThrottledHTTPSession:
    def __init__(self, delay: float = 1.0, ua: str = None, outdir = None):
        self.ua = ua
        if self.ua is None:
            self.ua = default_ua
        self.outdir = outdir
        if self.outdir is None:
            self.outdir = default_outdir
        self.outdir: pathlib.Path = pathlib.Path(self.outdir)
        self.delay = delay
        self.last_get = 0
        self.ses = None
    def start_ses(self):
        if self.ses is not None:
            return
        self.ses = requests.Session()
        self.ses.headers["User-Agent"] = self.ua
        self.ses.cookies.set("has_js", "1")
        self.ses.cookies.set("show_adult", "1")
    def get(self, url: str, out_filename = None):
        if self.ses is None:
            self.start_ses()
        needed_delay = self.delay - (time.time() - self.last_get)
        if needed_delay > 0:
            time.sleep(needed_delay)
        if url.startswith('//'):
            url = 'https:' + url
        log.debug(f"URL: {url}")
        if out_filename is None:
            if '//' in url:
                out_filename = url.split('?')[0].split('//')[1]
            else:
                out_filename = url.split('?')[0]
        out_filename = self.outdir / out_filename
        out_file_dir = out_filename.parent
        os.makedirs(out_file_dir, exist_ok = True)
        if os.path.exists(out_filename):
            log.info(f"Exists {out_filename}")
            return
        resp = self.ses.get(url)
        self.last_get = time.time()
        log.info(f"GET {resp.status_code} {out_filename}")
        with open(out_filename, "xb") as wf:
            wf.write(resp.content)
            log.debug(f"Size: {wf.tell()}")
        return out_filename

class IwaraUrlGen:
    def __init__(self):
        self.p0_include_page_prob = 0.1
        self.keys = {"language": ["en", "zh-hans", "de", "ja"], "sort": ["date"]}
        self.url_base = "https://ecchi.iwara.tv/videos?"
    def get(self, page):
        keys = {}
        if page == 0:
            if random.random() < self.p0_include_page_prob:
                keys["page"] = 0
        else:
            keys["page"] = page
        if random.random() < 0.5:
            keys["language"] = random.choice(self.keys["language"])
        if random.random() < 0.5:
            keys["sort"] = "date"
        ki = list(keys.items())
        random.shuffle(ki)
        return self.url_base + '&'.join(f'{a}={b}' for a, b in ki)
class IwaraPaginator:
    def __init__(self, ses: ThrottledHTTPSession, recover = True):
        self.out_dir = "_videopages"
        self.out_fn_template = "{pagenum}_{timestamp}"
        self.next_page = 0
        if recover:
            self.next_page = self.recover_progress()
        self.ses = ses
        self.endpoint0 = "https://ecchi.iwara.tv/videos?language=en"
        self.endpoint = "https://ecchi.iwara.tv/videos?language=en&sort=date&page={}"
        self.urlgen = IwaraUrlGen()
    def recover_progress(self):
        if not os.path.exists(self.out_dir):
            os.mkdir(self.out_dir)
            return 0
        fs = os.listdir(self.out_dir)
        fs = set(int(f.split('_')[0]) for f in fs)
        ret = 0
        while True:
            if ret not in fs:
                return ret
            ret += 1
    def get_newest(self):
        return self.get_page(0)
    def get_next(self):
        ret = self.get_page(self.next_page)
        self.next_page += 1
        return ret
    def get_page(self, page_num):
        if page_num == 0:
            url = self.endpoint0
        else:
            url = self.endpoint.format(page_num)
        url = self.urlgen.get(page_num)
        out_fn = self.out_fn_template.format(pagenum = page_num, timestamp = int(time.time()))
        ret = self.ses.get(url, self.out_dir + '/' + out_fn)
        if ret is None:
            log.warning(f"Bug: File for page {page_num} already exists")
        if ret == "":
            return b''
        with open(ret, "rb") as rf:
            return rf.read()

class IwaraParser:
    def __init__(self):
        pass
    def parse_page(self, page: bytes):
        soup = bs4.BeautifulSoup(page)
        
        tiles = soup.select('div[id^="node-"]')
        for t in tiles:
            vid = {}
            img_el = t.find('img')
            if img_el is not None:
                vid["thumb"] = img_el['src']
                try:
                    vid["title"] = img_el['title']
                except Exception:
                    vid["title"] = None
                try:
                    vid["num"] = int(vid["thumb"].split('/')[-2])
                except Exception:
                    vid["num"] = None
            else:
                vid["thumb"] = None
                vid["title"] = None
                vid["num"] = None
            if vid["title"] == None:
                vid["title"] = t.select('h3 > a')[0].contents[0].strip()
            vid["atime"] = time.time()
            vid["url"] = t.select('h3 > a')[0]['href']
            if '?' in vid["url"]:
                vid["url"] = vid["url"].split('?')[0]
            vid["user"] = t.select('a.username')[0].contents[0]
            views_el = t.select('div.left-icon.likes-icon')
            if len(views_el) > 0:
                vid["views"] = views_el[0].get_text().strip()
            else:
                vid["views"] = 0
            likes_el = t.select('div.right-icon.likes-icon')
            if len(likes_el) > 0:
                vid["likes"] = likes_el[0].get_text().strip()
            else:
                vid["likes"] = 0
            print(vid)
            yield vid

class IwaraDatabase:
    def __init__(self, db_fn = None):
        if db_fn is None:
            db_fn = "iwara.db"
        self.db = sqlite3.connect(db_fn)
        self.db.execute("pragma synchronous = 1")
        self.db.execute("create table if not exists videos (num text, url text, title text, user text, atime text, views text, likes text)")
        self.db.execute("create unique index if not exists videos_url_index on videos(url)")
        self.db.commit()
    def push(self, vid):
        try:
            self.db.execute("insert into videos (num, url, title, user, atime, views, likes) values (?, ?, ?, ?, ?, ?, ?)", 
            (vid["num"], vid["url"], vid["title"], vid["user"], vid["atime"], vid["views"], vid["likes"]))
        except sqlite3.IntegrityError:
            return False
        self.db.commit()
        return True
    def delete(self, url):
        self.db.execute("delete from videos where url = (?)", (url,))

class IwaraPipeline:
    def __init__(self):
        self.ses = ThrottledHTTPSession()
        self.pages = IwaraPaginator(self.ses)
        self.parser = IwaraParser()
        self.db = IwaraDatabase()
        self.last_page_urls = []
        self.need_fetch_newest = True
        if args.newest is not None:
            self.pages.next_page = 0
            if args.start > 0:
                self.pages.next_page = args.start
            self.need_fetch_newest = False
            self.repeated_newest_videos = 0
    def parse(self, page, update_last_page = True):
        tiles = list(self.parser.parse_page(page))
        if len(tiles) == 0:
            raise RuntimeError("Parsed 0 videos from result page!")
        this_page_urls = [v["url"] for v in tiles]
        if len(set(self.last_page_urls) & set(this_page_urls)) > 0:
            # New items
            self.need_fetch_newest = True
        new_count = 0
        for vid in tiles:
            new_vid = self.db.push(vid)
            if new_vid:
                if vid["thumb"] is not None:
                    out_fn = vid["url"].split('/')[-1] + '.jpg'
                    shard = out_fn[:2] + '/' + out_fn[2:4]
                    self.ses.get(vid["thumb"], shard + '/' + out_fn)
                log.info(f'Add {vid["title"]} {vid["url"]}')
                new_count += 1
        if update_last_page:
            self.last_page_urls = this_page_urls
        return new_count
    def parse_with_retry(self):
        while True:
            try:
                page = self.pages.get_next()
                new_count = self.parse(page)
                return new_count
            except Exception as e:
                log.exception(f"Failed to parse page")
                log.info(f"Will retry later")
                self.pages.next_page -= 1
                time.sleep(random.random() * 60 + 60)
    def run(self):
        log.info(f"Will get page {self.pages.next_page}")
        new_count = self.parse_with_retry()
        if args.newest is not None:
            log.info(f"Added {new_count} videos from newest page")
            self.repeated_newest_videos += 36 - new_count
            if self.repeated_newest_videos > args.newest_limit:
                log.info("Finished getting newest videos")
                args.newest = None
                if args.start > 0:
                    self.pages.next_page = args.start
                else:
                    return False
            return True
        log.info(f"Added {new_count} videos from page {self.pages.next_page}")
        if self.need_fetch_newest:
            new_count = self.parse_with_retry()
            log.info(f"Added {new_count} videos from newest page")
            self.need_fetch_newest = False
        return True
    
if __name__ == "__main__":
    ip = IwaraPipeline()
    ret = True
    while ret:
        ret = ip.run()
        time.sleep(random.random() * 14 + 1)
