import datetime
import logging
import mimetypes
import os
from contextlib import suppress

import requests
from filelock import FileLock

from .utils import PROCESSING_RESULT


class Store:
    def __init__(self, configuration):
        self.config = configuration
        self.logger = logging.getLogger(
            "belegmail.store[{0}]".format(configuration.name)
        )

        self.path = configuration["store"]["path"]
        self.tag = configuration["store"].get("tag", None)
        if self.tag:
            self.pattern = configuration["store"].get(
                "pattern", "{isodate} {tag} Beleg {number:04d} {name}.{ext}"
            )
        else:
            self.pattern = configuration["store"].get(
                "pattern", "{isodate} Beleg {number:04d} {name}.{ext}"
            )

    @classmethod
    def get(cls, configuration):
        mod = configuration["store"]["module"]

        for cls_ in cls.__subclasses__():
            if cls_.__name__ == mod.title() + "Store":
                return cls_(configuration)

            s = cls_.get(configuration)
            if s is not None:
                return s

    def get_number(self, template_data):
        raise NotImplementedError

    def create_name(self, name, ctype, date):
        if date is None:
            date = datetime.date.today()

        template_data = {
            "year": date.strftime("%Y"),
            "isodate": date.strftime("%Y-%m-%d"),
            "tag": self.tag,
        }

        if name:
            nameparts = name.rsplit(".", 1)
            if len(nameparts) == 1:
                template_data["name"] = nameparts[0]
            else:
                template_data["name"], template_data["ext"] = nameparts

        if "ext" not in template_data:
            ext = mimetypes.guess_extension(ctype)
            if not "ext":
                template_data["ext"] = "dat"
            else:
                template_data["ext"] = ext[1:]

        template_data["number"] = self.get_number(template_data)

        formatted_path = self.path.format(**template_data)
        with suppress(FileExistsError):
            os.makedirs(formatted_path)

        filename = self.pattern.format(**template_data).replace("#", "_")

        fparts = filename.rsplit(".", 1)
        filename = "{}.{}".format(fparts[0].strip(), fparts[1].strip().lower())
        filepath = os.path.join(formatted_path, filename)
        return filepath


class NextcloudStore(Store):
    def __init__(self, configuration):
        super().__init__(configuration)
        self.username = configuration["store"]["username"]
        self.password = configuration["store"]["password"]

    def get_number(self, template_data):
        webdav_options = """<?xml version="1.0" encoding="UTF-8"?>
 <d:propfind xmlns:d="DAV:">
   <d:prop xmlns:oc="http://owncloud.org/ns">
     <d:getlastmodified/>
     <d:getcontentlength/>
     <d:getcontenttype/>
     <oc:permissions/>
     <d:resourcetype/>
     <d:getetag/>
   </d:prop>
 </d:propfind>
"""
        try:
            res = requests.request(
                "GET",
                "{}/.serial.txt".format(self.path),
                auth=(self.username, self.password),
                data=webdav_options,
            )

            res.raise_for_status()
            number = int(res.text) + 1
        except:
            number = 1

        requests.request(
            "PUT",
            "{}/.serial.txt".format(self.path),
            auth=(self.username, self.password),
            data="{}".format(number),
        )

        return number

    def store(self, name, data, ctype, date=None):
        file_name = self.create_name(name, ctype, date)

        self.logger.info("Uploading %s bytes to %s", len(data), file_name)

        requests.request(
            "PUT",
            "{}".format(file_name),
            auth=(self.username, self.password),
            data=data,
        )

        return PROCESSING_RESULT.UPLOADED


class DirectoryStore(Store):
    def get_number(self, template_data):
        formatted_path = self.path.format(**template_data)
        with suppress(FileExistsError):
            os.makedirs(formatted_path)

        numberfile = os.path.join(formatted_path, ".serial.txt")
        lock = FileLock("{}.lock".format(numberfile))
        with lock:
            try:
                with open(numberfile, "rt") as fp:
                    n = int(fp.read().strip())
            except:
                n = 0
            n = n + 1
            with open(numberfile, "wt") as fp:
                fp.write(str(n))
        return n

    def store(self, name, data, ctype, date=None):
        filepath = self.create_name(name, ctype, date)

        # FIXME Do not overwrite

        self.logger.info("Writing %s bytes to %s", len(data), filepath)
        with open(filepath, "wb") as fp:
            fp.write(data)

        return PROCESSING_RESULT.UPLOADED
