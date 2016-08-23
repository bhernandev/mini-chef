from __future__ import print_function #required to use print starting from Python 2
import sys  #for error handling in the database
import unirest, json
import boto3 #this is to use Amazon services like DynamoDB in our app
import decimal #this is to do something with decimals
from bs4 import BeautifulSoup

# Helper class to convert a DynamoDB item to JSON.
#ignore this, I just copied it honestly, but basically when we get an item from DynamoDB
#it gets it in binary and then we convert it to a regular dictionary
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)

#---------------------------FUCK THE COMMENTED SHIT----------------------------
#sts_client = boto3.client('sts')

# assumedRoleObject = sts_client.assume_role(
#     RoleArn="arn:aws:iam::437414226734:role/ChefBrian",
#     RoleSessionName="AssumeRoleSession1"
# )
# credentials = assumedRoleObject['Credentials']

#dynamodb = boto3.resource('dynamodb', region_name='us-east-1', aws_access_key_id = credentials['AccessKeyId'], aws_secret_access_key = credentials['SecretAccessKey'], aws_session_token = credentials['SessionToken'],)

#sets up the DynamoDB client to create tables and the resource to work with those tables
#I use my secret security credentials, but you'll have to generate and use your own
TABLE_NAME_FOR_ANY_ACCOUNT = "chefBrianData"

# --------------- Request handler ------------------
def lambdaHandler(event, context):
    print("event.session.application.applicationId=" +
          event['session']['application']['applicationId'])

    #check if the application id matches the session id
    if (event['session']['application']['applicationId'] != "amzn1.echo-sdk-ams.app.d697caf7-a152-47e6-ad58-73c7f7bc65e4"):
        raise ValueError("Invalid Application ID")

    #launch different function depending on type of request
    if event['request']['type'] == "LaunchRequest":
        return onLaunch(event['request'], event['session']) #request without an intent -> welcome message
    elif event['request']['type'] == "IntentRequest":
        return onIntent(event['request'], event['session']) #request with an intent -> intent handler
    elif event['request']['type'] == "SessionEndedRequest":
        return onSessionEnded(event['request'], event['session']) #request to end the session -> session ender

# --------------- Request Handles ------------------
def onLaunch(launch_request, session):
    """ Called when the user launches the skill without specifying what they want"""

    # get the welcome response
    return getWelcomeResponse()

#Function to handle all incoming intents
def onIntent(intent_request, session):
    """ Called when the user specifies an intent for this skill """

    #attempt to create a recipe data table before going through any intent
    createTable()

    intent = intent_request['intent']
    intent_name = intent_request['intent']['name']

    #intent to get the recipe asked for
    if intent_name == "getRecipeIntent":
        return getRecipe(intent, session)
    #intent to have ingredients read out
    elif intent_name == "readIngredientsIntent":
        return readIngredients(intent, session)
    #intent to start reading the recipe instructions
    elif intent_name == "startRecipeIntent":
        return startRecipe(intent, session)
    #intent to advance to the next step of the instructions
    elif intent_name == "nextStepIntent":
        return nextStep(intent, session)
    #intent to repeat the current step
    elif intent_name == "repeatStepIntent":
        return repeatStep(intent, session)
    #intent to go back to the previous step
    elif intent_name == "previousStepIntent":
        return previousStep(intent, session)
    #intent to load recipe data
    elif intent_name == "loadRecipeIntent":
            return loadRecipe(intent, session)
    elif intent_name == "AMAZON.HelpIntent":
        return getWelcomeResponse()
    #quit intents
    elif intent_name == "AMAZON.CancelIntent" or intent_name == "AMAZON.StopIntent":
        return sessionEndRequestHandle()
    else:
        raise ValueError("Invalid intent")


def onSessionEnded(session_ended_request, session):
    """ Called when the user ends the session. Is not called when the skill returns should_end_session=true"""

    print("on_session_ended requestId=" + session_ended_request['requestId'] + ", sessionId=" + session['sessionId'])


# --------------- Functions for all of the intents ------------------
#returns the welcome response when no intent is specified
def getWelcomeResponse():
    session_attributes = {}
    session_attributes["currentStep"] = -1
    session_attributes["recipeName"] = ""
    session_attributes["recipeInstructions"] = []
    session_attributes["recipeFound"] = False
    session_attributes["recipeIngredients"] = []

    card_title = "Time to Cook"
    speech_output = "Let's start cooking!" + " First, tell me what you want to make."
    text_output = "Let's start cooking!" + " First, tell me what you want to make."
    reprompt_text = "Sorry, I didn't get that." + " Tell me what you want to make."
    should_end_session = False
    return buildResponse(session_attributes, buildSpeechResponse(
        card_title, speech_output, text_output, reprompt_text, should_end_session))


#returns the end session response for when a user escapes the session
def sessionEndRequestHandle():
    card_title = "Voila, All Done"
    speech_output = "I hope cooking with me was fun. " + "Bon appetit!"
    text_output = "I hope cooking with me was fun. " + "Bon appetit!"
    # Setting this to true ends the session and exits the skill.
    should_end_session = True
    return buildResponse({}, buildSpeechResponse(
        card_title, speech_output, text_output, None, should_end_session))


#returns the top three most relevant recipes
def searchRecipes(intent, session):

    #card_title = intent['name']
    session_attributes = {}
    should_end_session = False

    #if the recipe name exists in the list of recipes (slots list is specified in Amazon developer console)
    if 'Recipe' in intent['slots']:
        recipeName = intent['slots']['Recipe']['value'] #store the name of the recipe

        #scrape Epicurious search page for the first three recipes
        searchUrl = "http://www.epicurious.com/tools/searchresults?search=" + recipeName
        searchResponse = unirest.get(searchUrl)
        searchData = searchResponse.body
        searchSource = BeautifulSoup(searchData, 'html.parser')

        recipeNames = []
        recipeLinks = []
        for recipe in searchSource.find_all('a', { "class" : "recipeLnk" }, limit=3):
            recipeName = recipe.get_text()
            recipeNames.append(recipeName)
            recipeLink = recipe.get('href')
            recipeLinks.append(recipeLink)



        #using Spoonacular API to extract recipe ingredients and instructions for the recipe URL fetched with Food2Fork
        newGetUrl = "https://spoonacular-recipe-food-nutrition-v1.p.mashape.com/recipes/extract?forceExtraction=false&url=" + getUrl
        recipeResponse = unirest.get(newGetUrl, headers={"X-Mashape-Key": "ZdI3P7OSmGmshXpO0mDVMDVndgoop1jjFIGjsnJBkk43YdMgsm"})
        recipeData = recipeResponse.body #store the json body of the response to the get request

        #if the data is not empty
        if recipeData:
            #create an empty ingredients list and add each ingredient to the list
            recipeIngredients = []
            for ingredient in recipeData['extendedIngredients']:
                ingredientText = ingredient['originalString'] + ". "
                recipeIngredients.append(ingredientText)

            recipeInstructions = recipeData['text']
            #some recipe instructions don't exist, so if they do, store them and divide them into parts
            session_attributes["recipeInstructions"] = []
            if recipeInstructions:
                instructionsList = recipeInstructions.split('.');
                session_attributes["recipeInstructions"] = instructionsList

            #set the session attributes and card title for the companion app
            session_attributes["recipeName"] = recipeName
            card_title = "Ingredients for " + recipeName
            session_attributes["recipeFound"] = True
            session_attributes["recipeIngredients"] = recipeIngredients
            session_attributes["currentStep"] = -1

            #we save the recipe data in the table when we get it
            storeRecipeData(session["user"]["userId"], recipeName, recipeIngredients, recipeInstructions, 0)

            speech_output = "I found the recipe for " + recipeName + ". I sent the ingredients to your phone. " + "Would you like me to read the ingredients or jump straight to the instructions?"
            text_output = "Ingredients:\n"
            for ingredient in recipeIngredients:
                text_output = text_output + ingredient + "\n"
            reprompt_text = "I sent the ingredients to your phone. " + " Would you like me to say them?"
    else:
        speech_output = "I'm not sure I know how to cook that. " + "Want to to try something else?"
        text_output = "I'm not sure I know how to cook that. " + "Want to to try something else?"
        reprompt_text = "I'm not sure I know how to cook that. " + "Want to to try something else?"
    return buildResponse(session_attributes, buildSpeechResponse(
        card_title, speech_output, text_output, reprompt_text, should_end_session))


#read the ingredients list aloud
def readIngredients(intent, session):

    card_title = "Read Ingredients Aloud for " + session["attributes"]["recipeName"]
    session_attributes = session["attributes"]
    should_end_session = False
    speech_output = ""
    ingredientsList = session["attributes"]["recipeIngredients"]

    if session["attributes"]["recipeFound"] == True:
        #we save the recipe data in every intent actually just for safety, so no matter what happens, it's always saved
        storeRecipeData(session["user"]["userId"], session["attributes"]["recipeName"], ingredientsList, session["attributes"]["recipeInstructions"], 0)

        for ingredient in ingredientsList:
            speech_output += ingredient
        #speech_output += " <break time="1ms"/>  Say instructions when you're ready to start cooking."
        text_output = ""
        reprompt_text = "Say instructions when you're ready to start cooking."
    else:
        speech_output = "I don't understand what you're saying, bro."
        text_output = "I don't understand what you're saying, bro."
        reprompt_text = "I don't understand what you're saying, bro."
    return buildResponse(session_attributes, buildSpeechResponse(
        card_title, speech_output, text_output, reprompt_text, should_end_session))

#start reading the recipe instructions
def startRecipe(intent, session):

    card_title = session["attributes"]["recipeName"]
    session_attributes = session["attributes"]
    should_end_session = True

    #only attempt to read the recipe if it was already found, otherwise prompt to first choose a recipe to make
    if session["attributes"]["recipeFound"] == True:
        recipeText = session["attributes"]["recipeInstructions"]
        if recipeText:
            should_end_session = False
            session_attributes["currentStep"] = 0
            currentStep = session_attributes["currentStep"]
            storeRecipeData(session["user"]["userId"], session["attributes"]["recipeName"], session["attributes"]["recipeIngredients"], recipeText, currentStep)

            speech_output = recipeText[currentStep]
            text_output = recipeText[currentStep]
            reprompt_text = ""
        else:
            speech_output = "There are no instructions for this recipe."
            text_output = "There are no instructions for this recipe."
            reprompt_text = "There are no instructions for this recipe."
    else:
        speech_output = "First, we need a recipe to cook!"
        text_output = "First, we need a recipe to cook!"
        reprompt_text = "First, we need a recipe to cook!"

    return buildResponse(session_attributes, buildSpeechResponse(
        card_title, speech_output, text_output, reprompt_text, should_end_session))

#go to the next step in the recipe instructions
def nextStep(intent, session):

    session_attributes = session["attributes"]
    should_end_session = False

    recipeText = session["attributes"]["recipeInstructions"]
    currentStep = session["attributes"]["currentStep"]
    currentStep += 1 #increment a current step variable by 1
    card_title = "Step " + `currentStep + 1`

    if currentStep > 0 and currentStep < len(recipeText):

        session_attributes["currentStep"] = currentStep #save the current step to the session attributes
        storeRecipeData(session["user"]["userId"], session["attributes"]["recipeName"], session["attributes"]["recipeIngredients"], recipeText, currentStep)

        speech_output = recipeText[currentStep]
        text_output = recipeText[currentStep]
        reprompt_text = ""

    else:
        if currentStep <= 0:
            card_title = "I Don't Know What to Make"
            should_end_session = False
            speech_output = "First, we need a recipe to cook!"
            text_output = "First, we need a recipe to cook!"
            reprompt_text = "First, we need a recipe to cook!"
        elif currentStep >= len(recipeText) and len(recipeText) > 0:
            card_title = "Finished!"
            should_end_session = True
            speech_output = "All done. Enjoy your meal."
            text_output = "All done. Enjoy your meal."
            reprompt_text = "All done. Enjoy your meal."

    return buildResponse(session_attributes, buildSpeechResponse(
        card_title, speech_output, text_output, reprompt_text, should_end_session))


#repeat the current step (don't increment current step)
def repeatStep(intent, session):

    session_attributes = session["attributes"]
    should_end_session = False

    recipeText = session["attributes"]["recipeInstructions"]
    currentStep = session["attributes"]["currentStep"]
    card_title = "Step " + `currentStep + 1`

    if currentStep >= 0 and currentStep < len(recipeText):

        session_attributes["currentStep"] = currentStep
        storeRecipeData(session["user"]["userId"], session["attributes"]["recipeName"], session["attributes"]["recipeIngredients"], recipeText, currentStep)

        speech_output = recipeText[currentStep]
        text_output = recipeText[currentStep]
        reprompt_text = ""

    else:
        if currentStep < 0:
            card_title = "I Don't Know What to Make"
            should_end_session = False
            speech_output = "First, we need a recipe to cook!"
            text_output = "First, we need a recipe to cook!"
            reprompt_text = "First, we need a recipe to cook!"
        elif currentStep >= len(recipeText) and len(recipeText) > 0:
            card_title = "Finished!"
            should_end_session = True
            speech_output = "All done. Enjoy your meal."
            text_output = "All done. Enjoy your meal."
            reprompt_text = "All done. Enjoy your meal."

    return buildResponse(session_attributes, buildSpeechResponse(
        card_title, speech_output, text_output, reprompt_text, should_end_session))

#read the previous step of the recipe instructions
def previousStep(intent, session):

    session_attributes = session["attributes"]
    should_end_session = False

    recipeText = session["attributes"]["recipeInstructions"]
    currentStep = session["attributes"]["currentStep"]
    currentStep -= 1  #decrement current steo by 1
    card_title = "Step " + `currentStep + 1`

    if currentStep >= 0 and currentStep < len(recipeText):

        session_attributes["currentStep"] = currentStep
        storeRecipeData(session["user"]["userId"], session["attributes"]["recipeName"], session["attributes"]["recipeIngredients"], recipeText, currentStep)

        speech_output = recipeText[currentStep]
        text_output = recipeText[currentStep]
        reprompt_text = recipeText[currentStep]

    else:
        if currentStep < 0:
            if session["attributes"]["recipeFound"] == True:
                currentStep += 1
                session_attributes["currentStep"] = currentStep
                card_title = "Step " + `currentStep + 1`
                should_end_session = False
                speech_output = recipeText[currentStep]
                text_output = recipeText[currentStep]
                reprompt_text = ""
            else:
                card_title = "I Don't Know What to Make"
                should_end_session = False
                speech_output = "First, we need a recipe to cook!"
                text_output = "First, we need a recipe to cook!"
                reprompt_text = "First, we need a recipe to cook!"
        elif currentStep >= len(recipeText) and len(recipeText) > 0:
            card_title = "Finished!"
            should_end_session = True
            speech_output = "All done. Enjoy your meal."
            text_output = "All done. Enjoy your meal."
            reprompt_text = "All done. Enjoy your meal."

    return buildResponse(session_attributes, buildSpeechResponse(
        card_title, speech_output, text_output, reprompt_text, should_end_session))

#this function loads the recipe data
def loadRecipe(intent, session):
    session_attributes = {}

    #retrieve the recipe data from the table
    recipe = loadRecipeData(session["user"]["userId"])
    #if it's not empty, set the session attributes to it and build a response to the intent
    if recipe:
        session_attributes["currentStep"] = recipe["currentStep"]
        session_attributes["recipeName"] = recipe["recipeName"]
        session_attributes["recipeInstructions"] = recipe["recipeInstructions"]
        session_attributes["recipeFound"] = True
        session_attributes["recipeIngredients"] = recipe["recipeIngredients"]

        card_title = recipe["recipeName"] + " recipe found"
        should_end_session = True
        recipeText = recipe["recipeInstructions"]
        speech_output = "We stopped on step " + str(recipe["currentStep"]+1) + ". " + recipeText[recipe["currentStep"]]
        text_output = "We stopped on step " + str(recipe["currentStep"]+1) + ". " + recipeText[recipe["currentStep"]]
        reprompt_text = "Just say 'go on' to advance to the next step."
        should_end_session = False
    #otherwise set the sesison attributes to defaults and say that no recipe data could be found
    else:
        session_attributes["currentStep"] = -1
        session_attributes["recipeName"] = ""
        session_attributes["recipeInstructions"] = []
        session_attributes["recipeFound"] = False
        session_attributes["recipeIngredients"] = []

        card_title = "Couldn't find a saved recipe"
        should_end_session = True
        speech_output = "It seems like I couldn't find a recipe in progress."
        text_output = "It seems like I couldn't find a recipe in progress."
        reprompt_text = "Say 'let's make' and the name of a dish to start cooking it."
        should_end_session = False

    return buildResponse(session_attributes, buildSpeechResponse(
        card_title, speech_output, text_output, reprompt_text, should_end_session))


# --------------- Helpers that build all of the responses ----------------------
#build the json for the speech response for Alexa
def buildSpeechResponse(title, output, text_output, reprompt_text, should_end_session):
    return {
        'outputSpeech': {
            'type': 'PlainText',
            'text': output
        },
        'card': {
            'type': 'Simple',
            'title': title,
            'content': text_output
        },
        'reprompt': {
            'outputSpeech': {
                'type': 'PlainText',
                'text': reprompt_text
            }
        },
        'shouldEndSession': should_end_session#
    }

#function that builds the entire json response including passing in the session attributes
def buildResponse(session_attributes, speechlet_response):
    return {
        'version': '1.0',
        'sessionAttributes': session_attributes,
        'response': speechlet_response
    }


#-------------------Functions for DynamoDB table operations---------------------
def createTable():
    #try to get the info for an existing table
    try:
        existingTable = dynamodbClient.describe_table(TableName = TABLE_NAME_FOR_ANY_ACCOUNT)
    #but if there's an exception create a new table
    except:
        newTable = dynamodbClient.create_table(
            TableName = TABLE_NAME_FOR_ANY_ACCOUNT,
            KeySchema = [ #every table needs a key, which is a unique value for every item in the table
                {
                    'AttributeName': 'userId',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions = [
                {
                    'AttributeName': 'userId',
                    'AttributeType': 'S'
                },
            ],
            ProvisionedThroughput = {  #some advanced bullshit
                'ReadCapacityUnits': 10,
                'WriteCapacityUnits': 10
            }
        )

def storeRecipeData(userId, name, ingredients, instructions, step):
    #try to save the recipe data to the table
    try:
        table = dynamodbResource.Table(TABLE_NAME_FOR_ANY_ACCOUNT)
        tableWithRecipe = table.put_item( #we put all the values into a dictionary, which acts as our item
            Item = {
                'userId': userId,
                'recipeFound': 'True',
                'recipeName': name,
                'recipeIngredients': ingredients,
                'recipeInstructions': instructions,
                'currentStep': step
            }
        )
    except: #print the exception if saving fails for some reason (not ever supposed to)
        e = sys.exc_info()[0]
        print(e)

def loadRecipeData(userId):
    try: #try to load the recipe corresponding to the user of this Amazon device
        table = dynamodbResource.Table(TABLE_NAME_FOR_ANY_ACCOUNT)
        recipeGet = table.get_item(
            Key={    #we get the item by its key, which is the user id of the device (every device gets a user id)
                'userId': userId
            }
        )
    except:
        e = sys.exc_info()[0]
        print(e)
    else:
        item = recipeGet['Item']   #if saving works we get the item from the given dictionary
        recipeJSON = json.dumps(item, indent=4, cls=DecimalEncoder)  #make it a string
        return json.loads(recipeJSON) #make it JSON
