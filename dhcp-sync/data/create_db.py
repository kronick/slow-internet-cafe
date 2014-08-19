import sqlite3
db = sqlite3.connect("dhcp-sync.db")

cursor = db.cursor()
cursor.execute('''
        CREATE TABLE clients(id INTEGER PRIMARY KEY, clientIP KEY, routerIP, mac, host, time, active, cert_installed)
''')

db.commit()
db.close()
