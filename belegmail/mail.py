import datetime
import email
import email.utils
import io
import logging
import re
import zipfile
from email.header import decode_header
from signal import SIGINT, SIGTERM

import imapclient
import magic
import requests
from pysigset import suspended_signals

from .store import Store
from .utils import PROCESSING_RESULT

ACCEPTABLE_LIST = ["image/jpeg", "application/pdf", "application/x-pdf", "image/png"]
ACCEPTABLE_ZIP = ["application/zip", "application/x-zip-compressed"]
ACCEPTABLE_OCTET = "application/octet-stream"

ZIP_RECURSION_LIMIT = 2

BVG_URL_RE = re.compile(
    r"""(?P<url>https://shop\.bvg\.de/index\.php/(?:receipt/download/|generic/culture/[^/]+?return=[^/]+receipt%2fdownload%2f)(?P<id>\w+)(?:/\w+?/\w+?|%2f\w+?%2f\w+?))""",
    re.I,
)


def decode_header_value(data):
    result = []
    for text, encoding in decode_header(data):
        if hasattr(text, "decode"):
            result.append(text.decode(encoding or "us-ascii"))
        else:
            result.append(text)
    return "".join(result)


class ImapReceiver:
    def __init__(self, configuration):
        self.config = configuration
        self.store = Store.get(configuration)
        self.logger = logging.getLogger(
            "belegmail.mail[{0}]".format(configuration.name)
        )

    def run_once(self):
        return self.run(once=True)

    def run(self, once=False):
        config = self.config["imap"]

        server = imapclient.IMAPClient(
            config["server"], port=config["port"], ssl=config["ssl"]
        )
        server.login(config["username"], config["password"])

        server.debug = config.get("debug", False)

        first_done = False

        while not once or not first_done:
            first_done = True

            today = datetime.date.today()
            target_folder = "Hochgeladen {0}".format(today.year)
            if not server.folder_exists(target_folder):
                server.create_folder(target_folder)
                server.subscribe_folder(target_folder)

            select_info = server.select_folder("INBOX")
            if select_info[b"EXISTS"]:
                messages = server.search(["NOT", "DELETED", "NOT", "SEEN"])

                with suspended_signals(SIGINT, SIGTERM):
                    response = server.fetch(messages, ["RFC822"])

                    for msgid, data in response.items():
                        body = data[b"RFC822"]
                        target = None
                        result = PROCESSING_RESULT.ERROR

                        try:
                            message = email.message_from_bytes(body)

                            result = self.handle_mail(message, guessed_date=today)

                        except:
                            self.logger.exception(
                                "Fehler beim Bearbeiten der Mail {0}".format(msgid)
                            )

                        finally:
                            if result is PROCESSING_RESULT.UPLOADED and not config.get(
                                "dryrun", False
                            ):
                                server.add_flags(msgid, [imapclient.SEEN])
                                server.copy(msgid, target_folder)
                                server.delete_messages(msgid)
                                server.expunge()
                            elif result in (
                                PROCESSING_RESULT.IGNORE,
                                PROCESSING_RESULT.OTHER,
                            ):
                                server.remove_flags(msgid, [imapclient.SEEN])

            if not once:
                server.idle()
                server.idle_check(
                    timeout=300
                )  # Do a normal poll every 5 minutes, just in case
                server.idle_done()

    def handle_mail(self, message, guessed_date=None):
        if not self.check_access(message):
            self.logger.info("Message not from allowed sender or recipient")
            return PROCESSING_RESULT.IGNORE

        if guessed_date is None:
            guessed_date = datetime.date.today()

        upload_count = 0
        error_count = 0

        if "Date" in message:
            guessed_date = email.utils.parsedate_to_datetime(message.get("date")).date()
            self.logger.info("Message date: %s", guessed_date)

        retval = self.handle_special_messages(message, guessed_date)
        if retval is PROCESSING_RESULT.ERROR:
            return retval

        if not message.is_multipart():
            self.logger.info("Message is not multipart message")
            return retval

        inner_date = guessed_date
        for part in message.walk():
            ctype = part.get_content_type()
            name, data = None, None
            self.logger.info("Have %r", ctype)

            if "Date" in part:
                inner_date = email.utils.parsedate_to_datetime(part.get("date")).date()
                self.logger.info("Inner date: %s", inner_date)

            if ctype in ACCEPTABLE_LIST + ACCEPTABLE_ZIP + [ACCEPTABLE_OCTET]:
                name = decode_header_value(part.get_filename())
                data = part.get_payload(decode=True)

            if ctype == ACCEPTABLE_OCTET:
                magic_type = magic.from_buffer(data, mime=True)
                if magic_type in ACCEPTABLE_LIST + ACCEPTABLE_ZIP:
                    ctype = magic_type
                else:
                    data = None

            if data:
                if ctype in ACCEPTABLE_ZIP:
                    part_iter = self.handle_zip(name, ctype, data)
                else:
                    part_iter = [(name, ctype, data)]

                for (name, ctype, data) in part_iter:
                    self.logger.info(
                        "Have attachment %r (%s) of size %s", name, ctype, len(data)
                    )
                    result = None
                    try:
                        result = self.store.store(name, data, ctype, date=inner_date)
                    except:
                        self.logger.exception(
                            "Fehler beim Hochladen des Attachments {0}".format(name)
                        )
                        error_count = error_count + 1

                    if result:
                        self.logger.info(
                            "Attachment hochgeladen, Ergebnis: {0}".format(result)
                        )
                        upload_count = upload_count + 1

        if error_count > 0:
            return PROCESSING_RESULT.ERROR

        if upload_count > 0:
            return PROCESSING_RESULT.UPLOADED

        return PROCESSING_RESULT.PROCESSED

    def handle_zip(self, name, ctype, data, recursion=0):
        if recursion <= ZIP_RECURSION_LIMIT:
            zio = io.BytesIO(data)
            with zipfile.ZipFile(zio) as zfile:
                for finfo in zfile.infolist():
                    fdata = zfile.read(finfo)

                    fctype = magic.from_buffer(fdata, mime=True)

                    new_basename = name.rsplit(".", 1)[0]

                    new_name = "{0}__{1}".format(
                        new_basename,
                        finfo.filename.replace("/", "__").replace("\\", "__"),
                    )

                    if fctype in ACCEPTABLE_LIST:
                        yield (new_name, fctype, fdata)
                    elif fctype in ACCEPTABLE_ZIP:
                        yield from self.handle_zip(
                            new_name, fctype, fdata, recursion + 1
                        )

    def check_access(self, message):
        senders = message.get_all("from", [])
        recipients = message.get_all("to", []) + message.get_all("cc", [])

        for name, sender in email.utils.getaddresses(senders):
            for allowed_sender in self.config.get("access", {}).get("from", []):
                if sender.lower() == allowed_sender.lower():
                    return True

        for name, recipient in email.utils.getaddresses(recipients):
            for allowed_recipient in self.config.get("access", {}).get("to", []):
                if recipient.lower() == allowed_recipient.lower():
                    return True

        return False

    def handle_special_messages(self, message, guessed_date):
        attempt_count = 0
        error_count = 0

        for part in message.walk():
            ctype = part.get_content_type()

            if ctype == "text/plain":
                try:
                    data = part.get_payload(decode=True).decode()
                except UnicodeDecodeError:
                    continue

                bvg_match = BVG_URL_RE.search(data)
                if bvg_match:
                    attempt_count = attempt_count + 1
                    response = requests.get(bvg_match.group("url"))
                    name = "BVG-Rechnung {}.pdf".format(
                        bvg_match.group("id") or guessed_date
                    )
                    if response:
                        try:
                            result = self.store.store(
                                name, response.content, ctype, date=guessed_date
                            )
                        except:
                            self.logger.exception(
                                "Fehler beim Hochladen des Attachments {0}".format(name)
                            )
                            error_count = error_count + 1
                    else:
                        error_count = error_count + 1
                        self.logger.error(
                            "Fehler beim Abrufen von {0}".format(bvg_match.group("url"))
                        )

        if attempt_count == 0:
            return PROCESSING_RESULT.OTHER

        else:
            if error_count > 0:
                return PROCESSING_RESULT.ERROR
            else:
                return PROCESSING_RESULT.UPLOADED
