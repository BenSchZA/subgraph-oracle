import aws_cdk as core
import aws_cdk.assertions as assertions

from sao_stack.stack import SAOStack

# example tests. To run these tests, uncomment this file along with the example
# resource in subgraph_availability_oracle_sepolia/subgraph_availability_oracle_sepolia_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = SAOStack(app, "arbitrum-sepolia")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
