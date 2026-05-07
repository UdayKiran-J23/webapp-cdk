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

        # 1. VPC Configuration
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

        # 2. ECS Cluster & Auto Scaling Group
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

        # IAM Role for ECS tasks
        task_role = iam.Role(self, "EcsTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )
        # Allows interacting with S3 and CloudWatch as per requirements
        task_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"))
        task_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchFullAccess"))

        execution_role = iam.Role(self, "EcsTaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )
        execution_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy"))

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
        # Port 0 means dynamic port mapping for bridge mode
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

        # 3. Application Load Balancer
        alb = elbv2.ApplicationLoadBalancer(self, "WebAppALB",
            vpc=vpc,
            internet_facing=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)
        )

        # Configure Security Groups for ALB
        alb.connections.allow_from_any_ipv4(
            ec2.Port.tcp(80),
            "Allow HTTP traffic from internet"
        )
        alb.connections.allow_from_any_ipv4(
            ec2.Port.tcp(443),
            "Allow HTTPS traffic from internet"
        )

        listener = alb.add_listener("PublicListener",
            port=80,
            open=True
        )

        listener.add_targets("ECS",
            port=80,
            targets=[service.load_balancer_target(
                container_name="WebAppContainer",
                container_port=80
            )]
        )

        # Allow ALB to communicate with the ECS instances on ephemeral ports for dynamic port mapping
        asg.connections.allow_from(alb, ec2.Port.tcp_range(32768, 65535), "Allow traffic from ALB on ephemeral ports")

        # 4. S3 Bucket
        bucket = s3.Bucket(self, "WebAppAssetsBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            cors=[s3.CorsRule(
                allowed_methods=[s3.HttpMethods.GET],
                allowed_origins=["*"],
                allowed_headers=["*"]
            )],
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # 5. RDS (Bonus Feature)
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
            credentials=rds.Credentials.from_secret(db_secret),
            removal_policy=RemovalPolicy.DESTROY,
            deletion_protection=False
        )
        # Allow ASG (ECS instances) to connect to RDS
        rds_instance.connections.allow_default_port_from(asg)

        # 6. CloudFormation Outputs
        CfnOutput(self, "LoadBalancerDNS",
            value=alb.load_balancer_dns_name,
            description="Application Load Balancer DNS Name"
        )
        
        CfnOutput(self, "S3BucketName",
            value=bucket.bucket_name,
            description="S3 Bucket Name"
        )

        CfnOutput(self, "RDSEndpoint",
            value=rds_instance.db_instance_endpoint_address,
            description="RDS Instance Endpoint Address"
        )
