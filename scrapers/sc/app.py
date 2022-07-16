import sqlite3
import json
import time
import re

db = "sc.db"
db = sqlite3.connect(db)
def execute_noexcept(db, q):
    try:
        db.execute(q)
        db.commit()
    except sqlite3.OperationalError:
        pass

schema = """
pragma journal_mode = 'wal';
pragma synchronous = 1;
create table urls (url text not null, rank integer, ts real, state integer);
create index url_index on urls(url);
create index ts_index on urls(ts);
create table queries (url text not null, ts real);
create table sets (url text not null, rank integer, ts real, state integer);
create unique index sets_index on sets(url);
create table songs (url text not null, rank integer, ts real, state integer);
create unique index songs_index on sets(url);
create table users (url text not null, rank integer, ts real, state integer);
create unique index users_index on sets(url);
"""

def setup_db(db):
    for s in schema.strip().splitlines():
        execute_noexcept(db, s)
    db.commit()

def migrate_db(db):
    old = db.execute("select url, rank from urls order by ts desc").fetchall()
    for url, rank in old:
        route = url.split('?')[0]
        route = f'/{rank}/{route}'.split('/')
        route = [r for r in route if len(r) > 0]
        if '?' not in route:
            query = {}
        else:
            query = url.split('?')[1]
            query = query.split('&')
            query = dict(((a, c) for a, b, c in q.partition('=')) for q in query)

        print("Migrate", route, query)
        try:
            if route[0] == 'q':
                resp = read_app(route, query)
            else:
                resp = write_app(route, query)
            db.execute("delete from urls where url = (?)", (url,))
            db.commit()
        except Exception as e:
            print(f'{type(e)}: {e}')
            pass

def write_app(route, query):
    rank = int(route[0])
    route = route[1:]


    if len(route) == 1:
        table = 'users'
    elif len(route) == 2:
        if route[1] in ('popular-tracks', 'tracks', 'albums', 'sets', 'reposts'):
            # User page
            route = route[0:1]
            table = 'users'
        else:
            table = 'songs'
    elif len(route) == 3:
        if route[1] != 'sets':
            raise RuntimeError('Bad playlist url format')
        table = 'sets'
    else:
        raise RuntimeError('Unknown url format')

    url = "/" + "/".join(route)
    print(f'Insert {table} {url} {rank}')
    res = db.execute(f"insert into {table} values (?, ?, ?, ?)", (url, rank, time.time(), 0))
    db.commit()

    resp = {"ok": 1}
    return resp

def read_app(route, query):
    if 'in' in query:
        set_name = '/' + query['in']
        res = db.execute("select rank from sets where url = (?) order by ts desc limit 1", (set_name,)).fetchone()
        if res is not None:
            print(f'Shortcut inset {query} {res[0]}')
            return {"rank": res[0]}

    route = route[1:]

    if len(route) == 1:
        table = 'users'
    elif len(route) == 2:
        if route in ('popular-tracks', 'tracks', 'albums', 'sets', 'reposts'):
            # User page
            route = route[0:1]
            table = 'users'
        else:
            table = 'songs'
            res = db.execute(f"select rank from users where url = (?) order by ts desc limit 1", (f'/{route[0]}',)).fetchone()
            if res is not None:
                print(f'Shortcut whole user {route[0]} {res[0]}')
                return {"rank": res[0]}
    elif len(route) == 3:
        if route[1] != 'sets':
            raise RuntimeError('Bad playlist url format')
        table = 'sets'
    else:
        raise RuntimeError('Unknown url format')

    url = "/" + "/".join(route)

    res = db.execute(f"select rank from {table} where url = (?) order by ts desc limit 1", (url,)).fetchone()
    if res is None:
        print(f"Empty Read {table} {url}")
        return {"rank": 0}
    else:
        print(f"{res[0]} Read {table} {url}")
        return {"rank": res[0]}

def application(env, start_response):
    db.execute(f"insert into queries values (?, ?)", (f'/{env["PATH_INFO"]}?{env["QUERY_STRING"]}', time.time()))
    db.commit()
    route = env['PATH_INFO'].split('/')
    route = [r for r in route if len(r) > 0]
    query = env['QUERY_STRING']
    query = query.split('&')
    query = [q.partition('=') for q in query]
    query = [(q[0], q[2]) for q in query]
    query = dict(query)
    if len(route) < 2:
        # Bad request
        start_response("400 Bad Request", [("Content-Type", "application/json"), ('Access-Control-Allow-Origin', '*')])
        return [b'']

    try:
        if route[0] == 'q':
            resp = read_app(route, query)
        else:
            resp = write_app(route, query)
    except Exception as e:
        print(f'{type(e)}: {e}')
        start_response("400 Bad Request", [("Content-Type", "application/json"), ('Access-Control-Allow-Origin', '*')])
        return [b'']

    start_response("200 OK", [("Content-Type", "application/json"), ('Access-Control-Allow-Origin', '*')])
    return [json.dumps(resp).encode()]

setup_db(db)
migrate_db(db)

