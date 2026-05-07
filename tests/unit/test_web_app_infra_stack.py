import aws_cdk as core
import aws_cdk.assertions as assertions

from web_app_infra.web_app_infra_stack import WebAppInfraStack

# example tests. To run these tests, uncomment this file along with the example
# resource in web_app_infra/web_app_infra_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = WebAppInfraStack(app, "web-app-infra")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
