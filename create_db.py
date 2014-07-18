import sqlite3
db = sqlite3.connect("db/blackout.db")

cursor = db.cursor()
cursor.execute('''
	CREATE TABLE resources(id INTEGER PRIMARY KEY, url KEY unique,
						   last_accessed INTEGER, life_remaining INTEGER)
''')

db.commit()

db.close()