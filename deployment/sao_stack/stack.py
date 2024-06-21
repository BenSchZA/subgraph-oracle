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
)
from constructs import Construct
import os

class SAOStack(Stack):

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            environment_variables: dict,
            signing_key_ssm_parameter_name: str,
            **kwargs
        ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Define VPC with multiple availability zones
        vpc = ec2.Vpc(self, "VPC", max_azs=3)

        # Create the ECS cluster
        cluster = ecs.Cluster(
            self,
            "FargateCluster",
            cluster_name=f"sao-{construct_id}",
            vpc=vpc,
            container_insights=True,
        )

        # Add EC2 capacity to the cluster
        auto_scaling_group = cluster.add_capacity(
            "DefaultAutoScalingGroup",
            instance_type=ec2.InstanceType("t3.small"),
            min_capacity=2,
            max_capacity=5,
            desired_capacity=2
        )

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
            memory_limit_mib=512,
            cpu=256,
            execution_role=execution_role,
        )

        sao_container = sao_task_definition.add_container(
            f"sao-{construct_id}",
            image=ecs.ContainerImage.from_ecr_repository(repository, tag="latest"),
            logging=ecs.LogDriver.aws_logs(log_group=log_group, stream_prefix="ecs"),
            command=[
                "--dry-run",
            ],
            environment=environment_variables,
            secrets={
                "ORACLE_SIGNING_KEY": ecs.Secret.from_ssm_parameter(signing_key)
            },
        )

        # Create a CloudWatch Events rule to run the task every 5 minutes
        rule = events.Rule(
            self, "ScheduleRule", schedule=events.Schedule.rate(Duration.minutes(5))
        )

        rule.add_target(
            targets.EcsTask(
                cluster=cluster,
                task_definition=sao_task_definition,
                task_count=1,
                subnet_selection=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
                launch_type=ecs.LaunchType.FARGATE,
                platform_version=ecs.FargatePlatformVersion.LATEST
            )
        )

#         # Create S3 bucket to store Prometheus config
#         bucket = s3.Bucket(self, "PrometheusConfigBucket")

#         # Define the Prometheus configuration content with dynamic SAO service discovery
#         prometheus_config_content = f"""
# global:
#     scrape_interval: 15s

# scrape_configs:
#     - job_name: 'sao'
#     static_configs:
#         - targets: ['localhost:8090']
#         """

#         # Save the Prometheus configuration content to a file
#         prometheus_config_path = os.path.join(os.getcwd(), "prometheus.yml")
#         with open(prometheus_config_path, "w") as f:
#             f.write(prometheus_config_content)

#         # Create an asset for the Prometheus configuration file
#         prometheus_config_asset = s3_assets.Asset(self, "PrometheusConfigAsset",
#             path=prometheus_config_path
#         )

#         # Create Task Definition for Prometheus
#         prometheus_task_definition = ecs.Ec2TaskDefinition(
#             self,
#             "PrometheusTaskDef",
#             network_mode=ecs.NetworkMode.AWS_VPC,
#         )

#         prometheus_container = prometheus_task_definition.add_container(
#             "prometheus",
#             image=ecs.ContainerImage.from_registry("prom/prometheus"),
#             logging=ecs.LogDriver.aws_logs(stream_prefix="Prometheus"),
#             environment={
#                 'S3_BUCKET': bucket.bucket_name,
#                 'S3_KEY': prometheus_config_asset.s3_object_key
#             },
#             command=[
#                 '--config.file=/etc/prometheus/prometheus.yml'
#             ],
#             memory_limit_mib=1024,
#         )

#         prometheus_container.add_port_mappings(
#             ecs.PortMapping(container_port=9090)
#         )

#         # Add volume and mount point for Prometheus configuration
#         prometheus_task_definition.add_volume(
#             name="prometheus-config",
#             host=ecs.Host(
#                 source_path=None
#             )
#         )

#         prometheus_container.add_mount_points(
#             ecs.MountPoint(
#                 container_path="/etc/prometheus",
#                 source_volume="prometheus-config",
#                 read_only=False
#             )
#         )

#         # Add permissions to the task role to read from S3
#         prometheus_task_definition.task_role.add_to_policy(
#             iam.PolicyStatement(
#                 actions=["s3:GetObject"],
#                 resources=[bucket.arn_for_objects(prometheus_config_asset.s3_object_key)]
#             )
#         )

#         # Add an init container to copy the configuration file from S3
#         prometheus_config_init_container = prometheus_task_definition.add_container(
#             "prometheus-config-init",
#             image=ecs.ContainerImage.from_registry("amazonlinux"),
#             command=[
#                 'sh', '-c',
#                 'yum install -y aws-cli && '
#                 'aws s3 cp s3://$S3_BUCKET/$S3_KEY /etc/prometheus/prometheus.yml'
#             ],
#             essential=True,
#             environment={
#                 'S3_BUCKET': bucket.bucket_name,
#                 'S3_KEY': prometheus_config_asset.s3_object_key
#             },
#             memory_reservation_mib=128,
#             user="root",
#         )

#         prometheus_config_init_container.add_mount_points(
#             ecs.MountPoint(
#                 container_path="/etc/prometheus",
#                 source_volume="prometheus-config",
#                 read_only=False
#             )
#         )

#         # Create Security Group for Prometheus
#         prometheus_security_group = ec2.SecurityGroup(
#             self,
#             "PrometheusSG",
#             vpc=vpc,
#             description="Allow traffic to Prometheus",
#             allow_all_outbound=True
#         )

#         prometheus_security_group.add_ingress_rule(
#             ec2.Peer.ipv4(vpc.vpc_cidr_block),
#             ec2.Port.tcp(9090),
#             "Allow internal Prometheus access"
#         )

#         # Create EC2 Service for Prometheus
#         prometheus_service = ecs.Ec2Service(
#             self,
#             "PrometheusService",
#             cluster=cluster,
#             task_definition=prometheus_task_definition,
#             desired_count=1,
#             security_groups=[prometheus_security_group],
#             vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
#         )

#         # Create Task Definition for Grafana
#         grafana_task_definition = ecs.Ec2TaskDefinition(
#             self,
#             "GrafanaTaskDef",
#             network_mode=ecs.NetworkMode.AWS_VPC,
#         )

#         grafana_container = grafana_task_definition.add_container(
#             "grafana",
#             image=ecs.ContainerImage.from_registry("grafana/grafana"),
#             logging=ecs.LogDriver.aws_logs(stream_prefix="Grafana"),
#             environment={
#                 'GF_SECURITY_ADMIN_USER': 'admin',
#                 'GF_SECURITY_ADMIN_PASSWORD': 'your_secure_password'
#             },
#             memory_limit_mib=1024
#         )

#         grafana_container.add_port_mappings(
#             ecs.PortMapping(container_port=3000)
#         )

#         # Create Security Group for Grafana
#         grafana_security_group = ec2.SecurityGroup(
#             self,
#             "GrafanaSG",
#             vpc=vpc,
#             description="Allow traffic to Grafana",
#             allow_all_outbound=True
#         )

#         grafana_security_group.add_ingress_rule(
#             ec2.Peer.any_ipv4(),
#             ec2.Port.tcp(3000),
#             "Allow public Grafana access"
#         )

#         # Create EC2 Service for Grafana
#         grafana_service = ecs.Ec2Service(
#             self,
#             "GrafanaService",
#             cluster=cluster,
#             task_definition=grafana_task_definition,
#             desired_count=1,
#             security_groups=[grafana_security_group],
#             vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
#         )

#         # Create an Application Load Balancer for Grafana
#         lb = elbv2.ApplicationLoadBalancer(
#             self, "GrafanaLB",
#             vpc=vpc,
#             internet_facing=True,
#             security_group=grafana_security_group
#         )

#         listener = lb.add_listener("GrafanaListener", port=80)
#         listener.add_targets("GrafanaTarget", 
#             port=3000, 
#             targets=[grafana_service],
#             protocol=elbv2.ApplicationProtocol.HTTP,
#             health_check=elbv2.HealthCheck(
#                 path="/api/health",
#                 interval=Duration.seconds(30),
#                 timeout=Duration.seconds(5),
#                 healthy_http_codes="200"
#             )
#         )

#         # Outputs
#         self.output = {
#             'PrometheusLocalAccess': f"http://{prometheus_service.service_name}:9090",
#             'GrafanaURL': f"http://{lb.load_balancer_dns_name}"
#         }