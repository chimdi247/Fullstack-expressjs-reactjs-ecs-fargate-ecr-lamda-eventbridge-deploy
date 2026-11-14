# 🧒 Project: Automatically Update ECS When New Image is Pushed to ECR

## 📌 Overview

This project uses AWS services to automatically update your ECS service when a new image is pushed to an ECR repository.

### 🔧 Tools Used

* **ECR (Elastic Container Registry)**
* **ECS (Elastic Container Service)**
* **Lambda**
* **EventBridge (CloudWatch Events)**
* **IAM Roles and Policies**

---

## 🏗️ Step-by-Step Implementation

### ✅ Step 1: Create an ECR Repository

1. Go to AWS Console → **ECR**
2. Click **Create repository**
3. Enter name: `flask-app-backend`
4. Leave everything else as default
5. Click **Create repository**

---

### ✅ Step 2: Build and Push Docker Image to ECR

```bash
# Replace with your values
AWS_ACCOUNT_ID=987654321000
AWS_REGION=us-east-1
REPO_NAME=flask-app-backend

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build image
docker build -t $REPO_NAME .

# Tag image
docker tag $REPO_NAME:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME:v1.0.3

# Push image to ECR
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME:v1.0.3
```

---

### ✅ Step 3: Create an ECS Cluster

1. Go to **ECS** → Clusters → Create Cluster
2. Choose **Fargate**
3. Name: `production-backend-cluster`
4. Click **Create**

---

### ✅ Step 4: Create ECS Task Definition

1. Go to ECS → **Task Definitions** → Create new
2. Launch type: **Fargate**
3. Add container:

   * Name: `backend-container`
   * Image: `987654321000.dkr.ecr.us-east-1.amazonaws.com/flask-app-backend:v1.0.3`
   * Port: 5000
4. Click **Create**

---

### ✅ Step 5: Create ECS Service

1. Go to **Clusters → production-backend-cluster** → Create Service
2. Launch type: **Fargate**
3. Task definition: use the one you created
4. Number of tasks: 1
5. Click **Create Service**

---

### ✅ Step 6: Create Lambda Function

1. Go to AWS → **Lambda** → Create Function
2. Name: `AutoUpdateBackendOnPush`
3. Runtime: Python 3.12
4. Click **Create Function**

---

### ✅ Step 7: Add Lambda Code

Paste the Lambda code (see code section above).

```python
import boto3
import os
import logging

# 📝 Set up logging so we can see what's happening
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 🛠️ Connect to ECS
ecs_client = boto3.client('ecs')

def lambda_handler(event, context):
    try:
        # 📦 Get info from environment
        cluster_name = os.environ['ECS_CLUSTER']
        service_name = os.environ['ECS_SERVICE']
        container_name = os.environ['CONTAINER_NAME']
        account_id = os.environ['AWS_ACCOUNT_ID']
        #region = os.environ['AWS_REGION']
        region = os.environ.get('AWS_REGION', 'us-east-1')


        # 🎯 Get the new image from the event
        repository_name = event.get('detail', {}).get('repository-name')
        image_tag = event.get('detail', {}).get('image-tag')
        if not repository_name or not image_tag:
            raise ValueError("Missing 'repository-name' or 'image-tag' in event['detail']")

        image_uri = f"{account_id}.dkr.ecr.{region}.amazonaws.com/{repository_name}:{image_tag}"
        logger.info(f"👀 New image URI: {image_uri}")

        # 📦 Describe current ECS task
        response = ecs_client.describe_services(cluster=cluster_name, services=[service_name])
        task_def_arn = response['services'][0]['taskDefinition']
        task_def = ecs_client.describe_task_definition(taskDefinition=task_def_arn)
        container_definitions = task_def['taskDefinition']['containerDefinitions']

        # 🧬 Update image inside task definition
        updated = False
        for container in container_definitions:
            if container['name'] == container_name:
                container['image'] = image_uri
                updated = True

        if not updated:
            raise ValueError(f"❌ Container '{container_name}' not found.")

        # 🆕 Register a new task definition with the new image
        new_task_def = ecs_client.register_task_definition(
            family=task_def['taskDefinition']['family'],
            executionRoleArn=task_def['taskDefinition']['executionRoleArn'],
            networkMode=task_def['taskDefinition']['networkMode'],
            containerDefinitions=container_definitions,
            requiresCompatibilities=task_def['taskDefinition']['requiresCompatibilities'],
            cpu=task_def['taskDefinition']['cpu'],
            memory=task_def['taskDefinition']['memory']
        )

        # 🔄 Update ECS service with new task
        ecs_client.update_service(
            cluster=cluster_name,
            service=service_name,
            taskDefinition=new_task_def['taskDefinition']['taskDefinitionArn']
        )

        logger.info("✅ ECS updated!")
        return {"message": "ECS updated with new image"}

    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        return {"error": str(e)}


```

---

### ✅ Step 8: Set Environment Variables

Under **Configuration → Environment variables**:

* `ECS_CLUSTER` = `production-backend-cluster`
* `ECS_SERVICE` = `flask-backend-service`
* `CONTAINER_NAME` = `backend-container`
* `AWS_ACCOUNT_ID` = `987654321000`
* `AWS_REGION` = `us-east-1`

---

### ✅ Step 9: Add IAM Permissions to Lambda

Attach this policy to Lambda's execution role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeServices",
        "ecs:DescribeTaskDefinition",
        "ecs:RegisterTaskDefinition",
        "ecs:UpdateService"
      ],
      "Resource": "*"
    }
  ]
}
```

---

### ✅ Step 10: Create EventBridge Rule

1. Go to **EventBridge** → Rules → Create Rule
2. Name: `BackendAutoUpdateTrigger`
3. Event source: **AWS Services → ECR → Image Action**
4. Pattern:

```json
{
  "source": ["aws.ecr"],
  "detail-type": ["ECR Image Action"],
  "detail": {
    "action-type": ["PUSH"],
    "result": ["SUCCESS"]
  }
}
```

5. Set Target → **Lambda** → `AutoUpdateBackendOnPush`
6. Click **Create**

---

## ✅ Final Result

Every time you push a new image to ECR:

* EventBridge triggers the Lambda
* Lambda updates ECS Task Definition
* ECS runs the updated container

---

## 📈 Architecture Diagram

```
+------------+      Push        +-----------+       Triggers      +------------------------+
| Developer  |  ------------->  |   ECR     |  -----------------> |  Lambda (AutoUpdater)  |
+------------+                 +-----------+                     +------------------------+
                                                                      |
                                                                      | Calls
                                                                      v
                                                             +---------------------+
                                                             |   ECS Service       |
                                                             | (flask-backend-svc) |
                                                             +---------------------+
```

---

## 🏑 That's It!

You have successfully created a **fully automated pipeline** to update your ECS container on every ECR push using EventBridge and Lambda.


Done! ✅

- I've added random but realistic example values for:

1. ECR repo name: flask-app-backend
2. Image tag: v1.0.3
3. Account ID: 987654321000
4. ECS cluster: production-backend-cluster
5. Service name: flask-backend-service
6. Container name: backend-container



# 🧪 Step-by-Step: Test Your Auto-Update Setup

### 🎯 Goal:

When you push a new image to ECR, your ECS service should **automatically update** with that image. No manual work!

---

## 🧱 PRE-REQUIREMENTS CHECKLIST

✅ You already have:

* An ECR repo (e.g., `flask-app-backend`)
* An ECS Cluster + ECS Service running
* A working Lambda function that updates ECS
* EventBridge rule that triggers Lambda when new image is pushed

If YES, you’re good to go! 🎉

---

## 🚀 Step 1: Open Terminal and Set Your Variables

Paste this in your terminal:

```bash
AWS_ACCOUNT_ID=987654321000
AWS_REGION=us-east-1
REPO_NAME=flask-app-backend
NEW_VERSION=v1.0.4
```

---

## 🏗️ Step 2: Build a New Docker Image

```bash
docker build -t $REPO_NAME .
```

---

## 🏷️ Step 3: Tag the Image With a New Version

```bash
docker tag $REPO_NAME:latest \
$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME:$NEW_VERSION
```

---

## ☁️ Step 4: Push to ECR (this triggers the update!)

```bash
aws ecr get-login-password --region $AWS_REGION | \
docker login --username AWS --password-stdin \
$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME:$NEW_VERSION
```

👆 This PUSH will trigger EventBridge ➡ Lambda ➡ ECS 🚀

---

## ⏳ Step 5: Go to AWS Console → ECS

1. Open AWS Console
2. Go to **ECS > Clusters > production-backend-cluster**
3. Click on **Services > flask-backend-service**
4. Click **Tasks tab**
5. You’ll see:
   🔁 **Old task stops**
   🆕 **New task starts** using image `:v1.0.4`

---

## 🕵️ Step 6: Check Logs in Lambda

1. Go to **Lambda Console**
2. Click your function `AutoUpdateBackendOnPush`
3. Click **Monitor → View Logs in CloudWatch**
4. You’ll see logs like:

   ```
   Updating image to: flask-app-backend:v1.0.4
   ECS service updated successfully.
   ```

---

## ✅ Step 7: (Optional) Verify App Version

If your app has a version displayed (e.g., on `/version` route), visit the public IP of the ECS Task or Load Balancer and confirm it shows `v1.0.4`.

---

## 🎉 ALL DONE!

You just tested **ECR → Lambda → ECS Auto Deployment** by:

🛠️ Building a new version
📦 Pushing to ECR
⚡ Automatically updating ECS service
🖥️ Running new version live!

---

Let me know if you want:

* Sample app to test with
* HTML UI to show version
* Monitoring setup (like Slack alert)

I'm here like your tech buddy! 👶💻
