/**
 * API routes for datasheets
 */

import { Router, Request, Response } from 'express';
import { DynamoDBService } from '../db/dynamodb';
import { Datasheet } from '../types/models';
import { v4 as uuidv4 } from 'uuid';
import config from '../config';

const router = Router();
const db = new DynamoDBService({ tableName: config.dynamodb.tableName });

/**
 * GET /api/datasheets
 * List all datasheets
 */
router.get('/', async (_req: Request, res: Response) => {
  try {
    const datasheets = await db.listDatasheets();
    
    // Map to frontend expected format
    // Frontend expects product_type='datasheet' to identify them
    // We preserve the actual product type (e.g. 'motor') in the category field
    // Frontend expects product_type='datasheet' to identify them in the list
    const mappedDatasheets = datasheets.map(ds => ({
      ...ds,
      product_type: 'datasheet',
      component_type: ds.product_type, // Preserve the actual component type (motor, drive)
      product_name: ds.product_name,
      product_id: ds.datasheet_id, // Ensure product_id exists for frontend keys
    }));

    res.json({
      success: true,
      data: mappedDatasheets,
      count: mappedDatasheets.length,
    });
  } catch (error) {
    console.error('Error listing datasheets:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to list datasheets',
    });
  }
});

/**
 * POST /api/datasheets
 * Create a new datasheet
 */
router.post('/', async (req: Request, res: Response): Promise<void> => {
  try {
    const body = req.body;
    
    // Basic validation
    if (!body.url || !body.product_type || !body.product_name) {
      res.status(400).json({
        success: false,
        error: 'Missing required fields: url, product_type, product_name',
      });
      return;
    }

    // Check for duplicates
    const exists = await db.datasheetExists(body.url);
    if (exists) {
      res.status(409).json({
        success: false,
        error: 'Datasheet with this URL already exists',
      });
      return;
    }

    const datasheet: Datasheet = {
      ...body,
      datasheet_id: body.datasheet_id || uuidv4(),
    };

    const success = await db.create(datasheet);

    if (success) {
      res.status(201).json({
        success: true,
        data: datasheet,
      });
    } else {
      res.status(500).json({
        success: false,
        error: 'Failed to create datasheet',
      });
    }
  } catch (error) {
    console.error('Error creating datasheet:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to create datasheet',
    });
  }
});

/**
 * DELETE /api/datasheets/:id
 * Delete a datasheet by ID
 * Query params: type (product_type) - required
 */
router.delete('/:id', async (req: Request, res: Response): Promise<void> => {
  try {
    const { id } = req.params;
    const type = req.query.type as string;

    if (!type) {
      res.status(400).json({
        success: false,
        error: 'type query parameter is required',
      });
      return;
    }

    const success = await db.deleteDatasheet(id, type);

    if (success) {
      res.json({
        success: true,
        message: 'Datasheet deleted successfully',
      });
    } else {
      res.status(404).json({
        success: false,
        error: 'Datasheet not found or failed to delete',
      });
    }
  } catch (error) {
    console.error('Error deleting datasheet:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to delete datasheet',
    });
  }
});

/**
 * PUT /api/datasheets/:id
 * Update a datasheet
 */
router.put('/:id', async (req: Request, res: Response): Promise<void> => {
  try {
    const { id } = req.params;
    const body = req.body;
    
    if (!body.product_type) {
      res.status(400).json({
        success: false,
        error: 'product_type is required for updates',
      });
      return;
    }

    const success = await db.updateDatasheet(id, body.product_type, body);

    if (success) {
      res.json({
        success: true,
        message: 'Datasheet updated successfully',
      });
    } else {
      res.status(404).json({
        success: false,
        error: 'Datasheet not found or failed to update',
      });
    }
  } catch (error) {
    console.error('Error updating datasheet:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to update datasheet',
    });
  }
});

export default router;
