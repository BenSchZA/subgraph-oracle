from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
)
from constructs import Construct

class VPCStack(Stack):

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            **kwargs
        ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Define VPC with a single access zone and NAT gateway
        self.vpc = ec2.Vpc(self, "VPC",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/21"),
            max_azs=2,
            nat_gateways=1,
            # subnet_configuration=[
            #     ec2.SubnetConfiguration(
            #         name="public",
            #         subnet_type=ec2.SubnetType.PUBLIC,
            #     )
            # ]
        )

        # Create VPC endpoints for services that don't require internet access
        s3_endpoint = self.vpc.add_gateway_endpoint("S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3
        )

        ecr_api_endpoint = self.vpc.add_interface_endpoint("EcrApiEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.ECR
        )

        ecr_dkr_endpoint = self.vpc.add_interface_endpoint("EcrDkrEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER
        )

        ssm_endpoint = self.vpc.add_interface_endpoint("SsmEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SSM
        )

        ssm_messages_endpoint = self.vpc.add_interface_endpoint("SsmMessagesEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES
        )

        secrets_manager_endpoint = self.vpc.add_interface_endpoint("SecretsManagerEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER
        )

        ec2_messages_endpoint = self.vpc.add_interface_endpoint("Ec2MessagesEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.EC2_MESSAGES
        )

        logs_endpoint = self.vpc.add_interface_endpoint("LogsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS
        )