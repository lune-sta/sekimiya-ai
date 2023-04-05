#!/usr/bin/env node
import 'source-map-support/register'
import * as cdk from 'aws-cdk-lib'
import { IConstruct } from 'constructs'
import { SekimiyaAiStack } from '../lib/sekimiya-ai-stack'

const app = new cdk.App()

class DeletionPolicySetter implements cdk.IAspect {
  constructor(private readonly policy: cdk.RemovalPolicy) {}
  visit(node: IConstruct): void {
    if (node instanceof cdk.CfnResource) {
      node.applyRemovalPolicy(this.policy)
    }
  }
}

const stack = new SekimiyaAiStack(app, 'SekimiyaAiStack', {
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: 'us-west-2' },
})

cdk.Aspects.of(stack).add(new DeletionPolicySetter(cdk.RemovalPolicy.DESTROY))
