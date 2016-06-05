from __future__ import print_function
import unirest, json

# --------------- Request handler ------------------
def lambdaHandler(event, context):
    print("event.session.application.applicationId=" +
          event['session']['application']['applicationId'])

    #check if the application id matches the session id
    if (event['session']['application']['applicationId'] != "amzn1.echo-sdk-ams.app.[unique-value-here]"):
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
    speech_output = "Let's start cooking!" + "First, tell me what you want to make."
    text_output = "Let's start cooking!" + "First, tell me what you want to make."
    reprompt_text = "Sorry, I didn't get that." + "Tell me what you want to make."
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


#returns the recipe asked for in the intent
def getRecipe(intent, session):

    card_title = intent['name']
    session_attributes = {}
    should_end_session = False

    #if the recipe name exists in the list of recipes (slots list is specified in Amazon developer console)
    if 'Recipe' in intent['slots']:
        recipeName = intent['slots']['Recipe']['value'] #store the name of the recipe

        #using Food2Fork API to get recipe matching to name
        searchUrl = "http://food2fork.com/api/search?key=eabccd215340a8555c74ca4c1b91d0c5&page=1&q=" + recipeName
        response = unirest.get(searchUrl)
        data = response.body
        getUrl = data['recipes'][0]['source_url']

        #using Spoonacular API to extract recipe ingredients and instructions for the recipe URL fetched with Food2Fork
        newGetUrl = "https://spoonacular-recipe-food-nutrition-v1.p.mashape.com/recipes/extract?forceExtraction=false&url=" + getUrl
        fullRecipeResponse = unirest.get(newGetUrl, headers={"X-Mashape-Key": "ZdI3P7OSmGmshXpO0mDVMDVndgoop1jjFIGjsnJBkk43YdMgsm"})
        recipeData = fullRecipeResponse.body #store the json body of the response to the get request

        #if the data is not empty
        if recipeData:
            #create an empty ingredients list and add each ingredient to the list
            recipeIngredients = []
            for ingredient in recipeData['extendedIngredients']:
                ingredientText = ingredient['originalString']
                recipeIngredients.append(ingredientText)

            recipeInstructions = recipeData['text']
            #some recipe instructions don't exist, so if they do, store them and divide them into parts
            if recipeInstructions:
                instructionsList = recipeInstructions.split('.');
            #instructionsList = [x for x in map(str.strip, recipeInstructions.split('.')) if x]

            #set the session attributes and card title for the companion app
            session_attributes["recipeName"] = recipeName
            card_title = "Ingredients for " + recipeName
            session_attributes["recipeInstructions"] = instructionsList
            session_attributes["recipeFound"] = True
            session_attributes["recipeIngredients"] = recipeIngredients

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
    print(currentStep)
    card_title = "Step " + `currentStep + 1`

    if currentStep > 0 and currentStep < len(recipeText):

        session_attributes["currentStep"] = currentStep #save the current step to the session attributes
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
