/**
 * DynamoDB access for user-owned Projects.
 *
 * Single-table layout: items live in the same `products-<stage>` table
 * as products/datasheets/manufacturers but in their own partition.
 *
 *   PK = `USER#{owner_sub}`
 *   SK = `PROJECT#{id}`
 *
 * The per-user partition scopes list/queries without needing a GSI.
 * Product membership is embedded as a list (`product_refs`); fine up
 * to ~hundreds of items per project before the 400KB item cap bites.
 */

import {
  DynamoDBClient,
  GetItemCommand,
  PutItemCommand,
  QueryCommand,
  DeleteItemCommand,
  UpdateItemCommand,
  ConditionalCheckFailedException,
} from '@aws-sdk/client-dynamodb';
import { marshall, unmarshall } from '@aws-sdk/util-dynamodb';
import { Project, ProductRef } from '../types/models';

export interface ProjectsServiceConfig {
  tableName: string;
  region?: string;
}

function projectKey(ownerSub: string, id: string) {
  return { PK: `USER#${ownerSub}`, SK: `PROJECT#${id}` };
}

export class ProjectsService {
  private client: DynamoDBClient;
  private tableName: string;

  constructor(config: ProjectsServiceConfig) {
    this.tableName = config.tableName;
    this.client = new DynamoDBClient({
      region: config.region || process.env.AWS_REGION || 'us-east-1',
    });
  }

  async list(ownerSub: string): Promise<Project[]> {
    const result = await this.client.send(
      new QueryCommand({
        TableName: this.tableName,
        KeyConditionExpression: 'PK = :pk AND begins_with(SK, :sk)',
        ExpressionAttributeValues: marshall({
          ':pk': `USER#${ownerSub}`,
          ':sk': 'PROJECT#',
        }),
      })
    );
    return (result.Items ?? []).map(item => unmarshall(item) as Project);
  }

  async get(ownerSub: string, id: string): Promise<Project | null> {
    const result = await this.client.send(
      new GetItemCommand({
        TableName: this.tableName,
        Key: marshall(projectKey(ownerSub, id)),
      })
    );
    if (!result.Item) return null;
    return unmarshall(result.Item) as Project;
  }

  async create(ownerSub: string, project: Project): Promise<void> {
    const item = {
      ...projectKey(ownerSub, project.id),
      ...project,
    };
    await this.client.send(
      new PutItemCommand({
        TableName: this.tableName,
        Item: marshall(item, { removeUndefinedValues: true }),
        // Belt for randomUUID's already-tiny collision odds.
        ConditionExpression: 'attribute_not_exists(SK)',
      })
    );
  }

  async rename(ownerSub: string, id: string, name: string): Promise<Project | null> {
    try {
      const result = await this.client.send(
        new UpdateItemCommand({
          TableName: this.tableName,
          Key: marshall(projectKey(ownerSub, id)),
          UpdateExpression: 'SET #n = :name, updated_at = :ts',
          ConditionExpression: 'attribute_exists(SK)',
          ExpressionAttributeNames: { '#n': 'name' },
          ExpressionAttributeValues: marshall({
            ':name': name,
            ':ts': new Date().toISOString(),
          }),
          ReturnValues: 'ALL_NEW',
        })
      );
      return result.Attributes ? (unmarshall(result.Attributes) as Project) : null;
    } catch (err) {
      if (err instanceof ConditionalCheckFailedException) return null;
      throw err;
    }
  }

  async delete(ownerSub: string, id: string): Promise<boolean> {
    try {
      await this.client.send(
        new DeleteItemCommand({
          TableName: this.tableName,
          Key: marshall(projectKey(ownerSub, id)),
          ConditionExpression: 'attribute_exists(SK)',
        })
      );
      return true;
    } catch (err) {
      if (err instanceof ConditionalCheckFailedException) return false;
      throw err;
    }
  }

  /**
   * Add a product ref. Idempotent: a duplicate `(product_type, product_id)`
   * tuple is silently ignored rather than raising — matches the UX of a
   * dropdown checkbox where re-checking an already-checked project should
   * be a no-op, not an error.
   */
  async addProduct(
    ownerSub: string,
    id: string,
    ref: ProductRef
  ): Promise<Project | null> {
    const project = await this.get(ownerSub, id);
    if (!project) return null;
    const exists = (project.product_refs ?? []).some(
      r => r.product_type === ref.product_type && r.product_id === ref.product_id
    );
    if (exists) return project;
    const refs = [...(project.product_refs ?? []), ref];
    return this.replaceRefs(ownerSub, id, refs);
  }

  async removeProduct(
    ownerSub: string,
    id: string,
    ref: ProductRef
  ): Promise<Project | null> {
    const project = await this.get(ownerSub, id);
    if (!project) return null;
    const refs = (project.product_refs ?? []).filter(
      r => !(r.product_type === ref.product_type && r.product_id === ref.product_id)
    );
    return this.replaceRefs(ownerSub, id, refs);
  }

  private async replaceRefs(
    ownerSub: string,
    id: string,
    refs: ProductRef[]
  ): Promise<Project | null> {
    try {
      const result = await this.client.send(
        new UpdateItemCommand({
          TableName: this.tableName,
          Key: marshall(projectKey(ownerSub, id)),
          UpdateExpression: 'SET product_refs = :refs, updated_at = :ts',
          ConditionExpression: 'attribute_exists(SK)',
          ExpressionAttributeValues: marshall({
            ':refs': refs,
            ':ts': new Date().toISOString(),
          }),
          ReturnValues: 'ALL_NEW',
        })
      );
      return result.Attributes ? (unmarshall(result.Attributes) as Project) : null;
    } catch (err) {
      if (err instanceof ConditionalCheckFailedException) return null;
      throw err;
    }
  }
}
