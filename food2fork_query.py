#scrapes food2fork for recipe titles and prints it
import requests
import json

for x in range (1, 301):
    #each page contains 30 recipe titles
    #replace '{your_API_key}' with your key
    link = 'http://food2fork.com/api/search?key={your_API_key}&page=' + str(x)
    page = requests.get(link)
    j_page = json.loads(page.text)
    data = json.loads(page.text)
    for recipe in data['recipes']:
        name = recipe['title']
        print name
    
    