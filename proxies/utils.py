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