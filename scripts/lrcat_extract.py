import sqlite3
import os
import sys

db = sqlite3.connect(sys.argv[1])
coll = sys.argv[2]

coll_id = db.execute('select id_local from AgLibraryCollection where name = (?)', (coll,)).fetchone()
assert coll_id is not None

match_images = db.execute("with a as (select image from AgLibraryCollectionImage where collection = (?)), b as (select rootFile from Adobe_images inner join a on Adobe_images.id_local = a.image)    select folder, baseName || '.' || extension from AgLibraryFile inner join b on AgLibraryFile.id_local = b.rootFile", coll_id).fetchall()
print("Image count: {}".format(len(match_images)))
folder_map = db.execute("select f.id_local, r.absolutePath, f.pathFromRoot from AgLibraryRootFolder r, AgLibraryFolder f where f.rootFolder = r.id_local and f.id_local in (select distinct folder from AgLibraryFile)").fetchall()
folder_map = dict((f[0], f[1] + f[2] ) for f in folder_map)

match_images = [folder_map[i[0]] + i[1] for i in match_images]

for i in match_images:
    print(i)
