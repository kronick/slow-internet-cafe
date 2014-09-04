import logging
import subprocess
from time import sleep, time
import requests

logging.root.setLevel(logging.DEBUG)

python = "../venv/bin/python"

proxies = [
    {"name": "localproxy.py", "port": "8080", "tests": [("http://www.google.com", 20)]},
    {"name": "freeproxy.py", "port": "8081"},
    {"name": "blackoutproxy.py", "port": "8082"},
    {"name": "surfproxy.py", "port": "8083"},
    {"name": "swapproxy.py", "port": "8084"},
    {"name": "erasureproxy.py", "port": "8085"},
    {"name": "similarproxy.py", "port": "8086"},
    ]
processes = []

def launch(proxy):
    logging.info("Launching {} on port {}".format(proxy["name"], proxy["port"]))
    proxy["process"] = subprocess.Popen([python, proxy["name"], proxy["port"]])

def kill(proxy):
    logging.warn("Killing {}!".format(proxy["name"]))
    if proxy.get("process"):
        proxy["process"].terminate()

def test(proxy):
    if not proxy.get("tests"):
        return

    logging.debug("Checking to see if {} is running...".format(proxy["name"]))
    for t in proxy["tests"]:
        failed = False
        error = ""
        try:
            r = requests.get(t[0],  timeout=t[1], proxies={"http": "http://127.0.0.1:{}".format(int(proxy["port"]) + 1000)})
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            failed = True
            error = str(e)

        if failed:
            logging.error("{} is not working properly!! Failed to get {}: {}".format(proxy["name"], t[0], error))
            kill(proxy)
            launch(proxy)
            break


for proxy in proxies:
    launch(proxy)

try:
    sleep(5)

    while True:
        for proxy in proxies:
            #test(proxy)
            pass

        sleep(10)
        
except KeyboardInterrupt:
    logging.debug("Terminating...")
    pass

for p in proxies:
    kill(p)

logging.debug("Launcher terminated.")
