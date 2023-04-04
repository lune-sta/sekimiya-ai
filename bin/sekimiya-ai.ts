#!/usr/bin/env node
import 'source-map-support/register'
import * as cdk from 'aws-cdk-lib'
import { SekimiyaAiStack } from '../lib/sekimiya-ai-stack'

const app = new cdk.App()
new SekimiyaAiStack(app, 'SekimiyaAiStack', {
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: 'us-west-2' },
})
