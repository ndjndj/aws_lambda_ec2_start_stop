import boto3
import json
import os 
import sys
from datetime import datetime, date
from decimal import Decimal

region = "ap-northeast-1"
instances = [os.getenv("INSTANCE_ID")]
ec2 = boto3.client("ec2", region_name=region)

UNDEFINED_STATUS = {"Code": -1, "Name": "Undefined"}

# EC2 status 
#  0: pending
# 16: running
# 32: shutting-down
# 48: terminated
# 64: stopping
# 80: stopped

def desc_status_ec2():
    ec2_instance = ec2.describe_instances(
        Filters=[{"Name": "instance-id","Values": instances}]
    )
    ec2_status = ec2_instance \
        .get("Reservations", [{}])[0] \
        .get("Instances", [{}])[0] \
        .get("State", UNDEFINED_STATUS)
    
    return ec2_status 

def lambda_handler(event, context):
    status_code = 200
    body = {}
    try:
        query = event.get("queryStringParameters", {}) 
        if query == None:
            query = {}
        action = query.get("action", "check")
        
        if action == "check":
            ec2_status = desc_status_ec2()
            body = ec2_status
        elif action == "start":
            ec2_status = ec2.start_instances(InstanceIds=instances)
            body = ec2_status \
                .get("StartingInstances", [{}])[0] \
                .get("CurrentState", UNDEFINED_STATUS)
        elif action == "stop":
            ec2_status = ec2.stop_instances(InstanceIds=instances)
            body = ec2_status \
                .get("StoppingInstances", [{}])[0] \
                .get("CurrentState", UNDEFINED_STATUS)
        
    except Exception as e:
        exc_type, _, exc_tb = sys.exc_info()
        print("internal error %s %s: %s" % (exc_tb.tb_lineno, exc_type, e))
        status_code = 500
        body = {
            'message': 'Internal Server Error', 
            'details': "internal error %s %s: %s" % (exc_tb.tb_lineno, exc_type, e)
        }
        
    return {
        'statusCode': status_code,
        'body': json.dumps(body, ensure_ascii=False, default=defined_handler)
    }

def defined_handler(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return obj