#!/usr/bin/env python3
import os
import aws_cdk as cdk
from dotenv import load_dotenv
from sao_stack.stack import SAOStack

app = cdk.App()
load_dotenv('../.env')

graph_api_key = os.getenv("GRAPH_API_KEY")

if not graph_api_key:
    raise ValueError("GRAPH_API_KEY must be set as an environment variable")

shared_environment_variables = {
    "ORACLE_IPFS": "https://api.thegraph.com/ipfs",
    "ORACLE_INDEX": "2",
    "ORACLE_IPFS_CONCURRENCY": "4",
    "ORACLE_IPFS_TIMEOUT_SECS": "10000",
    "ORACLE_MIN_SIGNAL": "100",
    # The task frequency is managed by CloudWatch Events
    # "ORACLE_PERIOD_SECS": "300",
    "SUPPORTED_DATA_SOURCE_KINDS": "ethereum,ethereum/contract,file/ipfs,substreams,file/arweave",
}

SAOStack(app, "arbitrum-sepolia",
    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.

    # Uncomment the next line to specialize this stack for the AWS Account
    # and Region that are implied by the current CLI configuration.

    #env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */

    #env=cdk.Environment(account='123456789012', region='us-east-1'),

    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html

    # Custom stack configuration
    environment_variables={
        **shared_environment_variables,
        "ORACLE_SUBGRAPH": "https://api.thegraph.com/subgraphs/name/graphprotocol/graph-network-arbitrum-sepolia",
        "EPOCH_BLOCK_ORACLE_SUBGRAPH": "https://api.thegraph.com/subgraphs/name/graphprotocol/arbitrum-sepolia-ebo",
        "SUBGRAPH_AVAILABILITY_MANAGER_CONTRACT": "0x71D9aE967d1f31fbbD1817150902de78f8f2f73E",
        "RPC_URL": "https://arb-sepolia.g.alchemy.com/v2/71hNcKNJvQh6M2PcD0OpyPPRbsWHJrvw",
    },
    signing_key_ssm_parameter_name="/sao/arbitrum/sepolia/ORACLE_SIGNING_KEY",
)

SAOStack(app, "arbitrum-one",
    # Custom stack configuration
    environment_variables={
        **shared_environment_variables,
        "ORACLE_SUBGRAPH": f"https://gateway-arbitrum.network.thegraph.com/api/{graph_api_key}/deployments/id/QmSWxvd8SaQK6qZKJ7xtfxCCGoRzGnoi2WNzmJYYJW9BXY",
        "EPOCH_BLOCK_ORACLE_SUBGRAPH": f"https://gateway-arbitrum.network.thegraph.com/api/{graph_api_key}/deployments/id/QmQEGDTb3xeykCXLdWx7pPX3qeeGMUvHmGWP4SpMkv5QJf",
        "SUBGRAPH_AVAILABILITY_MANAGER_CONTRACT": "0x1cB555359319A94280aCf85372Ac2323AaE2f5fd",
        "RPC_URL": " https://arb-mainnet.g.alchemy.com/v2/X2dOQoQvCqexaUJGypdBpmDF6JB1a4SV",
    },
    signing_key_ssm_parameter_name="/sao/arbitrum/one/ORACLE_SIGNING_KEY",
)

app.synth()
