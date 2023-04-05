import * as cdk from 'aws-cdk-lib'
import { IConstruct } from 'constructs'
import * as s3 from 'aws-cdk-lib/aws-s3'
import * as ecr from 'aws-cdk-lib/aws-ecr'

export class DeletionPolicySetter implements cdk.IAspect {
  constructor(private readonly policy: cdk.RemovalPolicy) {}
  visit(node: IConstruct): void {
    if (node instanceof cdk.CfnResource) {
      node.applyRemovalPolicy(this.policy)
    }

    if (this.policy == cdk.RemovalPolicy.DESTROY) {
      if (node instanceof s3.Bucket) {
        node['enableAutoDeleteObjects']()
      }

      if (node instanceof ecr.Repository) {
        node['enableAutoDeleteImages']()
      }
    }
  }
}
