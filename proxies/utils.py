from libmproxy import controller
import threading
import sqlite3

import logging, logging.handlers
from config import global_config
from os import path

def concurrent(fn):
    def _concurrent(ctx, msg):

        reply = msg.reply
        m = msg
        msg.reply = controller.DummyReply()
        if hasattr(reply, "q"):
            msg.reply.q = reply.q

        def run():
            fn(ctx, msg)
            reply()

        threading.Thread(target=run).start()
        
    return _concurrent


def get_hostname(clientIP, routerIP):
    db = sqlite3.connect("../dhcp-sync/data/dhcp-sync.db")
    with db:
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        cursor.execute("SELECT * FROM clients WHERE clientIP=? AND routerIP=?", (clientIP, routerIP))
        result = cursor.fetchone()

        if result:

            return result["host"] or None
        else:
            return None


def get_user_info(clientIP, routerIP):
    db = sqlite3.connect("../dhcp-sync/data/dhcp-sync.db")
    with db:
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        cursor.execute("SELECT * FROM clients WHERE clientIP=? AND routerIP=?", (clientIP, routerIP))
        result = cursor.fetchone()

        if result:
            return (result["host"], result["mac"]) or (None, None)
        else:
            return (None, None)


def generate_trust(msg, clientIP, routerIP):
    # Check if this page is a redirect to a HTTPS site or being served over HTTPS itself
    if "trust_the_cafe=1" in msg.flow.request.path:
        host, mac = get_user_info(clientIP, routerIP)
        db = sqlite3.connect("../dhcp-sync/data/dhcp-sync.db")
        with db:
            db.row_factory = sqlite3.Row
            cursor = db.cursor()
            cursor.execute("UPDATE clients SET cert_installed=1 WHERE mac=?", (mac,))
            db.commit()
            print "TRUSTING {}".format(mac)

    if "use_the_cafe=1" in msg.flow.request.path:
        host, mac = get_user_info(clientIP, routerIP)
        db = sqlite3.connect("../dhcp-sync/data/dhcp-sync.db")
        with db:
            db.row_factory = sqlite3.Row
            cursor = db.cursor()
            cursor.execute("UPDATE clients SET active=1 WHERE mac=?", (mac,))
            db.commit()
            print "USING {}".format(mac)

    if msg.code == 200 and "text/html" in " ".join(msg.headers["content-type"]):
        new_user = True
        host, mac = get_user_info(clientIP, routerIP)
        db = sqlite3.connect("../dhcp-sync/data/dhcp-sync.db")
        with db:
            db.row_factory = sqlite3.Row
            cursor = db.cursor()
            cursor.execute("SELECT * FROM clients WHERE mac=?", (mac,))
            result = cursor.fetchall()
            if result:
                for r in result:
                    if r["active"] > 0 or r["cert_installed"] > 0:
                        new_user = False

        if new_user:
            # Redirect to the ABOUT page
            msg.code = 302
            msg.msg = "Found"
            req = msg.flow.request
            if msg.headers.get("location"):
                url = msg.headers["location"][0]
            else:
                url = "{}://{}{}".format(req.get_scheme(), "".join(req.headers["host"]), req.path)

            #msg.headers["location"] = ["{}://cafe.slow/about?r={}".format(msg.flow.request.get_scheme(), url)]
            msg.headers["location"] = ["http://cafe.slow/about?r={}".format(url)]

            return True            

    if ((msg.code in [301, 302, 303, 307]) and msg.headers["location"][0].startswith("https")) or msg.code == 204:
        # Check if this user has already acknowledged the trust certificate
        host, mac = get_user_info(clientIP, routerIP)

        db = sqlite3.connect("../dhcp-sync/data/dhcp-sync.db")
        with db:
            db.row_factory = sqlite3.Row
            cursor = db.cursor()
            cursor.execute("SELECT * FROM clients WHERE mac=?", (mac,))
            result = cursor.fetchall()
            if result:
                for r in result:
                    if r["cert_installed"] > 0:
                        return False
        
        # Redirect to the HTTPS trust page
        msg.code = 302
        msg.msg = "Found"
        req = msg.flow.request
        if msg.headers.get("location"):
            url = msg.headers["location"][0]
        else:
            url = "{}://{}{}".format(req.get_scheme(), "".join(req.headers["host"]), req.path)

        msg.headers["location"] = ["{}://trust-us.slow/?r={}".format(msg.flow.request.get_scheme(), url)]
        
        return True
    
    # If this is a plain HTTP page, don't worry about it
    return False


CP_ALLOWED_HOSTS = ["captive.apple.com"]
CP_ALLOWED_AGENTS = ["CaptiveNetworkSupport"]
def avoid_captive_portal(msg):
    user_agent = "".join(msg.flow.request.headers["user-agent"])
    if msg.flow.request.host in CP_ALLOWED_HOSTS:
        return True

    for agent in CP_ALLOWED_AGENTS:
        if agent in user_agent:
            return True

    return False


def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(min(global_config["log_level"], global_config["log_console_level"]))
    formatter = logging.Formatter("%(asctime)s [%(name)s - %(levelname)s] %(message)s")
    #filehandler = logging.FileHandler(path.join(global_config["log_dir"], name), encoding="utf-8")
    filehandler = logging.handlers.RotatingFileHandler(path.join(global_config["log_dir"], name), maxBytes=global_config["log_max_size"], backupCount=10, encoding="utf-8")
    filehandler.setLevel(global_config["log_level"])
    filehandler.setFormatter(formatter)
    logger.addHandler(filehandler)
    if global_config["log_console_level"]:
        # Add a handler to output to stdout & stderr
        stream_formatter = logging.Formatter("%(asctime)s [%(name)s - %(levelname)s] %(message)s")
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(global_config["log_console_level"])
        stream_handler.setFormatter(stream_formatter)
        logger.addHandler(stream_handler)

    return logger


