import hashlib
import os
import urllib2
import time
import logging
from util import GenericObject

BUFFER_SIZE = 1024 * 50


class Chunk(GenericObject):
    filepath = ""
    timestamp = ""
    buffer = ""

    def __init__(self, timestamp, path, cm):
        self.timestamp = timestamp
        self.filepath = path + str(timestamp)
        self.cm = cm

    def write(self, payload):
        self.logger.debug('Writing chunk %s' % str(self.timestamp))
        with open(self.filepath, "wb") as f:
            f.write(payload)

    def read(self):
        self.logger.debug('Reading chunk %s' % str(self.timestamp))
        with open(self.filepath, "rb") as f:
            return f.read()

    def delete(self):
        try:
            self.logger.debug('Deleting chunk %s' % str(self.timestamp))
            os.remove(self.filepath)
        except Exception as e:
            self.logger.critical("Can't find and remove chunk %s" % self.filepath)
            self.logger.critical(e)

    @property
    def seconds(self):
        return float(self.cm.next(self).timestamp) - float(self.timestamp)


class ChunkManager(GenericObject):
    def __init__(self, path, url, buffer, shift):
        self.buffer = buffer
        self.shift = shift

        # TODO: validation buffer > shift

        self.path = path + hashlib.md5(url).hexdigest() + "/"
        if not os.path.exists(self.path):
            os.mkdir(self.path)

    def find(self):
        self.logger.debug("Find chunk with offset %s" % str(self.shift))
        t = time.time() - self.shift
        files = sorted(os.listdir(self.path))

        for file in files:
            if t < float(file):
                self.logger.debug("Found %s" % file)
                return Chunk(file, self.path, self)

    def list(self):
        chunks = []
        for filename in sorted(os.listdir(self.path)):
            chunks.append(Chunk(filename, self.path, self))
        return chunks

    def next(self, chunk):
        list = self.list()
        try:
            for idx, file in enumerate(list):
                if file.timestamp == chunk.timestamp:
                    return list[idx + 1]
            return None
        except:
            return None

    def write(self, timestamp, payload):
        Chunk(timestamp=time.time(), path=self.path, cm=self).write(payload=payload)

class Stream(GenericObject):

    def __init__(self, url, cm):
        # print ("### stream.py, Stream init")
        self.url = url
        self.cm = cm

    def listen(self):
        # print ("### stream.py, Stream listen")
        chunk = self.cm.find()
        while chunk:
            self.logger.info("Listening to chunk %d" % chunk.timestamp)
            yield chunk.read()
            self.logger.info("Waiting %d" % chunk.seconds)
            time.sleep(chunk.seconds)
            chunk = self.cm.next(chunk)

        self.logger.error("Run out of chunks")

    def purge(self):
        # print ("### stream.py, Stream purge")
        for chunk in self.cm.list():
            if (time.time() - float(os.path.basename(chunk.timestamp))) > chunk.cm.buffer:
                self.logger.debug("Purge chunk %s" % os.path.basename(chunk.timestamp))
                chunk.delete()

    def buffer(self):
        # print ("### stream.py, Stream buffer")
        conn = urllib2.urlopen(self.url)
        while True:
            chunk = conn.read(BUFFER_SIZE)
            if not chunk:
                break
            self.cm.write(time.time(), chunk)
