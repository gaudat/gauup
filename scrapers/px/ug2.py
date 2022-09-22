from dataclasses import dataclass
from typing import BinaryIO, Generator, Iterable, Union, Optional, Mapping
from zipfile import ZipFile
import PIL.Image
import PIL.ImageFile
import os
import io
from abc import ABC, abstractmethod
import subprocess
from dataclasses import dataclass
import json
import tempfile
import unittest

THUMBNAIL_SIZE = (250, 250)

def chunked_read(fp: BinaryIO, chunk_size: int = 65536) -> Generator[bytes, None, None]:
    while True:
        chunk = fp.read(chunk_size)
        if len(chunk) == 0:
            break
        yield chunk
    fp.close()

@dataclass
class HTTPHeaders:
    content_type: str
    content_length: Optional[int]
    last_modified: Union[str, int, float]

@dataclass
class HTTPResponse:
    headers: HTTPHeaders
    payload: Union[bytes, Generator[bytes, None, None], PIL.Image.Image]

class MediaFile(ABC):
    filepath: str

class ImageFile(MediaFile):

    def __init__(self, filepath: str):
        self.filepath = filepath    
        im: PIL.ImageFile.ImageFile = PIL.Image.open(self.filepath)
        self.content_type: str = im.get_format_mimetype()
        self.stat_res = os.stat(self.filepath)

    def get_original(self) -> HTTPResponse:

        with open(self.filepath, "rb") as rf:
            return HTTPResponse(
                HTTPHeaders(
                    self.content_type, self.stat_res.st_size, self.stat_res.st_mtime
                ), chunked_read(rf)
            )
        
    def get_thumbnail(self, size: int = THUMBNAIL_SIZE) -> HTTPResponse:
        im = PIL.Image.open(self.filepath)
        im.thumbnail(size, resample=PIL.Image.LANCZOS)
        tn = io.BytesIO()
        im.save(tn, "JPEG")
        tn = tn.getvalue()
        return HTTPResponse(
            HTTPHeaders(
                "image/jpeg", len(tn), self.stat_res.st_mtime
            ), tn
        )

class UgoiraFile(MediaFile):
    def __init__(self, filepath: str):
        assert filepath.endswith('.zip')
        assert os.path.exists(filepath)
        self.filepath = filepath
        self.jsonpath = filepath + '.json'
        assert os.path.exists(self.jsonpath)
        with open(self.jsonpath) as rf:
            self.json = json.load(rf)
        assert self.json["category"] == "pixiv"
        assert self.json["extension"] == "zip"
        assert type(self.json["frames"]) == list
        # FIXME add JSON schema verification in "frames"
    def _get_frames(self, frame_nums: Iterable[int]):
        with ZipFile(self.filepath) as zf:
            for num in frame_nums:
                frame_fn = self.json["frames"][num]["file"]
                with zf.open(frame_fn) as ff:
                    im = PIL.Image.open(ff)
                    im.load()
                    yield im
    def get_frame(self, frame_num: int):
        return next(self._get_frames((frame_num,)))
    def get_thumbnail(self, size: int = THUMBNAIL_SIZE):
        im = self.get_frame(0)
        im.thumbnail(size, resample=PIL.Image.LANCZOS)
        return im
    def get_video(self):
        with ZipFile(self.filepath) as zf, tempfile.TemporaryDirectory() as tmpd:
            for frame in self.json["frames"]:
                frame_fn = frame["file"]
                with zf.open(frame_fn) as ff, open(tmpd + "/" + frame_fn, "wb") as tf:
                    tf.write(ff.read())
            # Generate concat file
            with open(tmpd + "/concat.txt", "w") as cf:
                cf.write("ffconcat version 1.0\n")
                for frame in self.json["frames"]:
                    cf.write("file {}\n".format(frame["file"]))
                    cf.write("duration {}\n".format(frame["delay"] / 1000))
            cmdline = "ffmpeg -i concat.txt -c:v vp8 -f webm -"
            cmdline = cmdline.split(' ')
            proc = subprocess.Popen(cmdline, stdout=subprocess.PIPE, cwd=tmpd)
            while proc.poll() is None:
                yield proc.stdout.read(65536)
            yield proc.stdout.read()


# Formats: jpg, png, mp4, zip (ugoira)

# Endpoint: /image/{size int | orig}/{path}

TEST_FILE = "/media/fv/gallery-dl/ugoira/10694230 sakusya4/84957694_p0.zip"

class UgfTest(unittest.TestCase):
    def test_init(self):
        ug = UgoiraFile(TEST_FILE)
        self.assertTrue(True)
    def test_get_thumbnail(self):
        ug = UgoiraFile(TEST_FILE)
        tn = ug.get_thumbnail()
        with open("test_tn.jpg", "wb") as tf:
            tn.save(tf, "JPEG")
        self.assertTrue(True)
    def test_get_video(self):
        ug = UgoiraFile(TEST_FILE)
        vid = ug.get_video()
        with open("test_vid.webm", "wb") as tf:
            for chunk in vid:
                tf.write(chunk)
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
