/**
 * DynamoDB client for CRUD operations on products.
 * This module mirrors the functionality of datasheetminer/db/dynamo.py
 */

import {
  DynamoDBClient,
  GetItemCommand,
  PutItemCommand,
  QueryCommand,
  DeleteItemCommand,
  BatchWriteItemCommand,
} from '@aws-sdk/client-dynamodb';
import { marshall, unmarshall } from '@aws-sdk/util-dynamodb';
import { Product, ProductType } from '../types/models';

export interface DynamoDBConfig {
  tableName: string;
  region?: string;
}

export class DynamoDBService {
  private client: DynamoDBClient;
  private tableName: string;

  constructor(config: DynamoDBConfig) {
    this.tableName = config.tableName;
    this.client = new DynamoDBClient({
      region: config.region || process.env.AWS_REGION || 'us-east-1',
    });
  }

  /**
   * Create a new product in DynamoDB
   */
  async create(product: Product): Promise<boolean> {
    try {
      const item = this.serializeProduct(product);
      await this.client.send(
        new PutItemCommand({
          TableName: this.tableName,
          Item: marshall(item, { removeUndefinedValues: true }),
        })
      );
      return true;
    } catch (error) {
      console.error('Error creating product:', error);
      return false;
    }
  }

  /**
   * Read a product by ID and type
   */
  async read(productId: string, productType: ProductType): Promise<Product | null> {
    try {
      const typeUpper = productType.toUpperCase();
      const pk = `PRODUCT#${typeUpper}`;
      const sk = `PRODUCT#${productId}`;

      const result = await this.client.send(
        new GetItemCommand({
          TableName: this.tableName,
          Key: marshall({ PK: pk, SK: sk }),
        })
      );

      if (!result.Item) {
        return null;
      }

      return this.deserializeProduct(unmarshall(result.Item));
    } catch (error) {
      console.error('Error reading product:', error);
      return null;
    }
  }

  /**
   * Delete a product by ID and type
   */
  async delete(productId: string, productType: ProductType): Promise<boolean> {
    try {
      const typeUpper = productType.toUpperCase();
      const pk = `PRODUCT#${typeUpper}`;
      const sk = `PRODUCT#${productId}`;

      await this.client.send(
        new DeleteItemCommand({
          TableName: this.tableName,
          Key: marshall({ PK: pk, SK: sk }),
        })
      );

      return true;
    } catch (error) {
      console.error('Error deleting product:', error);
      return false;
    }
  }

  /**
   * List products by type with optional filtering
   */
  async list(
    productType: ProductType = 'all',
    limit?: number
  ): Promise<Product[]> {
    try {
      // If 'all', we need to query both types
      if (productType === 'all') {
        const [motors, drives] = await Promise.all([
          this.list('motor', limit),
          this.list('drive', limit),
        ]);
        return [...motors, ...drives];
      }

      const typeUpper = productType.toUpperCase();
      const pk = `PRODUCT#${typeUpper}`;

      const result = await this.client.send(
        new QueryCommand({
          TableName: this.tableName,
          KeyConditionExpression: 'PK = :pk',
          ExpressionAttributeValues: marshall({ ':pk': pk }),
          Limit: limit,
        })
      );

      if (!result.Items) {
        return [];
      }

      return result.Items.map((item) => this.deserializeProduct(unmarshall(item)));
    } catch (error) {
      console.error('Error listing products:', error);
      return [];
    }
  }

  /**
   * List all products (convenience method)
   */
  async listAll(limit?: number): Promise<Product[]> {
    return this.list('all', limit);
  }

  /**
   * Batch create multiple products
   * DynamoDB has a limit of 25 items per batch
   */
  async batchCreate(products: Product[]): Promise<number> {
    if (products.length === 0) {
      return 0;
    }

    let successCount = 0;
    const batchSize = 25;

    for (let i = 0; i < products.length; i += batchSize) {
      const batch = products.slice(i, i + batchSize);

      try {
        const requests = batch.map((product) => ({
          PutRequest: {
            Item: marshall(this.serializeProduct(product), {
              removeUndefinedValues: true
            }),
          },
        }));

        await this.client.send(
          new BatchWriteItemCommand({
            RequestItems: {
              [this.tableName]: requests,
            },
          })
        );

        successCount += batch.length;
      } catch (error) {
        console.error('Error in batch create:', error);
        // Continue with next batch even if this one fails
      }
    }

    return successCount;
  }

  /**
   * Count products by type
   */
  async count(): Promise<{ total: number; motors: number; drives: number }> {
    const [motors, drives] = await Promise.all([
      this.list('motor'),
      this.list('drive'),
    ]);

    return {
      total: motors.length + drives.length,
      motors: motors.length,
      drives: drives.length,
    };
  }

  /**
   * Serialize product for DynamoDB storage
   */
  private serializeProduct(product: Product): any {
    const typeUpper = product.product_type.toUpperCase();

    return {
      ...product,
      PK: `PRODUCT#${typeUpper}`,
      SK: `PRODUCT#${product.product_id}`,
    };
  }

  /**
   * Deserialize product from DynamoDB
   */
  private deserializeProduct(item: any): Product {
    // Type assertion based on product_type
    return item as Product;
  }
}
