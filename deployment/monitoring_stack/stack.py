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

class MonitoringStack(Stack):

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            vpc: ec2.Vpc,
            environment_variables: dict,
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
        cluster.add_capacity(
            "T3MicroAutoScalingGroup",
            instance_type=ec2.InstanceType("t3.micro"),
            min_capacity=0,
            max_capacity=2,
        )

        cluster.add_capacity(
            "T3XLargeAutoScalingGroup",
            instance_type=ec2.InstanceType("t3.xlarge"),
            min_capacity=0,
            max_capacity=1,
        )

        # Create S3 bucket to store Prometheus config
        bucket = s3.Bucket(self, "PrometheusConfigBucket")

        # Define the Prometheus configuration content with dynamic SAO service discovery
        prometheus_config_content = f"""
global:
    scrape_interval: 15s

scrape_configs:
    - job_name: 'sao'
    static_configs:
        - targets: ['localhost:8090']
        """

        # Save the Prometheus configuration content to a file
        prometheus_config_path = os.path.join(os.getcwd(), "prometheus.yml")
        with open(prometheus_config_path, "w") as f:
            f.write(prometheus_config_content)

        # Create an asset for the Prometheus configuration file
        prometheus_config_asset = s3_assets.Asset(self, "PrometheusConfigAsset",
            path=prometheus_config_path
        )

        # Create Task Definition for Prometheus
        prometheus_task_definition = ecs.Ec2TaskDefinition(
            self,
            "PrometheusTaskDef",
            network_mode=ecs.NetworkMode.AWS_VPC,
        )

        prometheus_container = prometheus_task_definition.add_container(
            "prometheus",
            image=ecs.ContainerImage.from_registry("prom/prometheus"),
            logging=ecs.LogDriver.aws_logs(stream_prefix="Prometheus"),
            environment={
                'S3_BUCKET': bucket.bucket_name,
                'S3_KEY': prometheus_config_asset.s3_object_key
            },
            command=[
                '--config.file=/etc/prometheus/prometheus.yml'
            ],
            # cpu=cpu,
            memory_limit_mib=1024 * 14,  # 14 GB for buffer of 2 GB
        )

        prometheus_container.add_port_mappings(
            ecs.PortMapping(container_port=9090)
        )

        # Add volume and mount point for Prometheus configuration
        prometheus_task_definition.add_volume(
            name="prometheus-config",
            host=ecs.Host(
                source_path=None
            )
        )

        prometheus_container.add_mount_points(
            ecs.MountPoint(
                container_path="/etc/prometheus",
                source_volume="prometheus-config",
                read_only=False
            )
        )

        # Add permissions to the task role to read from S3
        prometheus_task_definition.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[bucket.arn_for_objects(prometheus_config_asset.s3_object_key)]
            )
        )

        # Add an init container to copy the configuration file from S3
        prometheus_config_init_container = prometheus_task_definition.add_container(
            "prometheus-config-init",
            image=ecs.ContainerImage.from_registry("amazonlinux"),
            command=[
                'sh', '-c',
                'yum install -y aws-cli && '
                'aws s3 cp s3://$S3_BUCKET/$S3_KEY /etc/prometheus/prometheus.yml'
            ],
            essential=True,
            environment={
                'S3_BUCKET': bucket.bucket_name,
                'S3_KEY': prometheus_config_asset.s3_object_key
            },
            memory_reservation_mib=128,
            user="root",
        )

        prometheus_config_init_container.add_mount_points(
            ecs.MountPoint(
                container_path="/etc/prometheus",
                source_volume="prometheus-config",
                read_only=False
            )
        )

        # Create Security Group for Prometheus
        prometheus_security_group = ec2.SecurityGroup(
            self,
            "PrometheusSG",
            vpc=vpc,
            description="Allow traffic to Prometheus",
            allow_all_outbound=True
        )

        prometheus_security_group.add_ingress_rule(
            ec2.Peer.ipv4(vpc.vpc_cidr_block),
            ec2.Port.tcp(9090),
            "Allow internal Prometheus access"
        )

        # Create EC2 Service for Prometheus
        prometheus_service = ecs.Ec2Service(
            self,
            "PrometheusService",
            cluster=cluster,
            task_definition=prometheus_task_definition,
            desired_count=1,
            security_groups=[prometheus_security_group],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )

        # Create Task Definition for Grafana
        grafana_task_definition = ecs.Ec2TaskDefinition(
            self,
            "GrafanaTaskDef",
            network_mode=ecs.NetworkMode.AWS_VPC,
        )

        grafana_container = grafana_task_definition.add_container(
            "grafana",
            image=ecs.ContainerImage.from_registry("grafana/grafana"),
            logging=ecs.LogDriver.aws_logs(stream_prefix="Grafana"),
            environment={
                'GF_SECURITY_ADMIN_USER': 'admin',
                'GF_SECURITY_ADMIN_PASSWORD': 'your_secure_password'
            },
            # cpu=cpu,
            memory_limit_mib=512,
        )

        grafana_container.add_port_mappings(
            ecs.PortMapping(container_port=3000)
        )

        # Create Security Group for Grafana
        grafana_security_group = ec2.SecurityGroup(
            self,
            "GrafanaSG",
            vpc=vpc,
            description="Allow traffic to Grafana",
            allow_all_outbound=True
        )

        grafana_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(3000),
            "Allow public Grafana access"
        )

        # Create EC2 Service for Grafana
        grafana_service = ecs.Ec2Service(
            self,
            "GrafanaService",
            cluster=cluster,
            task_definition=grafana_task_definition,
            desired_count=1,
            security_groups=[grafana_security_group],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        # Create an Application Load Balancer for Grafana
        lb = elbv2.ApplicationLoadBalancer(
            self, "GrafanaLB",
            vpc=vpc,
            internet_facing=True,
            security_group=grafana_security_group
        )

        listener = lb.add_listener("GrafanaListener", port=80)
        listener.add_targets("GrafanaTarget", 
            port=3000, 
            targets=[grafana_service],
            protocol=elbv2.ApplicationProtocol.HTTP,
            health_check=elbv2.HealthCheck(
                path="/api/health",
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                healthy_http_codes="200"
            )
        )

        # Outputs
        self.output = {
            'PrometheusLocalAccess': f"http://{prometheus_service.service_name}:9090",
            'GrafanaURL': f"http://{lb.load_balancer_dns_name}"
        }