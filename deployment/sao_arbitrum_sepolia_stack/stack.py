from aws_cdk import (
    Duration,
    Stack,
    RemovalPolicy,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_events as events,
    aws_events_targets as targets,
    aws_logs as logs,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_ssm as ssm
)
from constructs import Construct


class SAOArbitrumSepoliaStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Define VPC with multiple availability zones
        vpc = ec2.Vpc(self, "VPC", max_azs=3)

        # Create the ECS cluster
        cluster = ecs.Cluster(
            self,
            "FargateCluster",
            cluster_name="sao_arbitrum_sepolia",
            vpc=vpc,
            container_insights=True,
        )

        # Create the log group for the task
        log_group = logs.LogGroup(
            self,
            "LogGroup",
            log_group_name="/ecs/sao_arbitrum_sepolia_fargate_task",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Define the task execution role
        execution_role = iam.Role(
            self,
            "FargateTaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

        # Add the necessary permissions for security group ingress to the execution role
        execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ec2:AuthorizeSecurityGroupIngress"],
                resources=["*"]  # You can specify more restrictive resource ARNs if needed
            )
        )

        # Create the ECR repository
        repository = ecr.Repository.from_repository_attributes(
            self,
            "SAORepository",
            repository_arn="arn:aws:ecr:eu-north-1:891377045977:repository/graphprotocol/subgraph-availability-oracle",
            repository_name="graphprotocol/subgraph-availability-oracle",
        )

        # Fetch the signing key from SSM Parameter Store
        signing_key = ssm.StringParameter.from_secure_string_parameter_attributes(
            self, "SigningKey",
            parameter_name="/sao/arbitrum/sepolia/ORACLE_SIGNING_KEY"
        )

        # Create the task definition
        task_definition = ecs.FargateTaskDefinition(
            self,
            "TaskDef",
            memory_limit_mib=512,
            cpu=256,
            execution_role=execution_role,
        )

        task_definition.add_container(
            "sao_arbitrum_sepolia",
            image=ecs.ContainerImage.from_ecr_repository(repository, tag="latest"),
            logging=ecs.LogDriver.aws_logs(log_group=log_group, stream_prefix="ecs"),
            command=[
                # "--dry-run",
                "--ipfs", "https://api.thegraph.com/ipfs",
                "--subgraph", "https://api.thegraph.com/subgraphs/name/graphprotocol/graph-network-arbitrum-sepolia",
                "--epoch-block-oracle-subgraph", "https://api.thegraph.com/subgraphs/name/graphprotocol/arbitrum-sepolia-ebo",
                "--ipfs-concurrency", "4",
                "--ipfs-timeout", "10000",
                "--min-signal", "100",
                # The task frequency is managed by CloudWatch Events
                # "--period", "300",
                "--subgraph-availability-manager-contract", "0x71D9aE967d1f31fbbD1817150902de78f8f2f73E",
                "--url", "https://arb-sepolia.g.alchemy.com/v2/71hNcKNJvQh6M2PcD0OpyPPRbsWHJrvw",
                "--oracle-index", "2",
            ],
            secrets={
                "ORACLE_SIGNING_KEY": ecs.Secret.from_ssm_parameter(signing_key)
            }
        )

        # Create the Fargate service
        ecs.FargateService(
            self,
            "FargateService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            assign_public_ip=True,
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(
                    capacity_provider="FARGATE_SPOT",
                    weight=1
                ),
                ecs.CapacityProviderStrategy(
                    capacity_provider="FARGATE",
                    weight=1
                )
            ]
        )

        # Create a CloudWatch Events rule to run the task every 5 minutes
        rule = events.Rule(
            self, "ScheduleRule", schedule=events.Schedule.rate(Duration.minutes(5))
        )

        rule.add_target(
            targets.EcsTask(
                cluster=cluster,
                task_definition=task_definition,
                task_count=1,
                subnet_selection=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            )
        )
