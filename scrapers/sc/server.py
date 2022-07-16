from wsgiref.simple_server import make_server
from app import application

port = 22000

with make_server('', port, application) as httpd:
    print("Serving on port {} ...".format(port))
    httpd.serve_forever()
