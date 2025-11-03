/**
 * DynamoDB client for CRUD operations on products.
 * This module mirrors the functionality of datasheetminer/db/dynamo.py
 */

import {
  DynamoDBClient,
  GetItemCommand,
  PutItemCommand,
  QueryCommand,
  QueryCommandOutput,
  DeleteItemCommand,
  BatchWriteItemCommand,
  AttributeValue,
} from '@aws-sdk/client-dynamodb';
import { marshall, unmarshall } from '@aws-sdk/util-dynamodb';
import { Product, ProductType } from '../types/models';
import { VALID_PRODUCT_TYPES, formatDisplayName } from '../config/productTypes';

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
   * Automatically handles DynamoDB pagination to fetch all results
   */
  async list(
    productType: ProductType = 'all',
    limit?: number
  ): Promise<Product[]> {
    try {
      // If 'all', query all valid product types dynamically
      if (productType === 'all') {
        const allTypePromises = VALID_PRODUCT_TYPES.map(type =>
          this.list(type as ProductType, limit)
        );
        const results = await Promise.all(allTypePromises);
        return results.flat();
      }

      const typeUpper = productType.toUpperCase();
      const pk = `PRODUCT#${typeUpper}`;
      const allItems: Product[] = [];
      let lastEvaluatedKey: Record<string, AttributeValue> | undefined = undefined;

      // Paginate through all results
      let pageCount = 0;
      do {
        pageCount++;
        console.log(`[DynamoDB] Query page ${pageCount} for ${productType} (current total: ${allItems.length})`);

        const result: QueryCommandOutput = await this.client.send(
          new QueryCommand({
            TableName: this.tableName,
            KeyConditionExpression: 'PK = :pk',
            ExpressionAttributeValues: marshall({ ':pk': pk }),
            Limit: limit,
            ExclusiveStartKey: lastEvaluatedKey,
          })
        );

        console.log(`[DynamoDB] Page ${pageCount} returned ${result.Items?.length || 0} items, hasMore: ${!!result.LastEvaluatedKey}`);

        if (result.Items && result.Items.length > 0) {
          const items = result.Items.map((item: Record<string, AttributeValue>) =>
            this.deserializeProduct(unmarshall(item))
          );
          allItems.push(...items);
        }

        // Check if there are more results to fetch
        lastEvaluatedKey = result.LastEvaluatedKey;

        // If a limit was specified and we've reached it, stop paginating
        if (limit && allItems.length >= limit) {
          console.log(`[DynamoDB] Reached limit of ${limit}, stopping pagination`);
          break;
        }

      } while (lastEvaluatedKey);

      console.log(`[DynamoDB] Query complete for ${productType}: ${allItems.length} total items from ${pageCount} pages`);

      return allItems;
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
   * Uses the fixed list method which now paginates through all results
   * Returns counts for all valid product types dynamically
   */
  async count(): Promise<Record<string, number> & { total: number }> {
    // Query all product types in parallel
    const countPromises = VALID_PRODUCT_TYPES.map(async type => ({
      type,
      products: await this.list(type as ProductType)
    }));

    const results = await Promise.all(countPromises);

    // Build dynamic count object
    const counts: Record<string, number> & { total: number } = { total: 0 };

    for (const { type, products } of results) {
      const count = products.length;
      counts[type + 's'] = count; // e.g., "motors", "drives", "robot_arms"
      counts.total += count;
    }

    return counts;
  }

  /**
   * Get all unique product categories and their counts
   * Returns ALL valid product types (from config) with counts from database
   * Shows types with 0 count if they have no products yet
   * Handles case-insensitive matching since database may have inconsistent casing
   */
  async getCategories(): Promise<Array<{ type: string; count: number; display_name: string }>> {
    try {
      // Get all products from database
      const allProducts = await this.listAll();

      // Count products by type (case-insensitive)
      const categoryCountMap = new Map<string, number>();
      for (const product of allProducts) {
        const type = product.product_type.toLowerCase(); // Normalize to lowercase
        categoryCountMap.set(type, (categoryCountMap.get(type) || 0) + 1);
      }

      // Create array with ALL valid types (including those with 0 count)
      const categories = VALID_PRODUCT_TYPES.map(type => ({
        type,
        count: categoryCountMap.get(type.toLowerCase()) || 0, // Case-insensitive lookup
        display_name: formatDisplayName(type)
      }));

      // Sort by type name
      categories.sort((a, b) => a.type.localeCompare(b.type));

      console.log('[DynamoDB] Categories:', categories);

      return categories;
    } catch (error) {
      console.error('Error getting categories:', error);
      return [];
    }
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
