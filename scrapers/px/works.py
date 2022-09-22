import gallery_dl.extractor.pixiv as P
import time

class FlatUser:
    def __init__(self, url: str):
        self.e = P.PixivUserExtractor.from_url(url)
        self.works = None
    def fetch(self):
        # Genearator
        if self.e is None:
            return
        if self.works is not None:
            for w in self.works:
                yield w
        self.works = []
        gen = self.e.works()
        for w in gen:
            self.works.append(w)
            yield w

max_age = 0 #86400*7

def expand_user(db, user_id: int):
    res = db.execute("select mtime from users where id = (?)", (user_id,)).fetchone()
    if res is None:
        raise RuntimeError("user_id {} not in users table".format(user_id))
    res = res[0]
    if res is not None and float(res) < time.time() - max_age:
        # Expire
        res = None
    if res is None:
        # first grab
        works = FlatUser("https://pixiv.net/users/{}".format(user_id))
        for w in works.fetch():
            wid = w["id"]
            db.execute("insert or ignore into artworks (id, user, count, grab) values (?, ?, 0, 1)", (wid, user_id))
            db.commit()
            yield "https://pixiv.net/artworks/{}".format(wid)
        db.execute("update users set mtime = (?) where id = (?)", (time.time(), user_id))
        db.commit()
    if res is not None:
        # Read from cached items
        works = db.execute("select id from artworks where user = (?)", (user_id,)).fetchall()
        for w in works:
            yield "https://pixiv.net/artworks/{}".format(w[0])
