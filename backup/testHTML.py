from bs4 import BeautifulSoup
import unirest, json

recipeName = "challah"

searchUrl = "http://www.epicurious.com/tools/searchresults?search=" + recipeName
searchResponse = unirest.get(searchUrl)
searchData = searchResponse.body
searchSource = BeautifulSoup(searchData, 'html.parser')

recipe = searchSource.find('a', { "class" : "recipeLnk" })
recipeName = recipe.get_text()
recipeLink = recipe.get('href')

recipeGetUrl = "http://www.epicurious.com" + recipeLink
recipeResponse = unirest.get(recipeGetUrl)
recipeData = recipeResponse.body
recipeSource = BeautifulSoup(recipeData, 'html.parser')

ingredients = []
instructions = []
for ingredient in recipeSource.find_all('li', { "class" : "ingredient" }):
    print(ingredient.get_text())
    ingredients.append(ingredient.get_text())
for step in recipeSource.find_all('li', { "class" : "preparation-step" }):
    stepText = step.get_text()
    stepText = stepText.strip()
    print(stepText)
    instructions.append(stepText)
