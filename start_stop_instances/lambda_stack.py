from aws_cdk import (
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as actions,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    core as cdk
)


class LambdaStack(cdk.Stack):
    def __init__(self, scope: cdk.Construct, construct_id: str, subscriber: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        publish_logs_to_cloudwatch = iam.ManagedPolicy(self, 'PublishLogsPolicy',
                                                       managed_policy_name='-'.join(
                                                           [construct_id, 'publish logs policy'.replace(' ', '-')]
                                                       ),
                                                       description='Policy to operate EC2 instances',
                                                       statements=[
                                                           iam.PolicyStatement(
                                                               sid='AllowPublishLogsToCloudwatch',
                                                               actions=[
                                                                   'logs:CreateLogGroup',
                                                                   'logs:CreateLogStream',
                                                                   'logs:PutLogEvents'
                                                               ],
                                                               resources=['arn:aws-cn:logs:*:*:*']
                                                           )
                                                       ]
                                                       )
        operating_ec2_policy = iam.ManagedPolicy(self, 'OperatingEC2Policy',
                                                 managed_policy_name='-'.join(
                                                     [construct_id, 'operating ec2 policy'.replace(' ', '-')]
                                                 ),
                                                 description='Policy to operate EC2 instances',
                                                 statements=[
                                                     iam.PolicyStatement(
                                                         sid='AllowStartStopEC2Instances',
                                                         actions=['ec2:StartInstances', 'ec2:StopInstances'],
                                                         resources=['arn:aws-cn:ec2:*:*:instance/*']
                                                     ),
                                                     iam.PolicyStatement(
                                                         sid='AllowDescribeEC2Instances',
                                                         actions=['ec2:DescribeInstances'],
                                                         resources=['*']
                                                     )
                                                 ]
                                                 )
        operating_rds_policy = iam.ManagedPolicy(self, 'OperatingRDSPolicy',
                                                 managed_policy_name='-'.join(
                                                     [construct_id, 'operating rds policy'.replace(' ', '-')]
                                                 ),
                                                 description='Policy to operate RDS instances',
                                                 statements=[
                                                     iam.PolicyStatement(
                                                         sid='AllowStartStopRDSInstances',
                                                         actions=['rds:StartDBInstance', 'rds:StopDBInstance'],
                                                         resources=['arn:aws-cn:rds:*:*:db:*']
                                                     ),
                                                     iam.PolicyStatement(
                                                         sid='AllowDescribeRDSInstances',
                                                         actions=['rds:DescribeDBInstances'],
                                                         resources=['arn:aws-cn:rds:*:*:db:*']
                                                     )
                                                 ]
                                                 )

        lambda_role = iam.Role(self, 'LambdaRole',
                               assumed_by=iam.ServicePrincipal('lambda.amazonaws.com.cn'),
                               description="IAM role for Lambda function",
                               managed_policies=[
                                   publish_logs_to_cloudwatch,
                                   operating_ec2_policy,
                                   operating_rds_policy
                               ],
                               role_name='-'.join([construct_id, 'role'.replace(' ', '-')]),
                               )
        lambda_function = _lambda.Function(self, 'LambdaFunction',
                                           code=_lambda.Code.from_asset(path="./start_stop_instances/lambda"),
                                           handler="start_stop_instances.lambda_handler",
                                           runtime=_lambda.Runtime.PYTHON_3_8,
                                           memory_size=128,
                                           role=lambda_role,
                                           timeout=cdk.Duration.seconds(900)
                                           )
        lambda_function.apply_removal_policy(cdk.RemovalPolicy.DESTROY)

        lambda_topic = sns.Topic(self, 'SNSTopicForLambda',
                                 display_name='Tell creator about failures in start-stop-instances lambda function.',
                                 topic_name='-'.join([construct_id, 'sns topic'.replace(' ', '-')])
                                 )
        lambda_topic.add_subscription(subscriptions.EmailSubscription(email_address=subscriber))
        lambda_topic.apply_removal_policy(cdk.RemovalPolicy.DESTROY)

        lambda_alarm = cloudwatch.Alarm(self, "LambdaAlarm",
                                        metric=(
                                            cloudwatch.Metric(
                                                metric_name='Errors',
                                                namespace='AWS/Lambda',
                                                dimensions_map={'FunctionName': lambda_function.function_name},
                                                period=cdk.Duration.minutes(1),
                                                statistic='Sum'
                                            )
                                        ),
                                        evaluation_periods=1,
                                        threshold=0,
                                        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD)
        lambda_alarm.apply_removal_policy(cdk.RemovalPolicy.DESTROY)
        lambda_alarm.add_alarm_action(actions.SnsAction(lambda_topic))
