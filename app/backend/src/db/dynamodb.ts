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
  ScanCommand,
  AttributeValue,
} from '@aws-sdk/client-dynamodb';
import { marshall, unmarshall } from '@aws-sdk/util-dynamodb';
import { Product, ProductType, Datasheet, Motor, Drive } from '../types/models';
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
   * Create a new product or datasheet in DynamoDB
   */
  async create(item: Product | Datasheet): Promise<boolean> {
    try {
      const dbItem = this.serializeItem(item);
      await this.client.send(
        new PutItemCommand({
          TableName: this.tableName,
          Item: marshall(dbItem, { removeUndefinedValues: true }),
        })
      );
      return true;
    } catch (error) {
      console.error('Error creating item:', error);
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
   * Delete products by manufacturer
   */
  async deleteByManufacturer(manufacturer: string): Promise<{ deleted: number; failed: number }> {
    return this.deleteByScan('manufacturer', manufacturer);
  }

  /**
   * Delete products by product name
   */
  async deleteByProductName(name: string): Promise<{ deleted: number; failed: number }> {
    return this.deleteByScan('product_name', name);
  }

  /**
   * Helper to delete items found by scanning a specific attribute
   */
  private async deleteByScan(attributeName: string, attributeValue: string): Promise<{ deleted: number; failed: number }> {
    try {
      console.log(`[DynamoDB] Scanning for items where ${attributeName} = ${attributeValue}`);
      
      const scanResult = await this.client.send(
        new ScanCommand({
          TableName: this.tableName,
          FilterExpression: `#attr = :val`,
          ExpressionAttributeNames: { '#attr': attributeName },
          ExpressionAttributeValues: marshall({ ':val': attributeValue }),
          ProjectionExpression: 'PK, SK',
        })
      );

      const items = scanResult.Items || [];

      if (items.length === 0) {
        return { deleted: 0, failed: 0 };
      }

      console.log(`[DynamoDB] Found ${items.length} items to delete`);

      // Delete found items
      const deletePromises = items.map(async (item) => {
        try {
          await this.client.send(
            new DeleteItemCommand({
              TableName: this.tableName,
              Key: {
                PK: item.PK,
                SK: item.SK,
              },
            })
          );
          return true;
        } catch (err) {
          console.error(`[DynamoDB] Failed to delete item ${item.SK?.S}:`, err);
          return false;
        }
      });

      const results = await Promise.all(deletePromises);
      const deleted = results.filter((r) => r).length;
      const failed = results.filter((r) => !r).length;

      return { deleted, failed };
    } catch (error) {
      console.error(`Error deleting products by ${attributeName}:`, error);
      throw error;
    }
  }

  /**
   * Delete products by part number
   * Scans for items with matching part_number and deletes them
   */
  async deleteByPartNumber(partNumber: string): Promise<{ deleted: number; failed: number }> {
    return this.deleteByScan('part_number', partNumber);
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
      // Handle datasheets specially as they have a different PK prefix
      const pk = productType === 'datasheet' ? `DATASHEET#${typeUpper}` : `PRODUCT#${typeUpper}`;
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
   * Batch delete multiple products
   */
  async batchDelete(items: { PK: string; SK: string }[]): Promise<number> {
    if (items.length === 0) {
      return 0;
    }

    let deletedCount = 0;
    const batchSize = 25;

    for (let i = 0; i < items.length; i += batchSize) {
      const batch = items.slice(i, i + batchSize);

      try {
        const requests = batch.map((item) => ({
          DeleteRequest: {
            // Strictly marshal only PK and SK
            Key: marshall({ PK: item.PK, SK: item.SK }),
          },
        }));

        await this.client.send(
          new BatchWriteItemCommand({
            RequestItems: {
              [this.tableName]: requests,
            },
          })
        );

        deletedCount += batch.length;
      } catch (error) {
        console.error('Error in batch delete:', error);
        // Continue with next batch even if this one fails
      }
    }

    return deletedCount;
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
   * Get all unique manufacturers
   */
  async getUniqueManufacturers(): Promise<string[]> {
    try {
      const allProducts = await this.listAll();
      const manufacturers = new Set(
        allProducts
          .map(p => p.manufacturer)
          .filter((f): f is string => !!f)
      );
      return Array.from(manufacturers).sort();
    } catch (error) {
      console.error('Error getting unique manufacturers:', error);
      return [];
    }
  }

  /**
   * Get all unique product names
   */
  async getUniqueNames(): Promise<string[]> {
    try {
      const allProducts = await this.listAll();
      const names = new Set(
        allProducts
          .map(p => p.product_name)
          .filter((n): n is string => !!n)
      );
      return Array.from(names).sort();
    } catch (error) {
      console.error('Error getting unique names:', error);
      return [];
    }
  }

  /**
   * Check if a datasheet exists by URL
   */
  async datasheetExists(url: string): Promise<boolean> {
    try {
      const scanResult = await this.client.send(
        new ScanCommand({
          TableName: this.tableName,
          FilterExpression: '#url = :url',
          ExpressionAttributeNames: { '#url': 'url' },
          ExpressionAttributeValues: marshall({ ':url': url }),
          Limit: 1,
          ProjectionExpression: 'PK',
        })
      );
      return (scanResult.Items?.length || 0) > 0;
    } catch (error) {
      console.error('Error checking datasheet existence:', error);
      return false;
    }
  }

  /**
   * List all datasheets
   */
  async listDatasheets(): Promise<Datasheet[]> {
    try {
      // Scan for items where PK starts with DATASHEET#
      // Note: Scan is inefficient but acceptable for now given the volume
      const scanResult = await this.client.send(
        new ScanCommand({
          TableName: this.tableName,
          FilterExpression: 'begins_with(PK, :pk)',
          ExpressionAttributeValues: marshall({ ':pk': 'DATASHEET#' }),
        })
      );

      return (scanResult.Items || []).map(item => 
        unmarshall(item) as Datasheet
      );
    } catch (error) {
      console.error('Error listing datasheets:', error);
      return [];
    }
  }

  /**
   * Delete a datasheet
   */
  async deleteDatasheet(id: string, productType: string): Promise<boolean> {
    try {
      const pk = `DATASHEET#${productType.toUpperCase()}`;
      const sk = `DATASHEET#${id}`;

      await this.client.send(
        new DeleteItemCommand({
          TableName: this.tableName,
          Key: marshall({ PK: pk, SK: sk }),
        })
      );
      return true;
    } catch (error) {
      console.error('Error deleting datasheet:', error);
      return false;
    }
  }

  /**
   * Update a datasheet
   */
  async updateDatasheet(id: string, productType: string, updates: Partial<Datasheet>): Promise<boolean> {
    try {
      const pk = `DATASHEET#${productType.toUpperCase()}`;
      const sk = `DATASHEET#${id}`;

      // Fetch existing item first to ensure it exists and preserve other fields
      const result = await this.client.send(
        new GetItemCommand({
          TableName: this.tableName,
          Key: marshall({ PK: pk, SK: sk }),
        })
      );

      if (!result.Item) {
        return false;
      }

      const existingItem = unmarshall(result.Item) as Datasheet;
      
      // Merge updates
      const updatedItem: Datasheet = {
        ...existingItem,
        ...updates,
        // Ensure keys don't change
        datasheet_id: id,
        product_type: existingItem.product_type,
        PK: pk,
        SK: sk
      };

      await this.client.send(
        new PutItemCommand({
          TableName: this.tableName,
          Item: marshall(updatedItem, { removeUndefinedValues: true }),
        })
      );

      return true;
    } catch (error) {
      console.error('Error updating datasheet:', error);
      return false;
    }
  }

  /**
   * Serialize item (Product or Datasheet) for DynamoDB storage
   */
  private serializeItem(item: Product | Datasheet): any {
    // Check if it's a Datasheet (has url property)
    if ('url' in item && !('product_id' in item)) {
      const ds = item as Datasheet;
      const typeUpper = ds.product_type.toUpperCase();
      return {
        ...ds,
        PK: `DATASHEET#${typeUpper}`,
        SK: `DATASHEET#${ds.datasheet_id}`,
      };
    }

    // It's a Product (Motor or Drive)
    const product = item as Motor | Drive;
    const typeUpper = product.product_type.toUpperCase();
    return {
      ...product,
      PK: `PRODUCT#${typeUpper}`,
      SK: `PRODUCT#${product.product_id}`,
    };
  }

  /**
   * Serialize product for DynamoDB storage
   * @deprecated Use serializeItem instead
   */
  private serializeProduct(product: Product): any {
    return this.serializeItem(product);
  }

  /**
   * Deserialize product from DynamoDB
   */
  private deserializeProduct(item: any): Product {
    // Handle datasheet mapping for frontend compatibility
    if (item.product_type === 'datasheet' && item.datasheet_id && !item.product_id) {
      return {
        ...item,
        product_id: item.datasheet_id,
      } as Product;
    }
    // Type assertion based on product_type
    return item as Product;
  }
}
