#!/usr/bin/env python
import datetime, fcntl, subprocess
import copy, os, pexpect, random, re, sys, time
import pexpect.fdpexpect
import threading

LEFT  = '\033OD'
RIGHT = '\033OC'
NONE  = None

CLEAR = chr(27) + '[2J'

ALLDIRECTIONS = [LEFT, RIGHT] + [NONE] * 14
STEPSPERGENERATION = 20000
POPULATIONSIZE = 8
GENERATIONS = 700
MUTATIONRATE = 0.1
ELITEMUTATIONRATE = 0.03

hostname = 'localhost'
username = 'sgle'
command = 'DISPLAY=:0 setsid -w ssh -t -t ' + username + '@' + hostname

ttyc = '/dev/pts/' + sys.argv[1]
fdtty = os.open(ttyc, os.O_RDWR|os.O_NONBLOCK|os.O_NOCTTY)
resultscreen = pexpect.fdpexpect.fdspawn(fdtty)
resultscreen.send(CLEAR)

ttys = '/dev/pts/' + sys.argv[2]
fdttys = os.open(ttys, os.O_RDWR|os.O_NONBLOCK|os.O_NOCTTY)
statusscreen= pexpect.fdpexpect.fdspawn(fdttys)
statusscreen.send(CLEAR)
statusscreen.send('\n')


class Logic(object):
    def __init__(self):
        self.currentStep = 0
        self.directions = []
        self.survivor = STEPSPERGENERATION
        for _ in range(STEPSPERGENERATION):
            self.directions.append(random.choice(ALLDIRECTIONS))
        random.shuffle(self.directions)

    def printLogic(self):
        return ''.join(['R' if i == RIGHT else 'L' if i == LEFT else ' ' \
                for i in self.directions])

    def addDirection(self, direction=NONE):
        self.directions.append(direction)

    def evolve(self, mutationrate = 0.1):
        for i in range(len(self.directions)):
            if random.random() < mutationrate:
                if self.directions[i] == LEFT:
                    self.directions[i] = random.choice([NONE, RIGHT])
                elif self.directions[i] == RIGHT:
                    self.directions[i] = random.choice([LEFT, NONE])
                else:
                    self.directions[i] = random.choice([LEFT, RIGHT])

    def mutateLastN(self, n):
        for i in range(n):
            if self.currentStep - i < 0:
                return
            if self.directions[self.currentStep - i] == LEFT:
                self.directions[self.currentStep - i] = random.choice([NONE, RIGHT])
            if self.directions[self.currentStep - i] == RIGHT:
                self.directions[self.currentStep - i] = random.choice([LEFT, NONE])
            else:
                self.directions[self.currentStep - i] = random.choice([LEFT, RIGHT])


class Gravitron(object):
    def __init__(self):
        self.brain = Logic()
        self.goal = False
        self.score = 0

    def reset(self):
        self.goal = False
        self.brain.currentStep = 0

    def nextMove(self):
        self.brain.currentStep = self.brain.currentStep + 1
        return self.brain.directions[self.brain.currentStep - 1]  

    def mutate(self, mutationrate = MUTATIONRATE):
        self.brain.evolve(mutationrate)

    def printGravitron(self):
        return self.brain.printLogic()


class Population(object):
    def __init__(self, size=2):
        self.population = []
        self.generation = 0
        self.populationScore = 0
        self.eliteSize = 0
        for _ in range(size):
            g = Gravitron()
            self.population.append(g)
    
    def printPopulation(self):
        for i in self.population:
            print i.score, i.printGravitron()

    def updatePopulationScore(self):
        score = 0
        for i in self.population:
            score = score + i.score
        self.populationScore = score

    def getBestScore(self):
        score = 0.0
        idx = 0
        for i in range(0, len(self.population)):
            if self.population[i].score > score:
                idx = i
                score = self.population[i].score
        return score, idx

    def naturalSelection(self):
        newGenenaration = []
        bestScore, idxbest = self.getBestScore()
        totalScore = self.populationScore

        winner = copy.deepcopy(self.population[idxbest])

        self.eliteSize = 6
        self.newBabiesSize = 1
        self.remaning = len(self.population) - (self.eliteSize + self.newBabiesSize) 

        print '--------------------------------------------------------------------'
        print 'Generation %03d - Summary' % (self.generation + 1)
        print 'Population size         : %d' % len(self.population)
        print 'Best Gravitron (%d)      : %3.2f' % (idxbest + 1, bestScore)
        print 'Number of Elite Members : %d' % self.eliteSize
        print 'New Gravitrons added    : %d' % self.newBabiesSize
        print 'Old Gravitrons Mutated  : %d' % self.remaning
        print 'Total Score (Sum)       : %4.2f' % totalScore
        print '--------------------------------------------------------------------'

        statusscreen.send('--------------------------------------------------------------------\n')
        statusscreen.send('Generation %03d\n' % (self.generation + 1))
        statusscreen.send('Best Gravitron (%d)      : %3.2f\n' % (idxbest + 1, bestScore))
        statusscreen.send('Score Total (Sum)       : %4.2f\n' % totalScore)
        statusscreen.send('--------------------------------------------------------------------\n')

        for i in range(self.eliteSize):
            elite = copy.deepcopy(winner)
	    if i > 1:
                elite.brain.mutateLastN(i * 3)
            elite.reset()
            newGenenaration.append(elite)

        for _ in range(self.newBabiesSize):
           newBaby = Gravitron()
           newGenenaration.append(newBaby)

        for _ in range(self.remaning):
            rvf = random.uniform(totalScore / 1.7, totalScore)
            gradualScore = 0
            for k in self.population:
                gradualScore = gradualScore + k.score
                if gradualScore > rvf:
                    son = copy.deepcopy(k)
                    son.mutate(MUTATIONRATE)
                    son.reset()
                    newGenenaration.append(son)
                    break

        self.population = copy.copy(newGenenaration)
        random.shuffle(self.population)
        self.generation = self.generation + 1


class playGameThread(threading.Thread):
    def __init__(self, threadID, gravitronID, generation, directions, tty, lock):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.gravitronID = gravitronID
        self.generation = generation
        self.directions = directions
        self.tty = tty
        self.logfile = 'content-' + str(threadID) + '-' + 'tty.log'
        self.flagfile = 'flag-' + str(threadID) + '-'
        self.currentStep = 0
        self.lock = lock

    def run(self):
        if self._Thread__target is not None:
            self._return = self._Thread__target(*self._Thread__args, **self._Thread__kwargs)
        global scores

games = Population(POPULATIONSIZE)
scores = []
lock = threading.Lock()
resultscreen.send('')

print '--------------------------------------------------------------------'
print '      Super Gravitron Leet Edition - Solution (PWN2WIN 2018)      '
print '--------------------------------------------------------------------'

for generation in range(1, GENERATIONS + 1):
    print '--------------------------------------------------------------------'
    print 'Generation %03d - Execution' % (generation)
    print '--------------------------------------------------------------------'

    for gravitron in range(0, POPULATIONSIZE):
        score = 0.0

        FNULL = open(os.devnull, 'w')
        p = subprocess.Popen(command, shell = True, stdin = subprocess.PIPE, \
                stdout = subprocess.PIPE, stderr = FNULL)
        fd = p.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        while True:
            try:
                screen = p.stdout.read(4096)
            except:
                continue
            resultscreen.send(screen)
            currentime = re.findall('\[\d+:\d+\].*\[(\d+.\d+)\]', screen)

           
            if 'CTF' in screen:
                suffix = datetime.datetime.now().strftime("%y%m%d_%H%M%S")
                filename = self.flagfile + suffix + '.txt'
                f = open(filename, 'w')
                f.write(screen)
                f.close()

            # Game Over
            if 'X' in screen:
                print 'Generation %03d - Gravitron %03d / %03d - \
Steps: %05d - Score: %3.02f' % (generation, gravitron + 1, POPULATIONSIZE, 
                                games.population[gravitron].brain.currentStep,
                                score)
        
                games.population[gravitron].score = score
                p.terminate()
                break 
        
   
            if currentime:
                score = float(currentime[0])
                move = games.population[gravitron].nextMove()
                if move:
                    p.stdin.write(move)

    games.updatePopulationScore()
    bestScore, _ = games.getBestScore()
    print 'Generation %03d - Best score: %03.2f - Total Score: %03.2f' \
            % (generation, bestScore, games.populationScore)
 
    games.naturalSelection()
