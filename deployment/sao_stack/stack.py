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
    aws_ssm as ssm,
    aws_s3 as s3,
    aws_s3_assets as s3_assets,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ecs_patterns as ecs_patterns,
    aws_applicationautoscaling as appscaling,
)
from constructs import Construct
import os

class SAOStack(Stack):

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            vpc: ec2.Vpc,
            environment_variables: dict,
            signing_key_ssm_parameter_name: str,
            memory_limit_mib: int,
            cpu: int,
            **kwargs
        ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create the ECS cluster
        cluster = ecs.Cluster(
            self,
            "FargateCluster",
            cluster_name=f"sao-{construct_id}",
            vpc=vpc,
            container_insights=True,
        )

        # Add EC2 capacity to the cluster
        # auto_scaling_group = cluster.add_capacity(
        #     "DefaultAutoScalingGroup",
        #     instance_type=ec2.InstanceType("t3.small"),
        #     min_capacity=0,
        #     max_capacity=2,
        #     desired_capacity=2
        # )

        # Create the log group for the task
        log_group = logs.LogGroup(
            self,
            "LogGroup",
            log_group_name=f"/ecs/sao-fargate-task-{construct_id}",
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
            parameter_name=signing_key_ssm_parameter_name,
        )

        # Create the task definition
        sao_task_definition = ecs.FargateTaskDefinition(
            self,
            "TaskDef",
            memory_limit_mib=memory_limit_mib,
            cpu=cpu,
            execution_role=execution_role,
        )

        sao_container = sao_task_definition.add_container(
            f"sao-{construct_id}",
            # image=ecs.ContainerImage.from_registry("ghcr.io/graphprotocol/availability-oracle:sha-28312fd"),
            image=ecs.ContainerImage.from_ecr_repository(repository),
            logging=ecs.LogDriver.aws_logs(log_group=log_group, stream_prefix="ecs"),
            command=[
                # "--dry-run",
            ],
            environment=environment_variables,
            secrets={
                "ORACLE_SIGNING_KEY": ecs.Secret.from_ssm_parameter(signing_key)
            },
        )

        service = ecs.FargateService(self, "FargateService",
            cluster=cluster,
            task_definition=sao_task_definition,
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(
                    capacity_provider="FARGATE_SPOT",
                    weight=1  # Prefer Fargate Spot instances
                ),
                ecs.CapacityProviderStrategy(
                    capacity_provider="FARGATE",
                    weight=0  # Fallback to Fargate instances
                )
            ]
        )
