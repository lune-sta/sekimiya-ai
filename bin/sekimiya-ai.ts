#!/usr/bin/env node
import 'source-map-support/register'
import * as cdk from 'aws-cdk-lib'
import { SekimiyaAiStack } from '../lib/sekimiya-ai-stack'
import { DeletionPolicySetter } from '../lib/deletion-policy-setter'

const app = new cdk.App()

const stack = new SekimiyaAiStack(app, 'SekimiyaAiStack', {
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: 'us-west-2' },
})

cdk.Aspects.of(stack).add(new DeletionPolicySetter(cdk.RemovalPolicy.DESTROY))
