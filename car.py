import random
from time import sleep
from decimal import Decimal
from collections import deque
from pdb import set_trace
from math import sqrt
from msg import Msg
from enum import Enum
from visualGraph import *



class State(Enum):
	VULNERABLE = 0
	INFECTED = 1
	RECOVERED = 2


def dist(p,q):  #eucledian distance
	return sqrt((p[0]-q[0])**2+(p[1]-q[1])**2)
def in_range(p,q,radius):	#returns true whether the distance p,q is less than radiu
	return dist(p,q) < radius


class Car:
	#Costruttore
	def __init__(self, plate, pos, adj):
		self.plate = plate
		self.pos = pos
		self.messages = []
		self.state = State.VULNERABLE
		self.timer_infected = None
		self.adj = adj
		self.sim = None  #simulator object
		self.neighbors = None  #neighbors of the car


	def initialize_for_simulation(self, sim):
		self.sim = sim

		# saves the neighbors in a list for more efficient access during the simulation
		neighbors = map(lambda x: self.sim.getCar(x), self.adj)
		neighbors = filter(lambda x: x != None, neighbors)
		self.neighbors = list(neighbors)


	def modifyMsg(self, msg, msg_list):
		#Update the message with my data
		msg.last_emit = self.pos
		all_emitters = set([self.pos])
		for m in msg_list:
			all_emitters = all_emitters.union(set(m.emitters))
		
		#I update the list of the emitters and if its length exceeds EMITTERS_LIMIT I keep the closest ones
		key = lambda x: dist(x, self.pos)
		all_emitters_srtd = sorted(list(all_emitters), key=key, reverse=True)
		msg.emitters = deque(all_emitters_srtd, maxlen=Msg.EMITTERS_LIMIT)
		
		msg.hop += 1

	def broadMsg(self):
		bcast = self.evaluate_positions(self.messages, self.pos)
		if (not bcast):
			return

		#take the first message in the list of incoming messages (the first message generated the infection)
		msg = self.messages[0].clone()
		self.modifyMsg(msg, self.messages)

		#Don't broadcast if the message reached its hop limit
		if msg.hop == msg.ttl:
			return

		message_sent = False
		for neighbor in self.neighbors:
			if not message_sent:   #we are in broadcast, count one message sent independently on the number of neighbors reached
				message_sent = True
				self.sim.sent_messages += 1

			if not self.sim.no_graphics:
				if neighbor.state == State.VULNERABLE:
					visualInfect(self, neighbor)
			neighbor.infect(msg)

		if not self.sim.no_graphics:
			sleep(0.01)

		self.messages.clear()



	def infect(self, msg):
		#Simulate message loss while receiving
		if random.random() < Simulator.DROP:
			return

		self.sim.rcv_messages += 1   #for simulation statistics

		# If I already received this message (RECOVERED state) I don't do anything
		if self.state == State.RECOVERED:
			return

		# If it's the first time that the message arrive, I go from VULNERABLE state to
		# INFECTED state, then I start the waiting timer
		if self.state == State.VULNERABLE:
			self.sim.t_last_infected = self.sim.t
			self.sim.n_hop_last_infected = msg.hop
			self.transition_to_state(State.INFECTED)
			self.timer_infected = self.getWaitingTime(msg.last_emit)  #set waiting timer in function of the distance 

		self.messages.append(msg)



	def getWaitingTime(self, emit_pos):
		""" Returns the waiting time a vehicle has to wait when infected.
		Calculated using the distance between me and the emitter that sent 
		me the message, expressed as number of simulator ticks
		"""
		dAS = dist(self.pos, emit_pos) 
		waiting_time = Simulator.TMAX*(1 - dAS/Simulator.RMAX)  #waiting time, in seconds

		if waiting_time <= Simulator.TMIN:
			waiting_time = Simulator.TMIN
		if waiting_time >= Simulator.TMAX:
			waiting_time = Simulator.TMAX

		# Converts from seconds to simulator ticks
		return waiting_time / Simulator.TIME_RESOLUTION



	# WE USED THIS
	def evaluate_positions(self, messages, my_pos):   # 1 messaggio solo  ## valuta se mandare in broadcast o no

		'''neighbor_positions = []   #positions of neighbors cars
		for c, i in zip(self.adj, range(len(self.adj))):
			if c == 1:
				#Ho preso la macchina corrispondente
				obj = self.sim.getCar(i)
				if obj != None:
					neighbor_positions.append(obj.pos)'''

		n_neighbors = len(self.neighbors)
		not_reached_neighbors = set(self.neighbors)

		for m in messages:
			for emit in m.emitters:  #per ogni emitter diversa che ha mandato il messaggio
				for neighbor in list(not_reached_neighbors):  #controllo se un mio vicino ha già ricevuto un messaggio da un emitter precedente
					if in_range(neighbor.pos, emit, self.sim.rmin):
						not_reached_neighbors.remove(neighbor)
		
		# return true (relay) only if there is a percentage ALPHA of uncoverd neighbors
		return len(not_reached_neighbors) > Simulator.ALPHA * n_neighbors




	# WE USED THIS as the probabilistic dissemination
	def evaluate_positions_probabilistic(self, messages, my_pos):
		#relay the message with probability P
		P = 0.9
		return random.random() > (1-P)

		

	# utility: transition a vehicle to a certain state
	def transition_to_state(self, state_final):
		if self.state == State.VULNERABLE and state_final == State.INFECTED:
			self.sim.infected_counter += 1
			self.state = State.INFECTED
		elif self.state == State.INFECTED and state_final == State.RECOVERED:
			self.sim.infected_counter -= 1
			self.state = State.RECOVERED
		else:
			raise ValueError('Inconsistent state transition from', self.state, 'to', state_final)



from simulator import Simulator  #se lo metto sopra si sfascia (cyclic imports), todo soluzione migliore
