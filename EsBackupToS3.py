# Name          : EsBackupToS3
# Author        : Bijohn Vincent
# Functionality : This function is for creating snapshot of AWS Elasticsearch service to S3
# Prerequisite  : - Snapshot repository must be created that directs to your S3 bucket
#                    (Follow 'Snapshot Prerequisites' and 'Registering a Snapshot Directory' in 
#                    http://docs.aws.amazon.com/elasticsearch-service/latest/developerguide/es-managedomains.html#es-managedomains-snapshots)
#                 - Requires 'requests' to be packaged while using in AWS Lambda


# Import modules
import requests, datetime, hashlib, hmac, os, sys, boto3
from time import sleep

#########################################   Modify following variables  ############################################
# Add your ES endpoint (https:// shold not be added here)
host = 'search-********************************.<region>.es.amazonaws.com'
snapshotRepository = '/_snapshot/mysnapshots/'  ##  !!! format '/_snapshot/<snapshot Repository Name>/' MUST end with '/'
SnsTopicArn = "arn:aws:sns:<region>:<Aws Account Number>:<SNS topic name>"
####################################################################################################################

# Global variables
service = 'es'
region = host.split(".")[1]
endpoint = 'https://'+ host
session_token = None

# Set 'True' Only if you need notification on everytime this function runs. 
# If 'False', function will notify only when request fails
# Idealy should be Flase
notifyEveryTime = False




# following two functions are Copied from:
# http://docs.aws.amazon.com/general/latest/gr/signature-v4-examples.html#signature-v4-examples-python
def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

def getSignatureKey(key, date_stamp, regionName, serviceName):
    kDate = sign(('AWS4' + key).encode('utf-8'), date_stamp)
    kRegion = sign(kDate, regionName)
    kService = sign(kRegion, serviceName)
    kSigning = sign(kService, 'aws4_request')
    return kSigning


################################################################
# This function will send notification to specified SNS topic
################################################################
def notify_sns (message, snsSubject):
    SnsClient = boto3.client('sns')
    response = SnsClient.publish(
        TopicArn= SnsTopicArn,
        Message= message,
        Subject= snsSubject,
        MessageStructure='string'
        )


################################################################
# This function will create the snapshot of the specified index
################################################################
def createEsSnapshot(indexName,access_key, secret_key, session_token, amz_date, date_stamp, snapshot_date_stamp):
    
    # Local variables for this function
    method = 'PUT'
    content_type = 'application/x-amz-json-1.0'
    #### !!! request_parameters must be sorted with name and must be url encoded !!!
    request_parameters = 'wait_for_completion=false'
    request_data = '{"indices": "'+ indexName +'",   "ignore_unavailable": true,  "include_global_state": false, "compress":true}'
    
    # Modify indexName to create a valid object in S3
    if indexName != '*':
        # Remove - and * from snapshot name
        for remove in '.-*':
            indexName=indexName.replace(remove,'')
    else:
        indexName = 'allindices'
    
    # Create snapshot name
    snpashotName = indexName+ '-on-' + str(snapshot_date_stamp)
    
    # CREATE A CANONICAL REQUEST 
    canonical_uri = snapshotRepository + snpashotName
    canonical_querystring = request_parameters
    canonical_headers = 'content-type:' + content_type + '\n' \
                        + 'host:' + host + '\n' \
                        + 'x-amz-date:' + amz_date + '\n'\
                        + 'x-amz-security-token:' + session_token + '\n'
    signed_headers = 'content-type;host;x-amz-date;x-amz-security-token'
    payload_hash = hashlib.sha256(request_data).hexdigest()
    canonical_request = method + '\n' \
                        + canonical_uri + '\n' \
                        + canonical_querystring + '\n' \
                        + canonical_headers + '\n' \
                        + signed_headers + '\n' \
                        + payload_hash
    
    # CREATE THE STRING TO SIGN
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = date_stamp + '/' + region + '/' + service + '/' + 'aws4_request'
    string_to_sign = algorithm + '\n' \
                +  amz_date + '\n' \
                +  credential_scope + '\n' \
                +  hashlib.sha256(canonical_request).hexdigest()
    
    # CALCULATE THE SIGNATURE
    signing_key = getSignatureKey(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, (string_to_sign).encode('utf-8'), hashlib.sha256).hexdigest()
    
    # ADD SIGNING INFORMATION TO THE REQUEST
    authorization_header = algorithm + ' ' \
                        + 'Credential=' + access_key + '/' + credential_scope + ', ' \
                        + 'SignedHeaders=' + signed_headers + ', ' \
                        + 'Signature=' + signature
    headers = {'Content-Type':content_type,
            'X-Amz-Date':amz_date,
            'Authorization':authorization_header,
            'X-Amz-Security-Token':session_token}
    
    # SEND THE REQUEST
    request_url = endpoint + canonical_uri
    r = requests.put(request_url, params=canonical_querystring, data=request_data, headers=headers)
    if r.status_code == 200:
        print "Initiated snapshot ("+snpashotName+") creation successfully"
        
        if notifyEveryTime:
            #Send notification if nofification required every time
            snsSubject = "Info: ElasticSearch snapshot to S3 succeeded"
            message = "Hello,\nRequest for ElasticSearch snapshot of " + snpashotName +\
                      " index/indices has returned a 200 status code.\n"
            notify_sns (message, snsSubject)
        
    else:
        print "Failed creation of snapshot ("+snpashotName+")"
        
        #Send notification if fails snapshot
        snsSubject = "Alert: Failed ElasticSearch snapshot to S3"
        message = "Hello,\nRequest for ElasticSearch snapshot of " + snpashotName +\
                  " index/indices has returned a non 200 status code.\n" +\
                  "status code = "+ repr(r.status_code) + "\n" + r.text
        notify_sns (message, snsSubject)
    return


################################################################
# Main function
################################################################
def lambda_handler(event, context):
    
    # Get IAM role credential of this Lambda function
    access_key = os.environ['AWS_ACCESS_KEY_ID']
    secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
    session_token = os.environ['AWS_SESSION_TOKEN']
    
    # Exit if no AWS credentials are available
    if access_key is None or secret_key is None or session_token is None:
        print 'Credentials not avilable.'
        sys.exit()
    
    # Create a date for headers and the credential string
    t = datetime.datetime.utcnow()
    amz_date = t.strftime('%Y%m%dT%H%M%SZ')
    date_stamp = t.strftime('%Y%m%d') # Date w/o time, used in credential scope
    snapshot_date_stamp = t.strftime('%Y%m%d-%H%M')
    
    # Get which index pattern to be included in snapshot.
    if 'backupIndex' in event:
        indexName = event['backupIndex']
    else:
        indexName = '*'
    
    # Initiate snapshot
    createEsSnapshot(indexName,access_key, secret_key, session_token, amz_date, date_stamp, snapshot_date_stamp)

    
