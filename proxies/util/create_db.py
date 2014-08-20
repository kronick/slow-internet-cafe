import sqlite3
import sys, getopt

def createTables(overwrite=False):
    
    if overwrite:
        ifnotexists = ""
    else:
        ifnotexists = "IF NOT EXISTS"

    # with sqlite3.connect("../db/blackout.db") as db:
    #     cursor = db.cursor()

    #     if overwrite:
    #         cursor.execute('''DROP TABLE resources''')

    #     cursor.execute('''
    #         CREATE TABLE {} resources(id INTEGER PRIMARY KEY, url KEY unique,
    #                                last_accessed INTEGER, accessed_by, life_remaining INTEGER)
    #     '''.format(ifnotexists))
    #     db.commit()
    

    with sqlite3.connect("../db/swap.db") as db:
        cursor = db.cursor()

        if overwrite:
            cursor.execute("DROP TABLE IF EXISTS images")
            cursor.execute("DROP TABLE IF EXISTS strings")
            cursor.execute("DROP TABLE IF EXISTS links")
            cursor.execute("DROP TABLE IF EXISTS hosts")
            cursor.execute("DROP TABLE IF EXISTS users")
            
        cursor.execute("pragma foreign_keys = on")

        cursor.execute('''
            CREATE TABLE {} users(mac PRIMARY KEY UNIQUE, hostname, 
                                   last_ip, last_seen INTEGER)
        '''.format(ifnotexists))

        cursor.execute('''
            CREATE TABLE {} strings(string_id INTEGER PRIMARY KEY, string_user INTEGER, string,
                                    length INTEGER KEY, url, time_added INTEGER,
                                    FOREIGN KEY(string_user) REFERENCES users(mac))
        '''.format(ifnotexists))

        cursor.execute('''
            CREATE TABLE {} images(image_id INTEGER PRIMARY KEY, image_user INTEGER, image, url,
                                   width INTEGER KEY, height INTEGER KEY, time_added INTEGER,
                                   FOREIGN KEY(image_user) REFERENCES users(mac))
        '''.format(ifnotexists))

        cursor.execute('''
            CREATE TABLE {} links(link_id INTEGER PRIMARY KEY, link_user INTEGER, url, time_added INTEGER,
                                   FOREIGN KEY(link_user) REFERENCES users(mac))
        '''.format(ifnotexists))        

        db.commit()

if __name__ == "__main__":
    try:
        opts, args = getopt.getopt(sys.argv[1:], "o", ["overwrite"])
    except getopt.GetoptError:
        print "USAGE: python create_db.py [-o]"
        print "       -o     overwrites existing databases"
        sys.exit(2)

    overwrite = False
    for opt,arg in opts:
        if opt in ("-o", "--overwrite"):
            overwrite = True

    createTables(overwrite)