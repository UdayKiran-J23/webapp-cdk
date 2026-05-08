# Web Application Infrastructure using AWS CDK

This project contains the infrastructure code to deploy a web application on AWS using Python and AWS CDK. The stack is designed to be scalable, secure, and easy to deploy.

## Architecture

The infrastructure is built around a VPC with public and private subnets spread across 2 Availability Zones. A NAT Gateway is included so that instances in the private subnets can reach the internet without being publicly exposed.

ECS tasks run inside the private subnets on EC2 instances managed by an Auto Scaling Group. The ASG is configured with a minimum of 2 instances and a maximum of 4, so the application can handle varying traffic loads automatically.

An Application Load Balancer sits in the public subnets and distributes incoming HTTP traffic to the ECS tasks. The ALB security group is locked down to only allow traffic on port 80 and port 443.

A private S3 bucket is used to store static assets for the web application. The bucket is encrypted, has public access fully blocked, and content is accessed using pre-signed URLs.

As a bonus, a PostgreSQL RDS instance is provisioned in the private subnets. It is encrypted at rest and only accessible from the ECS instances.

## Prerequisites

Before deploying, make sure you have the following installed and configured:

Python 3.9 or above

Node.js and npm (needed for the CDK CLI)

AWS CDK CLI — install it by running:
```bash
npm install -g aws-cdk
```

AWS CLI — install and configure with your credentials:
```bash
aws configure
```

## Setup and Deployment

Clone the repository and navigate into the project folder:
```bash
git clone https://github.com/UdayKiran-J23/webapp-cdk.git
cd webapp-cdk
```

Create and activate a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows use:
```bash
.venv\Scripts\activate
```

Install the required Python packages:
```bash
pip install -r requirements.txt
```

If this is your first time using CDK in your AWS account and region, bootstrap it:
```bash
cdk bootstrap aws://<ACCOUNT-ID>/<REGION>
```

Check that the CDK code synthesizes without errors:
```bash
cdk synth
```

Deploy the stack to your AWS account:
```bash
cdk deploy
```

You will be asked to confirm any IAM or security group changes. Type y to proceed.

## Post-Deployment Outputs

Once the deployment finishes, the CDK will print three important values:

LoadBalancerDNS — the public DNS name of the ALB. Open this in your browser to see the running web application.

S3BucketName — the name of the S3 bucket created for static assets.

RDSEndpoint — the endpoint address for the PostgreSQL database.

## Generating a Pre-Signed URL for S3

Since the S3 bucket is fully private, files are accessed using pre-signed URLs. Here is a simple example using boto3:

```python
import boto3

s3_client = boto3.client('s3', region_name='<YOUR-REGION>')

url = s3_client.generate_presigned_url(
    'get_object',
    Params={
        'Bucket': '<YOUR-BUCKET-NAME>',
        'Key': 'your-file.txt'
    },
    ExpiresIn=3600
)

print(url)
```

The URL will be valid for 1 hour. You can adjust ExpiresIn as needed.

## Security Decisions

ECS task roles follow least privilege — only the specific S3 and CloudWatch actions needed are allowed, no FullAccess policies.

ECS instances and the RDS database run in private subnets and are not reachable from the internet directly.

The ALB security group only allows HTTP and HTTPS traffic.

The S3 bucket has server-side encryption enabled and SSL is enforced on all requests.

The RDS instance has storage encryption enabled.

## Cleaning Up

To remove all the deployed resources and stop incurring AWS charges, run:
```bash
cdk destroy
```

## Bonus Features

An RDS PostgreSQL instance is included in the private subnets with encryption at rest.

IAM policies are scoped to least privilege instead of using broad managed policies.

S3 bucket versioning is enabled.

Health checks are configured on the ALB target group.

CORS on the S3 bucket is restricted to the ALB DNS origin only.
