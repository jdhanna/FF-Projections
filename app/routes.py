from flask import render_template
from app import app

from datetime import datetime
import requests
import json
from scipy.stats import norm

leagueIden = 157162

def checkResponseCode(code):
    if code != 200:
        print("There was a problem with the API pull. Error code:", response.status_code)
        if code == 301:
            print("Code 301 indicates that the API has changed its layout and we are using an outdated layout")
        if code == 400:
            print("Code 400 indicates there's a syntax error in the submission")
        if code == 401:
            print("Code 401 indicates that our authentication controls aren't valid")
        if code == 403:
            print(
                "Code 403 indicates that our credentials are valid, we just don't have the server side permission to access this")
        if code == 404:
            print(
                "Code 404 indicates that the API call was refused, probably because it tried to check an invalid address")
        if code == 503:
            print(
                "Code 503 indicates that the server is busy or overloaded at the moment, and can't honor the call")
        return
    return


def jprint(obj):
    text = json.dumps(obj, sort_keys=True, indent=4)
    print(text)


def sigma(position):
    # The purpose of this function is to keep track of the uncertainty in the fleaflicker projections. This data was gathered in the Standard Deviation.py script
    if position == "QB" or "QB/WR":  # Thank you Taysom Hill, for causing this bug.
        return 8.1060
    if position == "RB":
        return 7.3697
    if position == "WR":
        return 7.5289
    if position == "TE":
        return 6.8678
    if position == "K" or "PK":
        return 5.4311
    if position == "D/ST" or "DST":
        return 7.4976
    return "Error"


# 1089771 -- Tyrone
# 1087396 -- John
# 1092956 -- Jacob

# QB Data
# Average Projection Error: 0.4440
# Standard Deviation of Error: 8.1060

# RB Data
# Average Projection Error: -0.7285
# Standard Deviation of Error: 7.3697

# WR Data
# Average Projection Error: -0.9535
# Standard Deviation of Error: 7.5289

# TE Data
# Average Projection Error: -1.0926
# Standard Deviation of Error: 6.8678

# K Data
# Average Projection Error: -0.9036
# Standard Deviation of Error: 5.4311

# DST Data
# Average Projection Error: 2.7709
# Standard Deviation of Error: 7.4976

# League one: RADFFL = 97700
# League two: RUFF = 157162
# League three: TE = 327982

class team:
    def importTeam(self, title, teamId, leagueId=leagueIden):
        self.teamJson = requests.get("https://www.fleaflicker.com/api/FetchRoster",
                                     params={"sport": "NFL", "league_id": leagueId, "team_id": teamId})
        self.setImportedTeam(self.teamJson)
        self.name = title

    def setImportedTeam(self, teamObject):
        size = len(teamObject.json()["groups"][0]["slots"])
        self.roster = list()
        for i in range(0, size):
            starter = player()
            starter.importPlayer(teamObject.json()["groups"][0]["slots"][i])
            self.roster.append(starter)

    def refreshRoster(self):
        # print("Performed for", self.name)
        for item in self.roster:
            item.updateActiveScore()
            item.updateProjection()

    def currentPoints(self):
        sum = 0
        self.refreshRoster()
        for item in self.roster:
            sum += item.pointsScored
        return sum

    def showProjection(self):
        sum = 0
        for myPlayer in self.roster:
            print(myPlayer.name, "is projected to score", myPlayer.projection, "points")
            sum = sum + myPlayer.projection
        print("The team is projected to score: ", sum)

    def updateDistribution(self):
        self.mu = 0
        self.sigmaSquared = 0
        for item in self.roster:
            item.updateActiveScore()
            item.updateProjection()
            self.mu += item.projection
            self.sigmaSquared += item.timeLeft() * (sigma(item.position) ** 2) / 3600

class player:

    # PlayerJson becomes pretty important. This is a guide for reading that:
    # teamObject.json()["groups"][0]["slots"][i] <-- This should represent a single player in the ith slot
    # teamObject is run from earlier as well: requests.get("https://www.fleaflicker.com/api/FetchRoster", params={"sport": "NFL", "league_id": leagueId, "team_id": teamId})

    def importPlayer(self, playerJson):
        self.name = playerJson["leaguePlayer"]["proPlayer"]["nameFull"]
        self.ID = playerJson["leaguePlayer"]["proPlayer"]["id"]
        self.position = playerJson["leaguePlayer"]["proPlayer"]["position"]
        self.teamNFL = playerJson["leaguePlayer"]["proPlayer"]["proTeam"]["abbreviation"]
        self.projection = 0  # This is the fancier projection that will be updated in real time and used to calculate victory likelihood
        self.projectionFF = 0
        if "viewingProjectedPoints" in playerJson["leaguePlayer"]:
            self.projectionFF = playerJson["leaguePlayer"]["viewingProjectedPoints"][
                "value"]  # This is the projection that fleaflicker publishes.
        self.pointRate = self.projectionFF / 3600
        self.pointsScored = 0
        self.data = playerJson

    def updateActiveScore(self):
        if "viewingActualPoints" in self.data["leaguePlayer"]:
            if "value" in self.data["leaguePlayer"]["viewingActualPoints"]:
                self.pointsScored = self.data["leaguePlayer"]["viewingActualPoints"]["value"]
            else:
                if self.data["leaguePlayer"]["viewingActualPoints"]["formatted"] == "—":
                    self.pointsScored = 0
                else:
                    self.pointsScored = int(self.data["leaguePlayer"]["viewingActualPoints"]["formatted"])

    def updateProjection(self, method="simpleLinear"):
        # FleaFlicker is the default method
        # simpleLinear takes the projection from fleaflicker discounts based on the remaining time in the game.linearly discount with remaining time.
        # There may one day be a fancier method
        if method == "FleaFlicker":
            self.projection = self.data["leaguePlayer"]["viewingProjectedPoints"]["value"]
        if method == "simpleLinear":
            if self.position == "D/ST" or self.position == "DST":
                t = self.timeLeft() / 3600
                self.projection = self.projectionFF * (t) + self.pointsScored * (1 - t)
                # print(self.name, "is projected to score", self.projection)
            else:
                self.projection = self.pointRate * self.timeLeft() + self.pointsScored

    def timeLeft(self):
        # print(self.name)
        try:
            temp = self.data["leaguePlayer"]["requestedGames"][0]["game"]
        except KeyError:
            return 0
        if "status" not in temp:
            # This game hasn't started (Need to test if the player is on bye, or injured, something like that)
            return 3600

        if temp["status"] == "FINAL_SCORE":
            return 0

        if temp["status"] == "IN_PROGRESS":
            if "isBetweenSegments" in temp:
                if temp["isBetweenSegments"]:
                    qLeft = max(4 - temp["segment"], 0)
                    # print(self.name, "has", 900*qLeft)
                    return 900 * qLeft
            qLeft = max(4 - temp["segment"], 0)
            return (qLeft * 900) + int(temp["segmentSecondsRemaining"])

class ffGame:
    def __init__(self, homeTeam, awayTeam):
        self.homeTeam = homeTeam
        self.awayTeam = awayTeam

    def updateScore(self):
        self.homeScore = self.homeTeam.currentPoints()
        self.awayScore = self.awayTeam.currentPoints()

    def projectGame(self):
        # Specifically, calculating the likelihood the home team will win.
        self.updateScore()
        self.homeTeam.refreshRoster()
        self.homeTeam.updateDistribution()
        self.awayTeam.refreshRoster()
        self.awayTeam.updateDistribution()
        """
        # Used for testing
        print("Home team mu:", self.homeTeam.mu)
        print("Home team sigmaSquared:", self.homeTeam.sigmaSquared)
        print("Away team mu:", self.awayTeam.mu)
        print("Away team sigmaSquared:", self.awayTeam.sigmaSquared)
        """
        self.newMu = self.homeTeam.mu - self.awayTeam.mu
        self.newSigmaSquared = self.homeTeam.sigmaSquared + self.awayTeam.sigmaSquared
        self.newSigma = self.newSigmaSquared ** 0.5
        self.homeTeamWinProb = 1 - norm.cdf(-self.newMu / max(self.newSigma, 0.0000000001))
        self.homeTeamWinPercent = round(100 * self.homeTeamWinProb)
        self.awayTeamWinPercent = 100 - self.homeTeamWinPercent
        dummyHome = {'teamHome': {'name': self.homeTeam.name, 'odds': str(self.homeTeamWinPercent)}}
        dummyAway = {'teamAway': {'name': self.awayTeam.name, 'odds': str(self.awayTeamWinPercent)}}

        #print(self.homeTeam.name, "has a", str(self.homeTeamWinPercent), "% chance of winning")
        #print(self.awayTeam.name, "has a", str(self.awayTeamWinPercent), "% chance of winning")
        return dummyHome, dummyAway


def checkGames(games):
    parametersTeam = {"sport": "NFL", "league_id": leagueIden}
    response = requests.get("https://www.fleaflicker.com/api/FetchLeagueScoreboard", params=parametersTeam)
    checkResponseCode(response.status_code)
    numGames = len(response.json()["games"])

    for item in range(0, numGames):
        text = "game" + str(item)
        homeTeam = team()
        awayTeam = team()
        homeTeam.importTeam(response.json()["games"][item]["home"]["name"],
                            response.json()["games"][item]["home"]["id"], leagueIden)
        # print(homeTeam.name, "is Loaded")
        awayTeam.importTeam(response.json()["games"][item]["away"]["name"],
                            response.json()["games"][item]["away"]["id"], leagueIden)
        # print(awayTeam.name, "is Loaded")
        entry = {text: ffGame(homeTeam, awayTeam)}
        games.update(entry)


@app.route('/')
@app.route('/index')
def index():

    gamesList = list()
    games = {}
    checkGames(games)

    #print("Current Projections")
    #print("---------------------------------")
    for item in games:
        #print("In Game Number", int(str(item)[-1]) + 1)
        title = "Game " + str(int(str(item)[-1]) + 1)
        dummyGame = {"gameName" : title}
        output = games[item].projectGame()
        dummyGame.update(output[0])
        dummyGame.update(output[1])
        gamesList.append(dummyGame)
        #games[item].projectGame()
        #print("  ")
        now = datetime.now()
        timeString = now.strftime("%b-%d %H:%M")

    return render_template('index.html', Games = gamesList, time = timeString)