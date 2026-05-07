# Web Application Infrastructure using AWS CDK

This repository contains the infrastructure code to deploy a scalable, secure, and highly available web application on AWS using Python and the AWS Cloud Development Kit (CDK).

## Architecture

The stack provisions the following resources:
1. **VPC**: A Virtual Private Cloud with public and private subnets across 2 Availability Zones. Includes a NAT Gateway.
2. **ECS & ASG**: An Elastic Container Service (ECS) Cluster with an underlying Auto Scaling Group (min 2, max 4 instances). It runs instances in the private subnets.
3. **Application Load Balancer (ALB)**: Situated in the public subnets, this ALB distributes incoming HTTP traffic to the ECS tasks running `nginxdemos/hello`.
4. **S3 Bucket**: A secure, private S3 bucket meant for storing static assets, configured to allow CORS for pre-signed URLs.
5. **RDS Database**: A PostgreSQL database instance provisioned in the private subnets, accessible by the ECS application.

## Prerequisites

- **Python 3**: Ensure you have Python installed.
- **Node.js & npm**: Required to install the CDK CLI.
- **AWS CDK CLI**: Install globally via `npm install -g aws-cdk`.
- **AWS CLI**: Installed and configured with your AWS credentials (`aws configure`).

## Setup and Deployment

1. **Initialize Virtual Environment:**
   Create and activate a virtual environment in the root of the project:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install Dependencies:**
   Install the necessary Python requirements:
   ```bash
   pip install -r requirements.txt
   ```

3. **Bootstrap the Environment:**
   If this is your first time using CDK in your AWS account and region, you need to bootstrap it:
   ```bash
   cdk bootstrap aws://<ACCOUNT-ID>/<REGION>
   ```

4. **Synthesize the CloudFormation Template:**
   Verify that the CDK code synthesizes properly:
   ```bash
   cdk synth
   ```

5. **Deploy the Stack:**
   Deploy the infrastructure to your AWS account. You will be prompted to confirm security-related changes:
   ```bash
   cdk deploy
   ```

## Post-Deployment Outputs

After a successful deployment, the CDK CLI will output three important values:
- `LoadBalancerDNS`: The public DNS name of the ALB to access the `nginxdemos/hello` web service.
- `S3BucketName`: The name of the S3 bucket created for your static assets.
- `RDSEndpoint`: The endpoint address for your PostgreSQL database.

## Cleaning Up

To destroy the deployed resources and avoid incurring future charges, run:
```bash
cdk destroy
```

## Bonus Features Included
- Integrated an RDS PostgreSQL Instance in the private subnets.
- Configured secure default parameters (e.g., S3 Bucket Encryption, Block Public Access, IAM Least Privilege policies, Destroy Removal policies for easy teardown during testing).
