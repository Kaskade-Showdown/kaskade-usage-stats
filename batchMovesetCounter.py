#!/usr/bin/python
#File I/O is going to be the main bottleneck. Doing moveset counting in batch (a folder at a time, rather than log by log)
#should be much more efficient, as keylookup.pickle need only be loaded once per run.
# Switch from pickle to json so it can be created by JS

import sys
import math
import pickle as pickle
import json
import gzip
import os
import math

from common import keyify,weighting,readTable,aliases,victoryChance
from TA import nmod,statFormula,baseStats

def movesetCounter(filename, cutoff, teamtype, usage, movesetsfile):
	file = gzip.open(filename,'rb')
	raw = file.read()
	file.close()
	raw = raw.decode("utf-8")

	raw=raw.split('][')
	for i in range(len(raw)):
		if (i>0):
			raw[i]='['+raw[i]
		if (i<len(raw)-1):
			raw[i]=raw[i]+']'

	species = keyLookup[filename[filename.rfind('/')+1:]]
	for alias in aliases:
		if species in aliases[alias]:
			species = alias
			break

	bias = []
	stalliness = []
	abilities = {}
	items = {}
	happinesses = {}
	spreads = {}
	moves = {}
	movesets = []
	weights = []
	rawCount = 0
	gxes={}
	
	for line in raw:
		movesets = json.loads(line)
		for moveset in movesets:
			if teamtype:
				if teamtype not in moveset['tags']:
					continue
			rawCount = rawCount+1
			weight=weighting(1500.0,130.0,cutoff)
			if 'rating' in list(moveset.keys()):
				if 'rpr' in list(moveset['rating'].keys()) and 'rprd' in list(moveset['rating'].keys()):
					gxe = victoryChance(moveset['rating']['rpr'],moveset['rating']['rprd'],1500.0,130.0)
					gxe=int(round(100*gxe))

					addMe=True
					if moveset['trainer'] in gxes:
						if gxes[moveset['trainer']] > gxe:
							addMe = False
					if addMe:
						gxes[moveset['trainer']]=gxe

					if moveset['rating']['rprd'] != 0.0:
						weight=weighting(moveset['rating']['rpr'],moveset['rating']['rprd'],cutoff)
						weights.append(weight)
			elif 'outcome' in list(moveset.keys()):
				if moveset['outcome'] == 'win':
					weight=weighting(1540.16061434,122.858308077,cutoff)
				elif moveset['outcome'] == 'loss':
					weight=weighting(1459.83938566,122.858308077,cutoff)
				#else it's a tie, and we use 1500
			if moveset['ability'] not in keyLookup:
				moveset['ability'] = 'illuminate'
			if moveset['ability'] not in abilities:
				abilities[moveset['ability']] = 0.0
			abilities[moveset['ability']] = abilities[moveset['ability']] + weight

			if moveset['item'] not in keyLookup:
				moveset['item'] = 'nothing'
			if moveset['item'] not in items:
				items[moveset['item']] = 0.0
			items[moveset['item']] = items[moveset['item']] + weight

			if moveset['nature'] in ['serious','docile','quirky','bashful'] or moveset['nature'] not in keyLookup:
				nature = 'hardy'
		
			#round the EVs
			for stat in list(moveset['evs'].keys()):
				ev=moveset['evs'][stat]
				if species == 'shedinja' and stat == 'hp':
					stat = 1
					moveset['evs']['stat']=0
					continue
			
				if stat == 'hp':
					n=-1
				else:
					n=nmod[moveset['nature']][{'atk': 0, 'def': 1, 'spa': 2, 'spd': 3, 'spe': 4}[stat]]
				x = statFormula(baseStats[keyify(species)][stat],moveset['level'],n,moveset['ivs'][stat],ev)

				while ev > 0:
					if x != statFormula(baseStats[keyify(species)][stat],moveset['level'],n,moveset['ivs'][stat],ev-1):
						break
					ev = ev-1
			
			moveset['evs'][stat]=ev

			spread = keyLookup[moveset['nature']]+':'
			for stat in ['hp','atk','def','spa','spd']:
				spread=spread+str(moveset['evs'][stat])+'/'
			spread=spread+str(moveset['evs']['spe'])
			if spread not in spreads:
				spreads[spread] = 0.0
			spreads[spread] += weight

			for move in moveset['moves']:
				if move in keyLookup:
					#I think it's valid to triple-count 'nothing' right now
					#if keyLookup[move]=='Nothing':
					#	continue
					if move not in moves:
						moves[move] = 0.0
					moves[move] += weight

			happiness = moveset['happiness']
			if happiness not in list(happinesses.keys()):
				happinesses[happiness]=0.0
			happinesses[happiness]+=weight

	count = sum(abilities.values())
	gxes=list(reversed(sorted(gxes.values())))

	#teammate stats
	try:
		teammates = teammateMatrix[species]
	except KeyError:
		sys.stderr.write('No teammates data for '+filename+' ('+str(cutoff)+')\n')
		teammates={}
	for s in teammates:
		if s not in list(usage.keys()):
			teammates[s]=0.0
		else:
			teammates[s]=teammates[s]-(count*usage[s])

	#checks and counters
	cc={}
	if species in list(encounterMatrix.keys()):
		for s in list(encounterMatrix[species].keys()):
			matchup = encounterMatrix[species][s]
			#number of times species is KOed by s + number of times species switches out against s over number of times
			#either (or both) is switched out or KOed (don't count u-turn KOs or force-outs)
			n=sum(matchup[0:6])
			if n>20:
				p=float(matchup[0]+matchup[3])/n
				d=math.sqrt(p*(1.0-p)/n)
				#cc[s]=p-4*d #using a CRE-style calculation
				cc[s]=[n,p,d]

	maxGXE = [0,0,0,0]
	if len(gxes) > 0:
		maxGXE = [len(gxes),gxes[0],gxes[int(math.ceil(0.01*len(gxes)))-1],gxes[int(math.ceil(0.20*len(gxes)))-1]]

	stuff = {
		'Raw count': rawCount,
		'Viability Ceiling': maxGXE,
		'Abilities': abilities,
		'Items': items,
		'Spreads': spreads,
		'Moves': moves,
		'Happiness' : happinesses,
		'Teammates': teammates}
	if cc:
		stuff['Checks and Counters'] = cc

	#print tables
	tablewidth = 40

	separator = ' +'
	for i in range(tablewidth):
		separator = separator + '-'
	separator = separator + '+ \n'
	movesetsfile.write(separator)

	line = ' | '+species
	for i in range(len(species),tablewidth-1):
		line = line + ' '
	line = line + '| \n'
	movesetsfile.write(line)

	movesetsfile.write(separator)

	line = ' | Raw count: %d'%(rawCount)
	while len(line) < tablewidth+2:
		line = line + ' '
	line = line + '| \n'
	movesetsfile.write(line)
	line = ' | Viability Ceiling: %d'%(maxGXE[1])
	while len(line) < tablewidth+2:
		line = line + ' '
	line = line + '| \n'
	movesetsfile.write(line)

	movesetsfile.write(separator)

	# Generate Json
	pokeDict = dict()
	pokeDict["ability"] = keyLookup[max(stuff['Abilities'], key=stuff['Abilities'].get)]
	pokeDict["item"] = keyLookup[max(stuff['Items'], key=stuff['Items'].get)]
	if pokeDict["item"] == "Nothing": pokeDict["item"] = ""
	moveList = list() 
	for move in sorted(stuff["Moves"], key=stuff["Moves"].get, reverse=True):
		if len(moveList) == 4: break
		if (keyLookup[move] == "Nothing"): continue
		moveList.append(keyLookup[move])
	pokeDict["moves"] = moveList
	spread = max(stuff['Spreads'], key=stuff['Spreads'].get)
	pokeDict["nature"] = spread.split(":")[0]
	evList = spread.split(":")[1].split("/")
	evNames = ['hp', 'atk', 'def', 'spa', 'spd', 'spe']
	evDict = dict()
	for k,v in zip(evNames, evList):
		v = int(v)
		if v > 0:
			evDict[k] = v
	pokeDict["evs"] = evDict


	for x in ['Abilities','Items','Spreads','Moves','Teammates','Checks and Counters']:
		if x not in stuff:
			continue
		table = []
		line = ' | '+x
		while len(line) < tablewidth+2:
			line = line + ' '
		line = line + '| \n'
		movesetsfile.write(line)


		for i in stuff[x]:
			if (x in ['Spreads', 'Teammates','Checks and Counters']):
				table.append([i,stuff[x][i]])
			else:
				table.append([keyLookup[i],stuff[x][i]])
		if x == 'Checks and Counters':
			table=sorted(table, key=lambda table:-(table[1][1]-4.0*table[1][2]))
		else:
			table=sorted(table, key=lambda table:-table[1])
		total = 0.0
		for i in range(len(table)): 
			if (total > .95 and x != 'Abilities') or (x == 'Abilities' and i>5) or (x == 'Spreads' and i>5) or (x == 'Teammates' and i>11) or (x == 'Checks and Counters' and i>11):
				if x == 'Moves':
					line = ' | %s %6.3f%%' % ('Other',400.0*(1.0-total))
				elif x not in ['Teammates','Checks and Counters']:
					line = ' | %s %6.3f%%' % ('Other',100.0*(1.0-total))
			else:
				if x == 'Checks and Counters':
					matchup = encounterMatrix[species][table[i][0]]
					n=sum(matchup[0:6])
					score=float(table[i][1][1])-4.0*table[i][1][2]
					if score < 0.5:
						break
					
					line = ' | %s %6.3f (%3.2f\u00b1%3.2f)' % (table[i][0],100.0*score,100.0*table[i][1][1],100*table[i][1][2])
					while len(line) < tablewidth+1:
						line = line + ' '
					line=line+' |\n |\t (%2.1f%% KOed / %2.1f%% switched out)' %(float(100.0*matchup[0])/n,float(100.0*matchup[3])/n)
					if float(100.0*matchup[0])/n < 10.0:
						line = line+' '
					if float(100.0*matchup[3])/n < 10.0:
						line = line+' '
				elif x == 'Teammates':
					line = ' | %s %+6.3f%%' % (table[i][0],100.0*table[i][1]/count)
					if table[i][1] < 0.005*count:
						break
				else:
					line = ' | %s %6.3f%%' % (table[i][0],100.0*table[i][1]/count)
			while len(line) < tablewidth+2:
				line = line + ' '
			line = line + '| '
			movesetsfile.write(line + '\n')
			if (total > .95 and x != 'Abilities') or (x == 'Abilities' and i>5) or (x == 'Spreads' and i>5) or (x == 'Teammates' and i>10) or (x == 'Checks and Counters' and i>10):
				break
			if x == 'Moves':
				total = total + float(table[i][1])/count/4.0
			elif x == 'Teammates':
				total = total + float(table[i][1])/count/5.0
			elif x != 'Checks and Counters':
				total = total + float(table[i][1])/count
		movesetsfile.write(separator)
	return stuff, pokeDict

file = open('keylookup.json', 'rb')
keyLookup = json.load(file)
file.close()
keyLookup['nothing']='Nothing'
keyLookup['']='Nothing'

cutoff = 0
cutoffdeviation = 0
teamtype = None
tier = str(sys.argv[1])

if (len(sys.argv) > 2):
	cutoff = float(sys.argv[2])
	if (len(sys.argv) > 3):
		teamtype = keyify(sys.argv[3])

specs = '-'
if teamtype:
	specs += teamtype+'-'
specs += '{:.0f}'.format(cutoff)

filename="Stats/movesets/"+tier+specs+".txt"
d = os.path.dirname(filename)
if not os.path.exists(d):
	os.makedirs(d)
movesetsfile=open(filename,'w')

file = open('Raw/moveset/'+tier+'/teammate'+specs+'.pickle', 'rb')
teammateMatrix = pickle.load(file)
file.close()

file = open('Raw/moveset/'+tier+'/encounterMatrix'+specs+'.pickle', 'rb')
encounterMatrix = pickle.load(file)
file.close()

filename = 'Stats/'+tier+specs+'.txt'
file = open(filename)
table=file.readlines()
file.close()

usage,nBattles = readTable('Stats/'+tier+specs+'.txt')

pokes = []
for poke in list(usage.keys()):
	pokes.append([poke,usage[poke]])
if tier in ['randombattle','challengecup','challengecup1v1','seasonal']:
	pokes=sorted(pokes)
else:
	pokes=sorted(pokes, key=lambda pokes:-pokes[1])

chaos = {'info': {'metagame': tier, 'cutoff': cutoff, 'cutoff deviation': cutoffdeviation, 'team type': teamtype, 'number of battles': nBattles},'data':{}}
showdownDict = dict()
for poke in pokes:
	if poke[1] < 0.0001: #1/100th of a percent
		break
	stuff, pokeDict = movesetCounter('Raw/moveset/'+tier+'/'+keyify(poke[0]),cutoff,teamtype,usage,movesetsfile)
	showdownDict[poke[0]] = {"Showdown Usage": pokeDict}
	stuff['usage']=poke[1]
	chaos['data'][poke[0]]=stuff

filename="Stats/movesets/"+tier+specs+".json"
with open(filename, "w") as outfile:
    outfile.write(json.dumps(showdownDict))


filename="Stats/chaos/"+tier+specs+".json"
d = os.path.dirname(filename)
if not os.path.exists(d):
	os.makedirs(d)
file=open(filename,'w')
file.write(json.dumps(chaos))
file.close()	

movesetsfile.close()


# Generate Damage Calc import
filename="Stats/movesets/"+tier+specs+"_calc.txt"
d = os.path.dirname(filename)
dCalcFile=open(filename,'w')

if 'vgc' in tier:
	level = 50
else:
	level = 100

for poke in showdownDict:
	d = showdownDict[poke]["Showdown Usage"]
	dCalcFile.write(f"{poke} @ {d['item']}\n")
	dCalcFile.write(f"Ability: {d['ability']}\n")
	dCalcFile.write(f"Level: {level}\n")
	dCalcFile.write(f"EVs: {d['evs'].get('hp',0)} HP / {d['evs'].get('atk',0)} Atk / {d['evs'].get('def',0)} Def / {d['evs'].get('spa',0)} SpA / {d['evs'].get('spd',0)} SpD / {d['evs'].get('spe',0)} Spe\n")
	dCalcFile.write(f"{d['nature']} Nature\n")
	for move in d['moves']:
		dCalcFile.write(f"- {move}\n")
	dCalcFile.write("\n")

dCalcFile.close()
