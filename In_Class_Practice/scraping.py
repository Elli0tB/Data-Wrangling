import pandas as pd 
import requests
from bs4 import BeautifulSoup
from io import StringIO
import os

def wikipidaTable():
    url = "https://en.wikipedia.org/wiki/List_of_counties_in_Utah"
    if not os.path.isfile("cache.html"):
        resp = requests.get(url)
        with open("cache.html", 'w') as f:
            f.write(resp.text)
        webpage = resp.text
    else:
        with open("cache.html") as f:
            webpage = f.read()
    tables = pd.read_html(StringIO(resp.text))
    print (len(tables))
    print (tables[0])

    # ollama 
    response = ollama.generate(model="gemma4:e2b", prompt = "give me the list of counites in the html")
    print (response)



