from flask import Flask, request
import sqlite3
import time

app = Flask(__name__)
app.logger.setLevel(0)

@app.route("/update", methods=["POST"])
def update():
    action = request.form["action"]
    mac    = request.form["mac"]
    ip     = request.form["ip"]
    host   = request.form["hostname"]
    
    router = request.remote_addr

    db = sqlite3.connect("data/dhcp-sync.db")
    
    with db:
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cursor.execute("SELECT * FROM clients WHERE routerIP=? AND mac=? AND clientIP=?",
                        (router, mac, ip))
        resource = cursor.fetchone()

        if action == "add":
            if resource:
                # If this record already exists, it should be interpreted as an OLD entry
                lasttime = resource["time"]
                updateRecord(cursor,db,router,mac,ip,host)
                print "{} is back (but new to the DHCP server)! (last seen {}) {}".format(host or mac, lasttime, mac)
            else:
                createRecord(cursor, db, router, ip, mac, host)
                print "Welcome to {} on {}".format(host or mac, ip)

        elif action == "old":
            # Update record with current time
            if resource is None:
                # This record doesn't yet exist
                lasttime = 0
                createRecord(cursor, db, router, ip, mac, host)

            else:
                # Record already exists, just update time
                lasttime = resource["time"]
                updateRecord(cursor,db,router,mac,ip,host)

            print "{} is back! (last seen {}) {}".format(host or mac, lasttime, mac)
        
        elif action == "del":
            removeRecord(cursor,db,router,mac,ip,host)
            print "{} is no longer with us.".format(host or mac)
            # Select entries in database with this IP 

    return "OK"

def createRecord(cursor, db, router, ip, mac, host):
    # Make sure there's only one entry per router/IP
    cursor.execute("DELETE FROM clients WHERE routerIP=? and clientIP=?", (router, ip))

    cursor.execute("INSERT INTO clients(routerIP, clientIP, mac, host, time, active, cert_installed)" \
                    "values(?, ?, ?, ?, ?, 1, 0)", (router, ip, mac, host, int(time.time())))
    db.commit()

def updateRecord(cursor, db, router, mac, ip, host):
    # Make sure there's only one entry per router/IP
    cursor.execute("DELETE FROM clients WHERE routerIP=? and clientIP=? and mac!=?", (router, ip, mac))

    cursor.execute("UPDATE clients SET time = ? WHERE routerIP=? and mac=? and clientIP=?",
                   (int(time.time()), router, mac, ip))
    db.commit()            
    
def removeRecord(cursor, db, router, mac, ip, host):
    cursor.execute("DELETE FROM clients WHERE routerIP=? and clientIP=?",
                    (router, mac, ip))
    db.commit()

app.debug = True
if __name__ == "__main__":
    app.run(host='0.0.0.0')
