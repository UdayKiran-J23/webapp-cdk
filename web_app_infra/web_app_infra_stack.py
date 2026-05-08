from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_autoscaling as autoscaling,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_s3 as s3,
    aws_rds as rds,
)
from constructs import Construct


class WebAppInfraStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -------------------------
        # 1. VPC Configuration
        # -------------------------
        vpc = ec2.Vpc(self, "WebAppVpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                )
            ]
        )

        # -------------------------
        # 2. ECS Cluster & Auto Scaling Group
        # -------------------------
        cluster = ecs.Cluster(self, "WebAppCluster", vpc=vpc)

        asg = autoscaling.AutoScalingGroup(self, "WebAppASG",
            vpc=vpc,
            instance_type=ec2.InstanceType("t3.micro"),
            machine_image=ecs.EcsOptimizedImage.amazon_linux2023(),
            min_capacity=2,
            max_capacity=4,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        )

        capacity_provider = ecs.AsgCapacityProvider(self, "AsgCapacityProvider",
            auto_scaling_group=asg
        )
        cluster.add_asg_capacity_provider(capacity_provider)

        # IAM Role for ECS Tasks - Least Privilege
        task_role = iam.Role(self, "EcsTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )

        # Least privilege: only specific S3 and CloudWatch actions
        task_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket",
            ],
            resources=["*"]
        ))

        task_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "cloudwatch:PutMetricData",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogStreams"
            ],
            resources=["*"]
        ))

        execution_role = iam.Role(self, "EcsTaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )
        execution_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
        )

        # Task Definition
        task_definition = ecs.Ec2TaskDefinition(self, "WebAppTaskDef",
            task_role=task_role,
            execution_role=execution_role,
            network_mode=ecs.NetworkMode.BRIDGE
        )

        container = task_definition.add_container("WebAppContainer",
            image=ecs.ContainerImage.from_registry("nginxdemos/hello"),
            memory_limit_mib=256,
            cpu=128
        )
        container.add_port_mappings(ecs.PortMapping(container_port=80, host_port=0))

        # ECS Service
        service = ecs.Ec2Service(self, "WebAppService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=2,
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(
                    capacity_provider=capacity_provider.capacity_provider_name,
                    weight=1
                )
            ]
        )

        # -------------------------
        # 3. Application Load Balancer
        # -------------------------

        # ALB Security Group - only allow HTTP (80) and HTTPS (443)
        alb_sg = ec2.SecurityGroup(self, "AlbSecurityGroup",
            vpc=vpc,
            description="Allow HTTP and HTTPS traffic only",
            allow_all_outbound=True
        )
        alb_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "Allow HTTP")
        alb_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "Allow HTTPS")

        alb = elbv2.ApplicationLoadBalancer(self, "WebAppALB",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_sg,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)
        )

        # HTTP Listener on port 80
        listener = alb.add_listener("HttpListener",
            port=80,
            open=False  # Security group already controls access
        )

        listener.add_targets("EcsTargets",
            port=80,
            targets=[service.load_balancer_target(
                container_name="WebAppContainer",
                container_port=80
            )],
            health_check=elbv2.HealthCheck(
                path="/",
                healthy_http_codes="200"
            )
        )

        # Allow ALB to reach ECS instances on ephemeral ports (dynamic port mapping)
        asg.connections.allow_from(
            alb,
            ec2.Port.tcp_range(32768, 65535),
            "Allow ALB to reach ECS on ephemeral ports"
        )

        # -------------------------
        # 4. S3 Bucket (Private + Pre-signed URL ready)
        # -------------------------
        bucket = s3.Bucket(self, "WebAppAssetsBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            cors=[s3.CorsRule(
                allowed_methods=[s3.HttpMethods.GET, s3.HttpMethods.PUT],
                allowed_origins=[f"http://{alb.load_balancer_dns_name}"],
                allowed_headers=["*"],
                max_age=3000
            )],
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # Grant ECS task role access to the bucket
        bucket.grant_read_write(task_role)

        # -------------------------
        # 5. RDS PostgreSQL (Bonus Feature)
        # -------------------------
        db_secret = rds.DatabaseSecret(self, "DbSecret", username="dbadmin")

        rds_instance = rds.DatabaseInstance(self, "WebAppDB",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15
            ),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            multi_az=False,
            allocated_storage=20,
            storage_encrypted=True,
            credentials=rds.Credentials.from_secret(db_secret),
            removal_policy=RemovalPolicy.DESTROY,
            deletion_protection=False
        )

        # Allow ECS instances to connect to RDS
        rds_instance.connections.allow_default_port_from(asg)

        # -------------------------
        # 6. CloudFormation Outputs
        # -------------------------
        CfnOutput(self, "LoadBalancerDNS",
            value=alb.load_balancer_dns_name,
            description="Application Load Balancer DNS Name - Access your web app here"
        )

        CfnOutput(self, "S3BucketName",
            value=bucket.bucket_name,
            description="S3 Bucket Name - Use this to generate pre-signed URLs"
        )

        CfnOutput(self, "RDSEndpoint",
            value=rds_instance.db_instance_endpoint_address,
            description="RDS PostgreSQL Endpoint Address"
        )
