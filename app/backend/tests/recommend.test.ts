/**
 * Tests for recommendation route.
 * Mocks DynamoDB and RecommendationService.
 */

import request from 'supertest';
import { DynamoDBService } from '../src/db/dynamodb';

jest.mock('../src/db/dynamodb');

const mockRecommend = jest.fn();
const mockGetCachedProducts = jest.fn();
const mockSetCachedProducts = jest.fn();

jest.mock('../src/services/recommendation', () => ({
  RecommendationService: jest.fn().mockImplementation(() => ({
    recommend: mockRecommend,
    getCachedProducts: mockGetCachedProducts,
    setCachedProducts: mockSetCachedProducts,
  })),
}));

// Import app AFTER mocks are set up
import app from '../src/index';

describe('POST /api/recommend', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetCachedProducts.mockReturnValue(null);
  });

  it('returns 400 when message is missing', async () => {
    const response = await request(app).post('/api/recommend').send({});
    expect(response.status).toBe(400);
    expect(response.body.error).toContain('Message is required');
  });

  it('returns 400 when message is empty string', async () => {
    const response = await request(app).post('/api/recommend').send({ message: '' });
    expect(response.status).toBe(400);
  });

  it('returns 400 when message is whitespace only', async () => {
    const response = await request(app).post('/api/recommend').send({ message: '   ' });
    expect(response.status).toBe(400);
  });

  it('returns 400 when message is not a string', async () => {
    const response = await request(app).post('/api/recommend').send({ message: 123 });
    expect(response.status).toBe(400);
  });

  it('fetches products from DB on cache miss', async () => {
    const mockProducts = [
      { product_id: 'p1', product_type: 'motor', manufacturer: 'A', PK: 'PRODUCT#MOTOR', SK: 'PRODUCT#p1' },
    ];
    mockGetCachedProducts.mockReturnValue(null);
    (DynamoDBService.prototype.listAll as jest.Mock).mockResolvedValue(mockProducts);
    mockRecommend.mockResolvedValue({
      response: 'I recommend product p1',
      recommended_product_ids: ['p1'],
    });

    const response = await request(app).post('/api/recommend').send({ message: 'I need a motor' });
    expect(response.status).toBe(200);
    expect(response.body.success).toBe(true);
    expect(response.body.data.response).toContain('recommend');
    expect(response.body.data.products).toHaveLength(1);
  });

  it('uses cached products on cache hit', async () => {
    const mockProducts = [
      { product_id: 'p1', product_type: 'motor', manufacturer: 'A', PK: 'PRODUCT#MOTOR', SK: 'PRODUCT#p1' },
    ];
    mockGetCachedProducts.mockReturnValue(mockProducts);
    mockRecommend.mockResolvedValue({
      response: 'Use p1',
      recommended_product_ids: ['p1'],
    });

    const response = await request(app).post('/api/recommend').send({ message: 'motor please' });
    expect(response.status).toBe(200);
    expect(DynamoDBService.prototype.listAll).not.toHaveBeenCalled();
  });

  it('handles recommendation with no matching product IDs', async () => {
    mockGetCachedProducts.mockReturnValue([
      { product_id: 'p1', product_type: 'motor', manufacturer: 'A', PK: 'P', SK: 'S' },
    ]);
    mockRecommend.mockResolvedValue({
      response: 'No matches found',
      recommended_product_ids: ['nonexistent-id'],
    });

    const response = await request(app).post('/api/recommend').send({ message: 'find me something' });
    expect(response.status).toBe(200);
    expect(response.body.data.products).toHaveLength(0);
  });

  it('passes history to recommendation service', async () => {
    mockGetCachedProducts.mockReturnValue([]);
    mockRecommend.mockResolvedValue({
      response: 'Based on our conversation...',
      recommended_product_ids: [],
    });

    const history = [
      { role: 'user', content: 'I need a motor' },
      { role: 'model', content: 'What specs?' },
    ];

    const response = await request(app)
      .post('/api/recommend')
      .send({ message: '100W', history });

    expect(response.status).toBe(200);
    expect(mockRecommend).toHaveBeenCalledWith(
      '100W',
      expect.any(Array),
      history,
    );
  });

  it('returns 500 on recommendation service error', async () => {
    mockGetCachedProducts.mockReturnValue([]);
    mockRecommend.mockRejectedValue(new Error('Gemini API error'));

    const response = await request(app).post('/api/recommend').send({ message: 'help' });
    expect(response.status).toBe(500);
    expect(response.body.success).toBe(false);
    expect(response.body.error).toContain('Failed to generate recommendation');
  });
});
