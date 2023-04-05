import * as cdk from 'aws-cdk-lib'
import { Construct } from 'constructs'
import * as ec2 from 'aws-cdk-lib/aws-ec2'
import * as iam from 'aws-cdk-lib/aws-iam'
import * as ecs from 'aws-cdk-lib/aws-ecs'
import * as ecr from 'aws-cdk-lib/aws-ecr'
import * as logs from 'aws-cdk-lib/aws-logs'
import * as ssm from 'aws-cdk-lib/aws-ssm'
import * as lambda from 'aws-cdk-lib/aws-lambda'
import * as lambdaPython from '@aws-cdk/aws-lambda-python-alpha'
import * as events from 'aws-cdk-lib/aws-events'
import * as targets from 'aws-cdk-lib/aws-events-targets'
import * as imagedeploy from 'cdk-docker-image-deployment'
import { readFileSync } from 'fs'
import * as crypto from 'crypto'
import * as fs from 'fs'
import * as path from 'path'

function calculateDirectoryHash(directory: string): string {
  // ディレクトリのハッシュを計算 (Docker Image の Tag に使用)
  const hash = crypto.createHash('sha1')
  const files = fs.readdirSync(directory)

  files.forEach((file) => {
    const filePath = path.join(directory, file)
    const fileContent = fs.readFileSync(filePath)
    hash.update(fileContent)
  })

  return hash.digest('hex')
}

export class SekimiyaAiStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props)

    const { accountId, region } = new cdk.ScopedAws(this)

    // 秘密のパラメータを Get できるポリシー
    const allowGetSecureStringPolicy = new iam.ManagedPolicy(
      this,
      'AllowGetSecureString',
      {
        statements: [
          new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: ['ssm:GetParameters'],
            resources: [
              `arn:aws:ssm:${region}:${accountId}:parameter/sekimiya-ai/discord-token`,
              `arn:aws:ssm:${region}:${accountId}:parameter/sekimiya-ai/openai-secret`,
            ],
          }),
        ],
      }
    )

    // Frugally VPC
    const vpc = new ec2.Vpc(this, 'Vpc', {
      maxAzs: 1,
      natGateways: 1,
      natGatewayProvider: ec2.NatProvider.instance({
        instanceType: ec2.InstanceType.of(
          ec2.InstanceClass.T3,
          ec2.InstanceSize.NANO
        ),
      }),
    })

    // NAT Instance に Session Manager を使えるようにする
    const natInstance = vpc.node
      .findChild('PublicSubnet1')
      .node.findChild('NatInstance') as ec2.Instance
    natInstance.role.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonSSMManagedInstanceCore')
    )

    const cluster = new ecs.Cluster(this, 'Cluster', {
      vpc,
    })

    const repo = new ecr.Repository(this, 'Repository', {
      repositoryName: 'sekimiya-ai/chatbot',
    })

    repo.addLifecycleRule({
      maxImageCount: 3,
      tagStatus: ecr.TagStatus.ANY,
    })

    const tag = calculateDirectoryHash('./src/chatbot/')

    new imagedeploy.DockerImageDeployment(this, 'ImageDeploy', {
      source: imagedeploy.Source.directory('./src/chatbot/'),
      destination: imagedeploy.Destination.ecr(repo, {
        tag,
      }),
    })

    const taskDefinition = new ecs.FargateTaskDefinition(
      this,
      'TaskDefinition',
      {
        memoryLimitMiB: 512,
        cpu: 256,
      }
    )

    taskDefinition.addContainer('ChatBotContainer', {
      containerName: 'chatbot',
      image: ecs.ContainerImage.fromEcrRepository(repo, tag),
      logging: new ecs.AwsLogDriver({
        streamPrefix: 'chatbot',
      }),
      environment: {
        CHARACTER_SETTING: readFileSync('./lib/character_setting.txt', 'utf8'),
      },
    })

    // 環境変数 LOG_GROUP_NAME をセット
    const chatBotContainer = taskDefinition.node.findChild(
      'ChatBotContainer'
    ) as ecs.ContainerDefinition
    const logGroup = chatBotContainer.node.findChild('LogGroup').node
      .defaultChild as logs.CfnLogGroup
    chatBotContainer.addEnvironment('LOG_GROUP_NAME', logGroup.ref)

    // コンテナ内から Log を読めるようにする
    taskDefinition.taskRole.attachInlinePolicy(
      new iam.Policy(this, 'LogReadPolicy', {
        statements: [
          new iam.PolicyStatement({
            actions: ['logs:DescribeLogStreams', 'logs:GetLogEvents'],
            resources: [logGroup.attrArn],
            effect: iam.Effect.ALLOW,
          }),
        ],
      })
    )
    taskDefinition.taskRole.addManagedPolicy(allowGetSecureStringPolicy)

    new ecs.FargateService(this, 'Service', {
      cluster,
      taskDefinition,
      capacityProviderStrategies: [
        {
          capacityProvider: 'FARGATE',
          base: 0,
          weight: 0,
        },
        {
          capacityProvider: 'FARGATE_SPOT',
          base: 1,
          weight: 1,
        },
      ],
    })

    // Discord の FX Channel ID
    const channelId = ssm.StringParameter.valueFromLookup(
      this,
      '/sekimiya-ai/fx-channel-id'
    )

    const postIndicatorsFunction = new lambdaPython.PythonFunction(
      this,
      'PostIndicatorsFunction',
      {
        entry: './src/post_indicators',
        runtime: lambda.Runtime.PYTHON_3_8,
        index: 'main.py',
        handler: 'handler',
        memorySize: 1024,
        environment: {
          CHANNEL_ID: channelId,
          IMPORTANCE_LEVEL: '3', // 星3の重要指標だけお知らせ
        },
      }
    )

    postIndicatorsFunction.role?.addManagedPolicy(allowGetSecureStringPolicy)

    // 平日朝8時に起動
    const rule = new events.Rule(this, 'Rule', {
      schedule: events.Schedule.cron({
        hour: '23',
        minute: '0',
        weekDay: 'SUN-THU',
      }),
    })

    rule.addTarget(new targets.LambdaFunction(postIndicatorsFunction))
  }
}
