#!/usr/bin/python
# -*- coding: latin-1 -*-
#Loads an intermediate battle summary file created by LogReader and compiles usage and metagame stats, which
#are written to the appropriate folders. Also, if the user so wants, the script will generate a "matchup matrix"
#which looks at what happens when Pokemon X meets up with Pokemon Y. This could conceivably be used to come up
#with a statistical list of best checks and counters for each Pokemon, but I haven't yet made that script.

#encounterMatrix key: for entries encounterMatrix[poke1][poke2][i], i=...
#0: poke1 was KOed
#1: poke2 was KOed
#2: double down
#3: poke1 was switched out
#4: poke2 was switched out
#5: double switch
#6: poke1 was forced out
#7: poke2 was forced out
#8: poke1 was u-turn KOed
#9: poke2 was u-turn KOed
#10: poke1 was foddered
#11: poke2 was foddered
#12: no clue what happened

import sys
import pickle as pickle
import os
import json
import gzip

from common import *

#this is a lookup table for the outcomes if poke1 and poke2 were exchanged
otherGuy = [1,0,2,4,3,5,7,6,9,8,11,10,12]



tier = str(sys.argv[1])
cutoff = 0 #this is our default, but we can change it for '1337' stats
teamtype = None

if len(sys.argv) > 2:
	cutoff = float(sys.argv[2])
	if len(sys.argv) > 3:
		teamtype = keyify(sys.argv[3])

specs = '-'
if teamtype:
	specs += teamtype+'-'
specs += '{:.0f}'.format(cutoff)

filename="Raw/"+tier#+".txt"
file = gzip.open(filename,'rb')

filename="Stats/"+tier+specs+".txt"
d = os.path.dirname(filename)
if not os.path.exists(d):
	os.makedirs(d)
usagefile=open(filename,'w')
filename="Stats/metagame/"+tier+specs+".txt"
d = os.path.dirname(filename)
if not os.path.exists(d):
	os.makedirs(d)
if tier not in ["1v1", "challengecup1vs1"]:
	metagamefile=open(filename,'w')
else:
	metagamefile=False
filename="Raw/moveset/"+tier+"/teammate"+specs+".pickle"
teammatefile=open(filename,'wb')
filename="Raw/moveset/"+tier+"/encounterMatrix"+specs+".pickle"
encounterfile=open(filename,'wb')


battleCount = 0
teamCount = 0
counter = {'raw': {}, 'real': {}, 'weighted': {}, 'wins': {}, 'uniqueWins': {}, 'unique': {}}
leadCounter = {'raw': {}, 'weighted': {}, 'wins': {}}
#We're not doing these right now
#turnCounter = {}
#KOcounter = {}
#TCsquared = {} #for calculating std. dev
#KCsquared = {} #	"
encounterMatrix = {}
teammateMatrix = {}
tagCounter = {}
stallCounter = []
ratingCounter = []
weightCounter = []
WLratings = {'win':[],'loss':[]}
weatherTags = {
	'sun', 'rain', 'hail', 'bloodmoon', 'fog',
	'sand', 'dust', 'pollen', 'pheromones', 'smog', 'fairydust',
	'battleaura', 'pactivity', 'dreamscape', 'dragonforce', 'thunderstorm', 'magnetosphere',
	'strongwinds', 'allweather', 'multiweather', 'weatherless',
	'tricksun', 'trickrain', 'trickhail', 'trickbloodmoon', 'trickfog',
	'tricksand', 'trickdust', 'trickpollen', 'trickpheromones', 'tricksmog', 'trickfairydust',
	'trickbattleaura', 'trickpactivity', 'trickdreamscape', 'trickdragonforce', 'trickthunderstorm',
	'trickmagnetosphere', 'trickstrongwinds',
	'sunoffense', 'rainoffense', 'hailoffense', 'bloodmoonoffense', 'fogoffense',
	'sandoffense', 'dustoffense', 'pollenoffense', 'pheromonesoffense', 'smogoffense',
	'fairydustoffense', 'battleauraoffense', 'pactivityoffense', 'dreamscapeoffense',
	'dragonforceoffense', 'thunderstormoffense', 'magnetosphereoffense', 'strongwindsoffense',
	'sunstall', 'rainstall', 'hailstall', 'bloodmoonstall', 'fogstall',
	'sandstall', 'duststall', 'pollenstall', 'pheromonesstall', 'smogstall',
	'fairyduststall', 'battleaurastall', 'pactivitystall', 'dreamscapestall',
	'dragonforcestall', 'thunderstormstall', 'magnetospherestall', 'strongwindsstall',
	'sandfear', 'hailfear',
}

def writeTagTable(metagamefile, title, tags, totalWeight):
	if not tags:
		return
	metagamefile.write(title+'\n')
	for i in range(0,len(tags)):
		line = ' '+tags[i][0]
		for j in range(len(tags[i][0]),30):
			line = line + '.'
		line = line + '%8.5f%%' % (100.0*tags[i][1]/max(1.0,totalWeight))
		metagamefile.write(line+'\n')
	metagamefile.write('\n')

t=tier
if tier.endswith('suspecttest'):
	t=t[:-11]

for line in file:
	#print line
	battles = json.loads(line)

	for battle in battles:

		weight={}
		if 'turns' in list(battle.keys()) and t not in non6v6Formats:
			if battle['turns'] < 3 and t not in nonSinglesFormats:
				continue
			elif battle['turns'] < 2:
				continue
		for player in ['p1','p2']:
			if teamtype:
				if teamtype not in battle[player]['tags']:
					continue
			enemy_team = list()
			for enemy_player in {'p1','p2'} - {player}:
				for poke in battle[enemy_player]['team']:
					species = poke['species']
					for alias in aliases:
						if species in aliases[alias]:
							species = alias
							break
					enemy_team.append(species)
			team = []
			if 'rating' in list(battle[player].keys()):
				if 'rpr' in list(battle[player]['rating'].keys()) and 'rprd' in list(battle[player]['rating'].keys()):
					if battle[player]['rating']['rprd'] != 0.0:
						weight[player] = weighting(battle[player]['rating']['rpr'],battle[player]['rating']['rprd'],cutoff)
						ratingCounter.append(battle[player]['rating'])
				
						if 'outcome' in list(battle[player].keys()):
							WLratings[battle[player]['outcome']].append([battle[player]['rating']['rpr'],battle[player]['rating']['rprd'],weight[player]])
				
			if player not in list(weight.keys()): #if there's a ladder error, we have no idea what the player's rating is, so treat like a new player
				weight[player] = weighting(1500,130.0,cutoff)

				#try using outcome
				if 'outcome' in list(battle[player].keys()):
					if battle[player]['outcome'] == 'win':
						weight[player] = weighting(1540.16061434,122.858308077,cutoff)
					elif battle[player]['outcome'] == 'loss':
						weight[player] = weighting(1459.83938566,122.858308077,cutoff)

			weightCounter.append(weight[player])

			for poke in battle[player]['team']:
				#annoying alias shit
				species = poke['species']
				for alias in aliases:
					if species in aliases[alias]:
						species = alias
						break

				team.append(species)

				#if species not already in the tables, you gotta add them
				if species not in list(counter['raw'].keys()):
					counter['raw'][species]=0.0
					counter['real'][species]=0.0
					counter['uniqueWins'][species]=0.0
					counter['unique'][species]=0.0
					counter['weighted'][species]=0.0
					counter['wins'][species]=0.0
			
				#count usage
				counter['raw'][species]=counter['raw'][species]+1.0
				if poke['turnsOut'] > 0:
					counter['real'][species]=counter['real'][species]+1.0
					# unqiue
					if species not in enemy_team:
						counter['unique'][species]=counter['unique'][species]+1.0
						if 'outcome' in list(battle[player].keys()):
							if battle[player]['outcome'] == 'win':
								counter["uniqueWins"][species] = counter["uniqueWins"][species] + 1
						else:
							counter["uniqueWins"][species] = counter["uniqueWins"][species] + 0.5
				counter['weighted'][species]=counter['weighted'][species]+weight[player]
				if 'outcome' in list(battle[player].keys()):
					if battle[player]['outcome'] == 'win':
						counter["wins"][species] = counter["wins"][species] + 1
				else:
					counter["wins"][species] = counter["wins"][species] + 0.5

				if metagamefile:
					#count metagame stuff
					for tag in battle[player]['tags']:
						if tag not in list(tagCounter.keys()):
							tagCounter[tag] = 0.0
						tagCounter[tag] = tagCounter[tag]+weight[player] #metagame stuff is weighted
					stallCounter.append([battle[player]['stalliness'],weight[player]])

			teamCount = teamCount + 1

			#teammate stats
			for i in range(len(team)):
				for j in range(i):
					if team[i] not in list(teammateMatrix.keys()):
						teammateMatrix[team[i]]={}
					if team[j] not in list(teammateMatrix.keys()):
						teammateMatrix[team[j]]={}
					if team[j] not in list(teammateMatrix[team[i]].keys()):
						teammateMatrix[team[i]][team[j]]=0.0
					teammateMatrix[team[i]][team[j]]=teammateMatrix[team[i]][team[j]]+weight[player] #teammate stats are weighted
					teammateMatrix[team[j]][team[i]]=teammateMatrix[team[i]][team[j]] #nice symmetric matrix

		if t not in nonSinglesFormats: #lead stats for doubles is not currently supported
			#lead stats
			leads=['empty','empty']
			if len(battle['matchups'])==0:
				#this happens if the player forfeits after six turns and no switches--rare but possible
				for i in range(2):
					for poke in battle[['p1','p2'][i]]['team']:
						if poke['turnsOut'] > 0:
							leads[i] = poke['species']
							break
			else:
				for i in range(2):
					#it is utterly imperative that the p1 lead is first and the p2 lead second
					leads[i] = battle['matchups'][0][i]

			if 'empty' in leads:
				if len(battle['matchups']) == 0: #1v1 (or similiar) battle forfeited before started
					continue
				print("Something went wrong.")
				print(battle)

			for i in range(2):
				player = ['p1','p2'][i]
				if player not in weight:
					continue
				species = leads[i]
				#annoying alias shit
				for alias in aliases:
					if species in aliases[alias]:
						species = alias
						break
				if species not in list(leadCounter['raw'].keys()):
					leadCounter['raw'][species]=0.0
					leadCounter['weighted'][species]=0.0
					leadCounter['wins'][species]=0.0

				leadCounter['raw'][species]=leadCounter['raw'][species]+1.0
				leadCounter['weighted'][species]=leadCounter['weighted'][species]+weight[['p1','p2'][i]]
				if 'outcome' in list(battle[player].keys()):
					if battle[player]['outcome'] == 'win':
						leadCounter["wins"][species] = leadCounter["wins"][species] + 1
				else:
					leadCounter["wins"][species] = leadCounter["wins"][species] + 0.5

			#encounter Matrix
			if not teamtype:
				w=min(weight.values())
				for matchup in battle['matchups']:
					if matchup[0] not in list(encounterMatrix.keys()):
						encounterMatrix[matchup[0]]={}
					if matchup[1] not in list(encounterMatrix.keys()):
						encounterMatrix[matchup[1]]={}
					if matchup[1] not in list(encounterMatrix[matchup[0]].keys()):
						encounterMatrix[matchup[0]][matchup[1]]=[0 for k in range(13)]
						encounterMatrix[matchup[1]][matchup[0]]=[0 for k in range(13)]
					encounterMatrix[matchup[0]][matchup[1]][matchup[2]]=encounterMatrix[matchup[0]][matchup[1]][matchup[2]]+w #encounter Matrix is weighed
					encounterMatrix[matchup[1]][matchup[0]][otherGuy[matchup[2]]]=encounterMatrix[matchup[1]][matchup[0]][otherGuy[matchup[2]]]+w #by the inferior player

		battleCount = battleCount + 1
	
file.close()
total={}
for i in ['raw','real','weighted', 'unique', 'uniqueWins']:
	total[i] = sum(counter[i].values())

pokedict = {}
for i in list(counter['raw'].keys()):
	pokedict[i]=[counter['raw'][i],counter['real'][i],counter['weighted'][i], counter["wins"][i], counter["unique"][i], counter["uniqueWins"][i]]

if 'empty' in list(pokedict.keys()): #delete no-entry slot
		del pokedict['empty']

pokes = []
for i in pokedict:
	pokes.append([i]+pokedict[i])


#write teammates and encounter matrix to file
pickle.dump(teammateMatrix,teammatefile)
teammatefile.close()
pickle.dump(encounterMatrix,encounterfile)
encounterfile.close()

#sort by weighted usage
# if tier in ['challengecup1v1','1v1']:
if tier in ['challengecup1v1','1v1'] or 'vgc' in tier:
	pokes=sorted(pokes, key=lambda pokes:-pokes[2])
else:
	pokes=sorted(pokes, key=lambda pokes:-pokes[3])
p=[]
usagefile.write(" Total battles: "+str(battleCount)+"\n")
usagefile.write(" + ---- + ------------------ + --------- + ------ + -------- + ----- + -------- + \n")
usagefile.write(" | Rank | Pokemon            | Usage %   | Raw    | Win Rate | True  | True WR% | \n")
usagefile.write(" + ---- + ------------------ + --------- + ------ + -------- + ----- + -------- + \n")
for i in range(0,len(pokes)):
	if pokes[i][1] == 0:
		break
	trueWR = 100*pokes[i][6]/pokes[i][5] if pokes[i][5] else 0
	usagefile.write(' | %-4d | %-18s | %8.4f%% | %-6d | %7.3f%% | %-5d | %7.3f%% | \n' % (i+1, pokes[i][0], 100.0*pokes[i][3]/max(total['weighted'],1.0)*6.0, pokes[i][1], 100*pokes[i][4]/pokes[i][1], pokes[i][2], trueWR))
	p.append(pokes[i])
usagefile.write(" + ---- + ------------------ + --------- + ------ + -------- + ----- + -------- + \n")
usagefile.close()

if t not in nonSinglesFormats and t not in ['1v1','challengecup1vs1']: #lead stats for doubles is not currently supported
	#lead analysis

	filename="Stats/leads/"+tier+specs+".txt"
	d = os.path.dirname(filename)
	if not os.path.exists(d):
		os.makedirs(d)
	leadsfile=open(filename,'w')

	pokedict = {}
	for i in list(leadCounter['raw'].keys()):
		pokedict[i]=[leadCounter['raw'][i], leadCounter['weighted'][i], leadCounter['wins'][i]]
	if 'empty' in list(pokedict.keys()): #delete no-entry slot
			del pokedict['empty']
	pokes = []
	for i in pokedict:
		pokes.append([i]+pokedict[i])
	pokes=sorted(pokes, key=lambda pokes:-pokes[2])
	leadsfile.write(" Total leads: "+str(battleCount*2)+"\n")
	leadsfile.write(" + ---- + ------------------ + --------- + ------ + -------- + \n")
	leadsfile.write(" | Rank | Pokemon            | Usage %   | Raw    | Win Rate | \n")
	leadsfile.write(" + ---- + ------------------ + --------- + ------ + -------- + \n")
	for i in range(0,len(pokes)):
		if pokes[i][1] == 0:
			break
		leadsfile.write(" | %-4d | %-18s | %8.5f%% | %-6d | %7.3f%% | \n" % (i+1, pokes[i][0], 100.0*pokes[i][2]/max(1.0,sum(leadCounter['weighted'].values())), pokes[i][1], 100*pokes[i][3]/pokes[i][1]))
	leadsfile.write(" + ---- + ------------------ + --------- + ------ + ------- + \n")
	leadsfile.close()

#metagame analysis
if metagamefile:
	teamTags = []
	weather = []
	for tag in tagCounter:
		if tag in weatherTags:
			weather.append([tag,tagCounter[tag]])
		else:
			teamTags.append([tag,tagCounter[tag]])
	teamTags=sorted(teamTags, key=lambda tags:-tags[1])
	weather=sorted(weather, key=lambda tags:-tags[1])

	writeTagTable(metagamefile, 'Team types', teamTags, total['weighted'])
	writeTagTable(metagamefile, 'Weather', weather, total['weighted'])

	#stalliness
	stallCounter=sorted(stallCounter, key=lambda stallCounter:stallCounter[0])

	if stallCounter:
		#figure out a good bin range by looking at .1% and 99.9% points
		low = stallCounter[len(stallCounter)//1000][0]
		high = stallCounter[len(stallCounter)-len(stallCounter)//1000-1][0]
		

		nbins = 13 #this is actually only a rough idea--I think it might be the minimum?

		if (low > 0):
			low = 0.0
		elif (high < 0):
			high = 0.0

		binSize = (high-low)/(nbins-1)
		#this is bound to be an ugly number, so let's make it pretty
		for x in [10,5,2.5,2,1.5,1,0.5,0.25,0.2,0.1,0.05]:
			if binSize > x:
				break
		#if binSize < 0.05, fuck it--I'm not zooming in any further
		binSize = x
		histogram = [[0.0,0]]
		x=binSize
		while x+binSize/2 < high:
			histogram.append([x,0])
			x=x+binSize
		x=-binSize
		while x-binSize/2 > low:
			histogram.append([x,0])
			x=x-binSize
		histogram=sorted(histogram, key=lambda histogram:histogram[0])
		nbins = len(histogram)

		for start in range(len(stallCounter)):
			# TODO: Is this correct?
			if max(stallCounter[start]) >= histogram[0][0]-binSize/2:
				break

		j=0
		for i in range(start,len(stallCounter)):
			while stallCounter[i][0] > histogram[0][0]+binSize*(j+0.5):
				j=j+1
			if j>=len(histogram):
				break
			histogram[j][1] = histogram[j][1]+stallCounter[i][1]

		maximum = 0
		for i in range(len(histogram)):
			if histogram[i][1] > maximum:
				maximum = histogram[i][1]

		nblocks = 30 #maximum number of blocks to go across
		blockSize = maximum/nblocks

		if blockSize > 0:
			x=0.0
			y=0.0
			for score in stallCounter:
				x=x+score[0]*score[1]
				y=y+score[1]	

			#print histogram
			metagamefile.write(' Stalliness (mean: %6.3f)\n'%(x/y))
			for i in range(len(histogram)):
				if histogram[i][0]%(2.0*binSize) < binSize/2:
					line = ' '
					if histogram[i][0]>0.0:
						line=line+'+'
					elif histogram[i][0] == 0.0:
						line=line+' '
					line = line+'%3.1f|'%(histogram[i][0])
				else:
					line = '     |'
				for j in range(int((histogram[i][1]+blockSize/2)/blockSize)):#poor man's rounding
					line = line + '#'
				metagamefile.write(line+'\n')
			metagamefile.write(' more negative = more offensive, more positive = more stall\n')
			metagamefile.write(' one # = %5.2f%%\n'%(100.0*blockSize/y))

	metagamefile.close()
