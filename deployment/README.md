
# Welcome to your CDK Python project!

This is a blank project for CDK development with Python.

The `cdk.json` file tells the CDK Toolkit how to execute your app.

This project is set up like a standard Python project.  The initialization
process also creates a virtualenv within this project, stored under the `.venv`
directory.  To create the virtualenv it assumes that there is a `python3`
(or `python` for Windows) executable in your path with access to the `venv`
package. If for any reason the automatic creation of the virtualenv fails,
you can create the virtualenv manually.

To manually create a virtualenv on MacOS and Linux:

```
$ python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .venv/bin/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .venv\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

At this point you can now synthesize the CloudFormation template for this code.

```
$ cdk synth
```

To add additional dependencies, for example other CDK libraries, just add
them to your `setup.py` file and rerun the `pip install -r requirements.txt`
command.

## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation

Enjoy!

# DataEdge Transaction Guide

Copied from The Graph Notion workspace: https://thegraphfoundation.notion.site/SAO-Decentralization-Project-Shared-Workspace-77213794e9864fbf99bf919d40a0b180?pvs=4

## Introduction to the `DataEdge` Contract

The `DataEdge` contract is used to store arbitrary data on-chain on any EVM compatible blockchain. A subgraph can then read all the calldata sent to a particular contract, decode it and update the subgraph state accordingly.

The `DataEdge` accepts any function call by using a fallback function that will not revert. It is up to the implementor to define the calldata format as well as how to decode it.

## Constructing the Calldata

To ensure the subgraph can decode the calldata correctly, we need to follow a specific format. To simplify this process, we provide a JSON encoder web application.

https://graphprotocol.github.io/subgraph-oracle/

The encoder web app contains a sample JSON with default values. This should be reviewed and updated to match your specific configuration.

```json
{
	"version": "v0.0.1",
	"config": {
		"ipfs_concurrency": "4",
		"ipfs_timeout": "10000",
		"min_signal": "100",
		"period": "300",
		"grace_period": "0",
		"supported_data_source_kinds": "ethereum,ethereum/contract,file/ipfs,substreams,file/arweave",
		"network_subgraph_deloyment_id": "QmSWxvd8SaQK6qZKJ7xtfxCCGoRzGnoi2WNzmJYYJW9BXY",
		"epoch_block_oracle_subgraph_deloyment_id": "QmQEGDTb3xeykCXLdWx7pPX3qeeGMUvHmGWP4SpMkv5QJf",
		"subgraph_availability_manager_contract": "CONTRACT_ADDRESS",
		"oracle_index": "ORACLE_INDEX"
	}
}
```

Each operator should set their own `ORACLE_INDEX` and update the JSON with the appropriate version, subgraph deployment IDs, etc.

After verifying that the JSON contains the correct configuration values, compile the calldata by selecting `calldata` for the `Output type` and clicking the `Compile` button.

![Screenshot 2024-06-14 at 11.14.36.png](https://prod-files-secure.s3.us-west-2.amazonaws.com/24decb71-0e1c-4c5a-be73-c3518e2faba4/67fedf01-0fee-4a77-8669-b018f37ccb54/Screenshot_2024-06-14_at_11.14.36.png)

With the calldata compiled, proceed to the next step: posting the transaction to the `DataEdge` contract.

## Posting the Transaction

To post the transaction, send the calldata to the `DataEdge` contract using the same signer as your oracle account. You can use your preferred method for executing the transaction. Here, we provide a guide using a Hardhat task from the `graphprotocol/contracts` repository.

First, clone the contracts repository if you have not already done so:

```bash
> git clone git@github.com:graphprotocol/contracts.git && cd contracts
```

Follow the `Setup` steps in the [Readme.md](https://github.com/graphprotocol/contracts?tab=readme-ov-file#setup) to set up the project.

Next, navigate to the `data-edge` package:

```bash
> cd packages/data-edge
```

You are now ready to send your transaction using the `data:post` Hardhat task:

```bash
# NB: DATA_EDGE_CALLDATA should start with 0x
# NB: if you receive an "invalid mnemonic" error, try starting command with MNEMONIC="..."
npx hardhat data:post --edge $DATA_EDGE_CONTRACT --network arbitrum-one --data $DATA_EDGE_CALLDATA
```

### Arbitrum Sepolia

```bash
> MNEMONIC="TESTNET_ORACLE_ACCOUNT_MNEMONIC" npx hardhat data:post --edge 0xB61AF143c79Cbdd68f179B657AaC86665CC2B469 --network arbitrum-sepolia --data "0xCALLDATA"
```

### Arbitrum One

```bash
> MNEMONIC="PRODUCTION_ORACLE_ACCOUNT_MNEMONIC" npx hardhat data:post --edge 0xeD16cEbd4fa74a0016E1149cc03563Db4B223aec --network arbitrum-one --data "0xCALLDATA"
```

## Verifying Configuration

After posting your calldata, verify the configuration update by querying the subgraph:

- Arbitrum Sepolia: https://thegraph.com/explorer/subgraphs/Ec78hWTvrWxadwFnwDGdTgSaSEVZANqVo7dZ5tB9H3B4?view=Query&chain=arbitrum-one
- Arbitrum One: https://thegraph.com/explorer/subgraphs/9DR6unCi6gxi5CfJDszZygF4uA4j2qyTCxsJttw1CwdK?view=Query&chain=arbitrum-one

Use the following GraphQL query to check the configuration:

```graphql
{
  globalState(id: "0") {
    activeOracles(where:{index:"ORACLE_INDEX"}) {
      id
      latestConfig{
        version
        ipfsConcurrency
        ipfsTimeout
        minSignal
        period
        gracePeriod
        supportedDataSourceKinds
        networkSubgraphDeploymentId
        epochBlockOracleSubgraphDeploymentId
        subgraphAvailabilityManagerContract
        oracleIndex
      }
    }
  }
}
```

Replace `ORACLE_INDEX` with your corresponding oracle’s index value.