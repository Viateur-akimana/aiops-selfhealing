"""
AWS Lambda Function for Scale-Out (Auto-Scaling) Remediation

Triggered when:
- High CPU Saturation Alarm fires (>80% CPU)
- High Memory Saturation Alarm fires (>80% Memory)

Action:
- Increase ECS service desired count to handle load
- Log scaling action to CloudWatch
"""

import json
import boto3
import os
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ecs_client = boto3.client('ecs')
autoscaling_client = boto3.client('application-autoscaling')

CLUSTER_NAME = os.environ.get('CLUSTER_NAME')
SERVICE_NAME = os.environ.get('SERVICE_NAME')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')


def lambda_handler(event, context):
    """
    Main handler for scale-out remediation
    """
    try:
        logger.info(f"Received scaling event: {json.dumps(event)}")
        
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
        current_count = service['desiredCount']
        max_tasks = 4  # Should match Terraform max_capacity
        
        # Calculate new desired count (scale out by 1 task, max 4)
        new_count = min(current_count + 1, max_tasks)
        
        if new_count == current_count:
            logger.info(f"Service already at maximum capacity ({current_count} tasks)")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Already at max capacity',
                    'current_count': current_count,
                    'max_count': max_tasks
                })
            }
        
        logger.info(f"Scaling service from {current_count} to {new_count} tasks...")
        
        # Update service
        ecs_client.update_service(
            cluster=CLUSTER_NAME,
            service=SERVICE_NAME,
            desiredCount=new_count
        )
        
        # Log scaling action
        scaling_log = {
            'timestamp': datetime.utcnow().isoformat(),
            'action': 'scale_out',
            'cluster': CLUSTER_NAME,
            'service': SERVICE_NAME,
            'previous_count': current_count,
            'new_count': new_count,
            'max_count': max_tasks,
            'trigger': event.get('detail', {}).get('alarmName', 'unknown'),
            'status': 'success'
        }
        
        logger.info(f"Scale-out completed: {json.dumps(scaling_log)}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Service scaled out successfully',
                'service': SERVICE_NAME,
                'cluster': CLUSTER_NAME,
                'new_count': new_count
            })
        }
        
    except Exception as e:
        logger.error(f"Error during scale-out: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Scale-out failed'
            })
        }
