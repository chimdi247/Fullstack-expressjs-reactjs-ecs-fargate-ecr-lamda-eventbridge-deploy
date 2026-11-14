import boto3
import os
import json

ecs = boto3.client('ecs')
region = ecs.meta.region_name
sns = boto3.client('sns')

def send_email(subject, body):
    try:
        sns.publish(TopicArn=os.environ['SNS_TOPIC_ARN'], Subject=subject[:100], Message=body)
    except Exception as e:
        print(f"⚠️ Notification failed: {e}")


def lambda_handler(event, context):

    print("🔍 Event:", json.dumps(event))

    if 'detail' not in event:
        return {"message": "Invalid event"}

    cluster = os.environ['ECS_CLUSTER']
    account_id = os.environ['AWS_ACCOUNT_ID']

    repository = event['detail'].get('repository-name')
    tag = event['detail'].get('image-tag')

    if not repository or not tag:
        return {"message": "Missing repository-name or image-tag"}

    image_uri = f"{account_id}.dkr.ecr.{region}.amazonaws.com/{repository}:{tag}"

    service_map = {
        os.environ['BACKEND_REPO']: {
            "service": os.environ['BACKEND_SERVICE'],
            "task": os.environ['BACKEND_TASK']
        },
        os.environ['FRONTEND_REPO']: {
            "service": os.environ['FRONTEND_SERVICE'],
            "task": os.environ['FRONTEND_TASK']
        }
    }

    if repository not in service_map:
        return {"message": f"Unknown repo: {repository}"}

    service = service_map[repository]['service']
    task = service_map[repository]['task']

    try:
        res = ecs.describe_services(cluster=cluster, services=[service])
        task_def_arn = res['services'][0]['taskDefinition']

        task_def = ecs.describe_task_definition(taskDefinition=task_def_arn)['taskDefinition']
        container_defs = task_def['containerDefinitions']

        updated = False
        for c in container_defs:
            if c['name'] == task:
                c['image'] = image_uri
                updated = True

        if not updated:
            raise Exception(f"Container '{task}' not found in task definition")

        params = {
            "family": task_def['family'],
            "networkMode": task_def['networkMode'],
            "containerDefinitions": container_defs,
            "requiresCompatibilities": task_def['requiresCompatibilities'],
            "cpu": task_def['cpu'],
            "memory": task_def['memory'],
        }
        for key in ("executionRoleArn", "taskRoleArn", "volumes", "runtimePlatform"):
            if task_def.get(key):
                params[key] = task_def[key]

        new_task = ecs.register_task_definition(**params)
        new_arn = new_task['taskDefinition']['taskDefinitionArn']

        ecs.update_service(
            cluster=cluster,
            service=service,
            taskDefinition=new_arn
        )

    except Exception as e:
        send_email(
            subject=f"❌ Deployment FAILED: {service}",
            body=f"Deployment failed.\n\nService: {service}\nImage: {image_uri}\nError: {e}"
        )
        raise

    send_email(
        subject=f"🚀 Deployment started: {service}",
        body=(
            f"A new deployment has been triggered.\n\n"
            f"Cluster: {cluster}\n"
            f"Service: {service}\n"
            f"Image: {image_uri}\n"
            f"Task definition: {new_arn}\n"
        )
    )

    return {"message": f"{repository} deployed + email sent 🚀"}
