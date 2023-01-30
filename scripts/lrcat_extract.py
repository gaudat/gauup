import sqlite3
import os
import sys

db = sqlite3.connect(sys.argv[1])

pic_count = db.execute('select count(1) from Adobe_images;').fetchone()[0]
print("Image count: {}".format(pic_count))

colors = db.execute('select distinct colorLabels from Adobe_images;').fetchall()
colors = [c[0] for c in colors]
print("Colors: {}".format(colors))

if len(sys.argv) >= 3:
    selected_color = sys.argv[2].lower()
else:
    exit(0)

# Match prefix
match_colors = [c for c in colors if c.lower().startswith(selected_color.lower())]
if len(match_colors) > 1:
    print("Error - input match more than one color ({})".format(match_colors))
    exit(-1)
if len(match_colors) == 0:
    print("Error - input does not match any color")
    exit(-1)

match_images = db.execute("select folder, baseName || '.' || extension from AgLibraryFile where id_local in (select rootFile from Adobe_images where colorLabels = (?));", match_colors).fetchall()
folder_map = db.execute("select f.id_local, r.absolutePath, f.pathFromRoot from AgLibraryRootFolder r, AgLibraryFolder f where f.rootFolder = r.id_local and f.id_local in (select distinct folder from AgLibraryFile)").fetchall()
folder_map = dict((f[0], f[1] + f[2] ) for f in folder_map)

match_images = [folder_map[i[0]] + i[1] for i in match_images]

for i in match_images:
    print(i)
