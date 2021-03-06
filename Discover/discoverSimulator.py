
import sys
import random
import functools
from multiprocessing import Pool
from collections import defaultdict
from carD import Car, State as carState
from packetsD import *
from pdb import set_trace as breakpoint
from visualGraph import *
from threading import Thread


random.seed(40)

class Simulator:

	# Simulation parameters
	SECONDS_SIM = 20  #TODO change and iterate while there are infected cars
	TIME_RESOLUTION = 0.05 #0.05 seconds per iteration

	# Environment parameters
	TMAX = 1		#tempo di attesa massima prima di mandare un messaggio in broadcast, in secondi
	TMIN = 0		#tempo di attesa minima prima di mandare un messaggio in broadcast, in secondi
	RMIN = 50		#raggio minimo di comunicazione, espresso in metri
	RMAX = 2000		#raggio massimo di comunicazione, espresso in metri
	DROP = 0.00		#rate di messaggi persi spontaneamente nella trasmissione
	ALPHA = 0.8		#quanto tempo di attesa deve essere deterministico e quanto non deterministico.
					#ALPHA in [0,1]. ALPHA=1 è completamente deterministico, ALPHA=0 non deterministico.
					# (possiamo aggiungere dopo che ALPHA non è costante ma magari dipende da macchina a macchina, a seconda delle condizioni del traffico)

	def __init__(self, cars):
		self.cars = cars
		for car in self.cars:
			car.sim = self

		self.rmin = Simulator.RMIN

		# Create a dictionary plate-->car-object
		#_car_dict = {c.plate: c for c in self.cars}
		_car_dict = {c.plate: c for c in self.cars if c != None}
		self.car_dict = defaultdict(lambda: None, _car_dict)
		self.t = 0   #current simulation iteration

		# Metrics variables
		self.rcv_messages = 0  #number of received messages
		self.sent_messages = 0 #number of sent messages
		self.t_last_infected = 0  #time step of the last car infected
		self.n_hop_last_infected = 0  #number of hops of last infected car

		# Args
		self.no_graphics = "--no-graphics" in sys.argv


	def threadRoutine(self, car):
		if car.state == carState.INFECTED:
			car.timer_infected -= 1

			if car.timer_infected <= 0:
				car.timer_infected = None
				car.state = carState.RECOVERED
				car.broadMsg()


	def runSimulation(self):
		for t in range(int(Simulator.SECONDS_SIM/Simulator.TIME_RESOLUTION)):
			self.t = t

			threads= [None]*len(self.cars)
			i=0
			for car in self.cars:	# k è la chiave dell'elemento
				threads[i]=Thread(target=self.threadRoutine, args=(car,))
				threads[i].start()
				i+=1

	def getCar(self, plate):
		return self.car_dict[plate]



def init_cars():
	positions = []
	p = open("../grafi/Luxembourg/pos/pos_time27100Tper1000.txt", "r")
	#p = open("grafi/Cologne/pos/pos_time23000Tper1000.txt", "r")
	for i in p:
		d = i[:-1].split(' ')  #discard trailing \n
		if d[0] == d[2] and d[2] == d[4]:  #riga fallata
			positions.append(None)
		else:
			positions.append((float(d[2]), float(d[3])))
			#sphere(pos=vector(float(d[2]),float(d[3]),0), radius=20)


	a = open("../grafi/Luxembourg/adj/adj_time27100Tper1000.txt", "r")
	#a = open("grafi/Cologne/adj/adj_time23000Tper1000.txt", "r")
	adi = []
	for l in a:
		adi.append([int(n) for n in l.split(' ')])   #get the value as an int
	#breakpoint()
	cars = [Car(i,p,a) if p else None for i,p,a in zip(range(len(adi)),positions,adi)]   #Use as plate the index of the car
	cars = list(filter(lambda x: x != None, cars))
	return cars

def init_cars_newyork():
	import scipy.io as sio
	import numpy as np
	contents = sio.loadmat('grafi/NewYork/Newyork5003.mat')
	adia, coord = contents['Adia'], contents['coord']
	coord = [(x,y) for x,y in zip(coord[0], coord[1])]
	cars = []
	for i,c,a in zip(range(len(adia)),coord,adia):
		cars.append(Car(i,c,a))
	return cars


#Performs 'n' different simulations
def performSimulations(n, with_outliers=False):

	#Perform a single simulation
	def performSimulation():
		cars = init_cars()
		s = Simulator(cars)

		if s.no_graphics:
			random.sample(cars, 1)[0].infect(Request.dummyM())
		else:
			bubbles = displayCars(s.car_dict)
			firstinfected = s.getCar(firstInfection())
			req=Request(1,(0,0), 8, 8, [], 0.001)
			req.Vtx=firstinfected
			req.Vrx=firstinfected
			firstinfected.req = req
			firstinfected.infect(req)
			firstinfected.bm()


		s.runSimulation()
		tmp = str([c.state for c in cars])
		print("Simulation ended")
		print("Vulnerable: ", tmp.count("State.VULNERABLE"))
		print("Infected: ", tmp.count("State.INFECTED"))
		print("Recovered: ", tmp.count("State.RECOVERED"))
		print()

		# Return Simulator or, if the simulation was too bad, don't return it
		if with_outliers:
			return s
		return s if tmp.count("State.RECOVERED")>0.05*len(cars) else None  #consider as outlier a simulation where less than 5% of the cars got infected


	sims = [performSimulation() for i in range(n)]  #list with Simulator objects
	sims = list(filter(lambda x: x!=None, sims))    #filter out None

	print()
	print("Average metrics with D (RMIN) =",Simulator.RMIN)
	print("#sent messages: ", sum([s.sent_messages for s in sims])/n)
	print("#received messages: ", sum([s.rcv_messages for s in sims])/n)
	print("time of last car infection: ", sum([s.t_last_infected for s in sims])*Simulator.TIME_RESOLUTION/n)
	print("#hops to reach last infected car: ",sum([s.n_hop_last_infected for s in sims])/n)
	infected = 0
	for s in sims:
		infected += str([c.state for c in s.cars]).count("State.RECOVERED")
	#print("Cars infected ratio: {:.2f}%".format(100*(infected) / (len(sims)*len(sims[0].cars))))

	return (Simulator.RMIN, #for boxplots
		[s.sent_messages for s in sims],
		[str([c.state for c in s.cars]).count("State.RECOVERED") for s in sims],
		[s.t_last_infected for s in sims],
		[s.n_hop_last_infected for s in sims])
	#return (Simulator.RMIN,  #for graphs
	#	sum([s.sent_messages for s in sims])/n,
	#	100*(infected+15) / (len(sims)*len(sims[0].cars)))



def do_tests(r):
	Simulator.RMIN = r
	return performSimulations(7, with_outliers=True)


if __name__ == "__main__":
	if "--no-graphics" in sys.argv:
		with Pool(4) as pool:
			#print( pool.map(do_tests, range(50, 341, 10)) )
			do_tests(600)

	else:
		performSimulations(1)
