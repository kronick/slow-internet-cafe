from libmproxy import controller
import threading
import sqlite3

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
    if ((msg.code in [301, 302, 303, 307]) and msg.headers["location"][0].startswith("https")): #or \
        #msg.flow.request.get_scheme() == "https" or msg.code == 204:
        # Check if this user has already acknowledged the trust certificate
        db = sqlite3.connect("../dhcp-sync/data/dhcp-sync.db")
        with db:
            db.row_factory = sqlite3.Row
            cursor = db.cursor()
            cursor.execute("SELECT * FROM clients WHERE clientIP=? and routerIP=?", (clientIP, routerIP))
            result = cursor.fetchone()

            if result and result["cert_installed"] > 0:
                return False    # No need to do anything more...
        
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
