"""
AWS Lambda Function for Auto-Restarting ECS Service (Self-Healing)

Triggered when:
- High Error Rate Alarm fires (>5% errors)

Action:
- Update ECS service task count to 0 then back to desired count (restart)
- Log action to CloudWatch
"""

import json
import boto3
import os
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ecs_client = boto3.client('ecs')
logs_client = boto3.client('logs')

CLUSTER_NAME = os.environ.get('CLUSTER_NAME')
SERVICE_NAME = os.environ.get('SERVICE_NAME')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')


def lambda_handler(event, context):
    """
    Main handler for auto-restart remediation
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Get current service state
        response = ecs_client.describe_services(
            cluster=CLUSTER_NAME,
            services=[SERVICE_NAME]
        )
        
        if not response['services']:
            logger.error(f"Service {SERVICE_NAME} not found in cluster {CLUSTER_NAME}")
            return {
                'statusCode': 404,
                'body': json.dumps('Service not found')
            }
        
        service = response['services'][0]
        task_definition = service['taskDefinition']
        desired_count = service['desiredCount']
        
        logger.info(f"Current service state: desired_count={desired_count}, task_definition={task_definition}")
        
        # Step 1: Scale down to 0
        logger.info(f"Scaling service down to 0...")
        ecs_client.update_service(
            cluster=CLUSTER_NAME,
            service=SERVICE_NAME,
            desiredCount=0
        )
        
        # Wait a bit for tasks to drain
        import time
        time.sleep(10)
        
        # Step 2: Scale back up to desired count
        logger.info(f"Scaling service back up to {desired_count}...")
        ecs_client.update_service(
            cluster=CLUSTER_NAME,
            service=SERVICE_NAME,
            desiredCount=desired_count
        )
        
        # Log remediation action
        remediation_log = {
            'timestamp': datetime.utcnow().isoformat(),
            'action': 'auto_restart',
            'cluster': CLUSTER_NAME,
            'service': SERVICE_NAME,
            'previous_desired_count': desired_count,
            'new_desired_count': desired_count,
            'trigger': event.get('detail', {}).get('alarmName', 'unknown'),
            'status': 'success'
        }
        
        logger.info(f"Remediation completed: {json.dumps(remediation_log)}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Service restarted successfully',
                'service': SERVICE_NAME,
                'cluster': CLUSTER_NAME
            })
        }
        
    except Exception as e:
        logger.error(f"Error during remediation: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Remediation failed'
            })
        }
