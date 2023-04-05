# Sekimiya AI

関宮エーアイ研究室で使われている Bot のソースコードです。

## Requirements
- Node.js (LTS)
- Docker
- AWS CLI

## デプロイ手順

```
$ export AWS_DEFAULT_REGION=us-west-2
$ aws ssm put-parameter --type 'SecureString' --name '/sekimiya-ai/discord-token' \                                        
  --region us-west-2 --value '<Discord の Token>'
$ aws ssm put-parameter --type 'SecureString' --name '/sekimiya-ai/openai-secret' \
  --region us-west-2 --value '<OpenAI API の Secret>'
$ aws ssm put-parameter --type 'String' --name '/sekimiya-ai/fx-channel-id' \
  --region us-west-2 --value '<Discord の FX Channel の ID>'
$ npm install
$ cdk bootstrap
$ cdk deploy
```
