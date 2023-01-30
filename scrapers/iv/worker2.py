import requests
import time
import logging
import pathlib
import os
import sqlite3
import bs4
import random
import urllib
import re

default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.67 Safari/537.36"
default_outdir = "."

debug = True

log = logging.getLogger("iv")

logging.basicConfig(filename="ivscraper.log", filemode="a", encoding="utf-8", format="%(asctime)s %(levelname)s %(message)s")

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
        try:
            resp = self.ses.get(url, timeout=10)
        except TimeoutError:
            with open(out_filename, 'xb'):
                pass
            log.info("Timed out getting a response")
            return
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

        
class SPaginator:
    def __init__(self, ses: ThrottledHTTPSession):
        self.ses = ses
        self.next_page = 1
        self.parser = SPageParser()
        self.urlgen = IwaraUrlGen()
    def recover_progress(self, last_fetched_page):
        page = self.get_page(1)
        estimated_page = (page['total_ids'] - last_estimated_id) / page['ids_per_page']
        estimated_page = int(estimated_page) + 1 # Round down, 1 based paging
        self.next_page = estimated_page
    def get_newest(self):
        return self.get_page(1)
    def get_next(self):
        ret = self.get_page(self.next_page)
        self.next_page += 1
        return ret
    def get_page(self, page_num):
        # Better not cache each page
        log.info(f"Get page {page_num}")
        url = self.urlgen.get(page_num)
        now = int(time.time())
        page_fn = self.ses.get(url, f"_pages/{page_num}_{now}.html")
        with open(page_fn, 'rb') as rf:
            page = rf.read()
        return self.parser.parse(page)

class SPageParser:
    def __init__(self):
        pass
    def parse_each_project(self, each_project_div, estimated_id):
        url = each_project_div.select_one('a.project-link')['href']
        if not url.startswith('https://') and not url.startswith('//'):
            # It was relative url
            url = 'https://oshwhub.com' + url
        else:
            raise RuntimeError("Project url format changed")
        cover_pic = each_project_div.select_one('div.cover-desc img')['src']
        if cover_pic.startswith('//'):
            cover_pic = 'https:' + cover_pic
        elif cover_pic.startswith('/'):
            cover_pic = 'https://oshwhub.com' + cover_pic
        elif cover_pic.startswith('https://'):
            pass
        else:
            raise RuntimeError("Cover pic url format changed")
        title = each_project_div.select_one('div.title-layer')['title']
        cover_description = each_project_div.select_one('div.desc p.back-up').text.strip()
        return {
            "url": url,
            "estimated_id": estimated_id,
            "cover_pic": cover_pic,
            "title": title,
            "cover_description": cover_description
        }

    def parse(self, page_html: bytes):
        soup = bs4.BeautifulSoup(page_html)
        page_url = soup.select_one('div.not-login-wrap a:first-child')['href']
        page_url = urllib.parse.parse_qs(page_url.split('?')[1])['from'][0]
        page_num = int(urllib.parse.parse_qs(page_url.split('?')[1])['page'][0])
        pagination_div = soup.select_one('div.component-pagination')
        total_ids = int(pagination_div['data-page-total'])
        ids_per_page = int(pagination_div['data-page-per'])
        estimated_id_start = total_ids - ((page_num - 1) * ids_per_page)
        projects = [self.parse_each_project(el, eid) for el, eid in zip(soup.select('div.each-project'), range(estimated_id_start, -1, -1))]
        return {
            "page_url": page_url,
            "page_num": page_num,
            "total_ids": total_ids,
            "ids_per_page": ids_per_page,
            "projects": projects
        }


class SDatabase:
    def __init__(self, db_fn = None):
        if db_fn is None:
            db_fn = "oshwhub.db"
        self.db = sqlite3.connect(db_fn)
        self.db.execute("pragma synchronous = 1")
        self.db.execute("create table if not exists projects (url text, estimated_id integer, title text, cover_description text, state integer)")
        # State 0 = Seen, 1 = Expanded
        self.db.execute("create unique index if not exists projects_url_index on projects (url)")
        self.db.execute("create index if not exists projects_state_index on projects (state)")
        self.db.commit()
    def push_cover(self, project_cover):
        try:
            self.db.execute("insert into projects (url, estimated_id, title, cover_description, state) values (?, ?, ?, ?, ?)",
            (project_cover['url'], project_cover['estimated_id'], project_cover['title'], project_cover['cover_description'], 0))
            self.db.commit()
        except sqlite3.IntegrityError:
            return False
        return True
    def delete_project(self, proj_url):
        try:
            self.db.execute("delete from projects where url = (?)", (proj_url,))
            self.db.commit()
        except sqlite3.IntegrityError:
            return False
        return True
    def set_project_expanded(self, proj_url):
        try:
            self.db.execute("update projects set state = 1 where url = (?)", (proj_url,))
            self.db.commit()
        except sqlite3.IntegrityError:
            return False
        return True
    def get_cover_project(self):
        proj = self.db.execute('select url from projects where state = 0 order by random() limit 1').fetchone()
        if proj is None: # Can be none if no rows
            return None
        proj = proj[0]
        return proj
    def get_project_by_eid(self, eid):
        proj = self.db.execute('select url from projects where estimated_id = (?)', (eid,)).fetchone()
        if proj is None: # Can be none if no rows
            return None
        proj = proj[0]
        return proj
    def get_oldest_project_eid(self):
        eid = self.db.execute('select min(estimated_id) from projects').fetchone()
        if eid is None: # Can be none if no rows
            return None
        eid = eid[0]
        return eid 

class SPipeline:
    def __init__(self):
        self.ses = ThrottledHTTPSession()
        self.pages = SPaginator(self.ses)
        self.parser = SPageParser()
        self.db = SDatabase()
        self.finished = False

    def fetch_thumbnail(self, proj):
        urlcs = proj['url'].split('/')
        uploader = urlcs[-2]
        projname = urlcs[-1]
        outfn = f'{uploader}/{projname}_thumb'
        if not os.path.exists(outfn):
            self.ses.get(proj['cover_pic'], outfn)

    def fetch_newest_project_covers(self, limit=99999):
        self.finished = False
        prev_next_page = self.pages.next_page
        log.info(f"Getting newest projects. Prev paginator next_page: {prev_next_page}")
        self.pages.next_page = 1
        has_new_proj = True
        while has_new_proj:
            projs = self.pages.get_next()
            added_count = 0
            for proj in projs['projects']:
                self.fetch_thumbnail(proj)
                is_new_proj = self.db.push_cover(proj)
                if is_new_proj:
                    added_count += 1
                    limit -= 1
                    if limit <= 0:
                        # Escape
                        has_new_proj = False
                has_new_proj = has_new_proj and is_new_proj
            log.info(f"Added {added_count}/{projs['ids_per_page']} project covers")
        if limit <= 0:
            log.info(f"Exiting early due to too many new projects. Last eid: {proj['estimated_id']}")
        else:
            log.info("Finish getting newest projects")
        self.pages.next_page = prev_next_page
    
    def fetch_older_project_covers(self, limit=99999):
        self.finished = False
        prev_next_page = self.pages.next_page
        log.info(f"Getting older projects. Prev paginator next_page: {prev_next_page}")
        opeid = self.db.get_oldest_project_eid()
        if opeid == 1 or opeid == '1':
            log.info("All old projects fetched.")
            return
        if opeid is None:
            log.info("No projects in database yet. Fetching newest projects instead.")
            return self.fetch_newest_project_covers(limit)
        self.pages.recover_progress(opeid)
        has_new_proj = True
        while has_new_proj:
            projs = self.pages.get_next()
            added_count = 0
            if len(projs['projects']) == 0:
                log.info("No more older projects to fetch")
                break
            for proj in projs['projects']:
                self.fetch_thumbnail(proj)
                is_new_proj = self.db.push_cover(proj)
                if is_new_proj:
                    added_count += 1
                    limit -= 1
                    if limit <= 0:
                        # Escape
                        has_new_proj = False
            log.info(f"Added {added_count}/{projs['ids_per_page']} project covers")
        if limit <= 0:
            log.info(f"Exiting early due to too many projects. Last eid: {proj['estimated_id']}")
        else:
            log.info("Finish getting oldest projects")
        self.pages.next_page = prev_next_page

    def normalize_url(self, url):
        if url.startswith('//'):
            return 'https:' + url
        elif url.startswith('/'):
            return 'https://oshwhub.com' + url
        else:
            return url

    def proj_ses_get(self, proj_url, get_url, gu_fn = None):
        urlcs = proj_url.split('/')
        uploader = urlcs[-2]
        projname = urlcs[-1]
        if gu_fn is None:
            gu_fn = get_url.split('/')[-1]
        outfn = f'{uploader}/{projname}/{gu_fn}'
        if not os.path.exists(outfn):
            try:
                self.ses.get(get_url, outfn)
            except Exception:
                log.exception("Exception in url")

    def expand_one_project(self, proj_eid = None):
        if proj_eid is None:
            proj_url = self.db.get_cover_project()
            if proj_url is None:
                self.finished = True
                log.info("All projects in database are expanded")
                return
        else:
            proj_url = self.db.get_project_by_eid(proj_eid)
        if proj_url is None:
            raise RuntimeError("Project EID not found in database")
        log.info(f"Project url: {proj_url}")
        urlcs = proj_url.split('/')
        uploader = urlcs[-2]
        projname = urlcs[-1]
        phfn = f"{uploader}/{projname}/project.html"
        if not os.path.exists(phfn):
            self.ses.get(proj_url, phfn)
        with open(phfn, 'rb') as rf:
            soup = bs4.BeautifulSoup(rf.read())
        if soup.select_one('title').text.strip() == 'error':
            log.info(f"Project is error. Deleting this item")
            self.db.delete_project(proj_url)
            return
        cover = self.normalize_url(soup.select_one('div.img-cover img')['src'])
        self.proj_ses_get(proj_url, cover, 'cover')
        # Get all media in P1
        md = soup.select_one('div#P1').text
        md_media = re.findall('\]\(([^\)]+)\)', md)
        videos = [v['src'] for v in soup.select('div.project-detail-content video')]
        eeimg = [i['src'] for i in soup.select('div.document-img-wrap img')]
        all_media = md_media + videos + eeimg
        for murl in all_media:
            if '/' not in murl:
                # Probably bad parse
                log.info(f"Skipped probably bad url: {murl}")
                continue
            nurl = self.normalize_url(murl)
            self.proj_ses_get(proj_url, nurl)
        self.db.set_project_expanded(proj_url)
        log.info(f"Expanded {proj_url}")
    

        
    
if __name__ == "__main__":
    pl = SPipeline()
    pl.fetch_older_project_covers()
    while True:
        roll = random.random()
        try:
            if roll < 0.02:
                pl.fetch_newest_project_covers()
            elif 0.02 <= roll < 0.1:
                pl.fetch_older_project_covers()
            else:
                pl.expand_one_project()
        except Exception:
            log.exception("Exception in main")
        if not pl.finished:
            time.sleep(random.random() * 5 + 5)
        else:
            time.sleep(3600)
