/**
 * Tests for upload route.
 * Mocks DynamoDB and S3 presigned URL generation.
 */

import request from 'supertest';
import app from '../src/index';
import { DynamoDBService } from '../src/db/dynamodb';

jest.mock('../src/db/dynamodb');
jest.mock('@aws-sdk/s3-request-presigner', () => ({
  getSignedUrl: jest.fn().mockResolvedValue('https://s3.example.com/presigned-url'),
}));

describe('POST /api/upload', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('returns 201 with presigned URL on valid upload', async () => {
    (DynamoDBService.prototype.create as jest.Mock).mockResolvedValue(true);

    const response = await request(app).post('/api/upload').send({
      product_name: 'Test Motor',
      manufacturer: 'TestCorp',
      product_type: 'motor',
      filename: 'datasheet.pdf',
    });

    expect(response.status).toBe(201);
    expect(response.body.success).toBe(true);
    expect(response.body.data).toHaveProperty('datasheet_id');
    expect(response.body.data).toHaveProperty('s3_key');
    expect(response.body.data).toHaveProperty('upload_url');
    expect(response.body.data.upload_url).toContain('presigned-url');
  });

  it('returns 400 when product_name is missing', async () => {
    const response = await request(app).post('/api/upload').send({
      manufacturer: 'TestCorp',
      product_type: 'motor',
      filename: 'datasheet.pdf',
    });

    expect(response.status).toBe(400);
    expect(response.body.success).toBe(false);
    expect(response.body.error).toContain('Missing required fields');
  });

  it('returns 400 when manufacturer is missing', async () => {
    const response = await request(app).post('/api/upload').send({
      product_name: 'Test Motor',
      product_type: 'motor',
      filename: 'datasheet.pdf',
    });

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('Missing required fields');
  });

  it('returns 400 when product_type is missing', async () => {
    const response = await request(app).post('/api/upload').send({
      product_name: 'Test Motor',
      manufacturer: 'TestCorp',
      filename: 'datasheet.pdf',
    });

    expect(response.status).toBe(400);
  });

  it('returns 400 when filename is missing', async () => {
    const response = await request(app).post('/api/upload').send({
      product_name: 'Test Motor',
      manufacturer: 'TestCorp',
      product_type: 'motor',
    });

    expect(response.status).toBe(400);
  });

  it('returns 400 for non-PDF filename', async () => {
    const response = await request(app).post('/api/upload').send({
      product_name: 'Test Motor',
      manufacturer: 'TestCorp',
      product_type: 'motor',
      filename: 'datasheet.docx',
    });

    expect(response.status).toBe(400);
    expect(response.body.error).toContain('PDF');
  });

  it('accepts .PDF uppercase extension', async () => {
    (DynamoDBService.prototype.create as jest.Mock).mockResolvedValue(true);

    const response = await request(app).post('/api/upload').send({
      product_name: 'Test Motor',
      manufacturer: 'TestCorp',
      product_type: 'motor',
      filename: 'DATASHEET.PDF',
    });

    expect(response.status).toBe(201);
  });

  it('returns 500 when DynamoDB create fails', async () => {
    (DynamoDBService.prototype.create as jest.Mock).mockResolvedValue(false);

    const response = await request(app).post('/api/upload').send({
      product_name: 'Test Motor',
      manufacturer: 'TestCorp',
      product_type: 'motor',
      filename: 'datasheet.pdf',
    });

    expect(response.status).toBe(500);
    expect(response.body.success).toBe(false);
  });

  it('passes pages through when provided', async () => {
    (DynamoDBService.prototype.create as jest.Mock).mockResolvedValue(true);

    const response = await request(app).post('/api/upload').send({
      product_name: 'Test Motor',
      manufacturer: 'TestCorp',
      product_type: 'motor',
      filename: 'datasheet.pdf',
      pages: [1, 2, 3],
    });

    expect(response.status).toBe(201);
    expect(DynamoDBService.prototype.create).toHaveBeenCalledWith(
      expect.objectContaining({ pages: [1, 2, 3] })
    );
  });

  it('handles unexpected errors gracefully', async () => {
    (DynamoDBService.prototype.create as jest.Mock).mockRejectedValue(new Error('Unexpected'));

    const response = await request(app).post('/api/upload').send({
      product_name: 'Test Motor',
      manufacturer: 'TestCorp',
      product_type: 'motor',
      filename: 'datasheet.pdf',
    });

    expect(response.status).toBe(500);
    expect(response.body.error).toContain('Failed to create upload');
  });
});
