/**
 * Recommendation service — uses Gemini to recommend products based on user requirements.
 * Queries the same DynamoDB product catalog and provides AI-powered suggestions.
 */

import { GoogleGenAI } from '@google/genai';
import config from '../config';
import { Product } from '../types/models';

const MODEL_NAME = 'gemini-2.0-flash-exp';
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes
const MAX_PRODUCTS_IN_CONTEXT = 500;

// Key specs to include per product type for compact serialization
const KEY_SPECS: Record<string, string[]> = {
  motor: ['rated_voltage', 'rated_speed', 'rated_torque', 'rated_power', 'rated_current', 'type', 'series'],
  drive: ['input_voltage', 'rated_current', 'peak_current', 'output_power', 'type', 'series'],
  gearhead: ['gear_ratio', 'gear_type', 'max_continuous_torque', 'max_input_speed', 'stages'],
  robot_arm: ['payload', 'reach', 'degrees_of_freedom', 'max_tcp_speed'],
};

interface ChatMessage {
  role: 'user' | 'model';
  content: string;
}

interface RecommendationResult {
  response: string;
  recommended_product_ids: string[];
}

export class RecommendationService {
  private client: GoogleGenAI;
  private productCache: { products: Product[]; timestamp: number } | null = null;

  constructor() {
    this.client = new GoogleGenAI({ apiKey: config.gemini.apiKey || '' });
  }

  /**
   * Serialize products into a compact text catalog for the LLM context.
   * Only includes key specs to stay within token limits.
   */
  private serializeCatalog(products: Product[]): string {
    // Skip datasheets — only include real products
    const real = products.filter((p) => 'product_id' in p);
    const capped = real.slice(0, MAX_PRODUCTS_IN_CONTEXT);
    const lines = capped.map((p: any) => {
      const type = p.product_type;
      const specs = KEY_SPECS[type] || [];
      const specParts = specs
        .map((key: string) => {
          const val = p[key];
          if (val == null) return null;
          if (typeof val === 'object' && 'value' in val && 'unit' in val) {
            return `${key}=${val.value}${val.unit}`;
          }
          if (typeof val === 'object' && 'min' in val && 'max' in val && 'unit' in val) {
            return `${key}=${val.min}-${val.max}${val.unit}`;
          }
          return `${key}=${val}`;
        })
        .filter(Boolean);

      return `[${p.product_id}] ${type} | ${p.manufacturer} | ${p.part_number || 'N/A'} | ${specParts.join(', ')}`;
    });

    return lines.join('\n');
  }

  private buildSystemPrompt(catalog: string): string {
    return `You are a product recommendation assistant for industrial automation components.
You have access to a catalog of motors, drives, gearheads, and robot arms.
Your job is to help engineers find the right products for their requirements.

When the user describes their needs, recommend the most suitable products from the catalog.
Explain WHY each product is a good fit based on the specs provided.
If no products match well, say so honestly and suggest what specs to look for.
If the user's requirements are vague, ask clarifying questions.

PRODUCT CATALOG:
${catalog}

Respond in JSON with this exact schema:
{
  "response": "Your natural language explanation and recommendation",
  "recommended_product_ids": ["product_id_1", "product_id_2"]
}

Keep recommended_product_ids to 5 or fewer. Only include products from the catalog above.
If you have no recommendations or are asking a clarifying question, use an empty array for recommended_product_ids.`;
  }

  /**
   * Get cached products or signal that fresh data is needed.
   */
  getCachedProducts(): Product[] | null {
    if (this.productCache && Date.now() - this.productCache.timestamp < CACHE_TTL_MS) {
      return this.productCache.products;
    }
    return null;
  }

  /**
   * Update the product cache.
   */
  setCachedProducts(products: Product[]): void {
    this.productCache = { products, timestamp: Date.now() };
  }

  /**
   * Generate a recommendation based on user message and product catalog.
   */
  async recommend(
    message: string,
    products: Product[],
    history: ChatMessage[] = [],
  ): Promise<RecommendationResult> {
    const catalog = this.serializeCatalog(products);
    const systemPrompt = this.buildSystemPrompt(catalog);

    // Build contents: system prompt first, then history, then current message
    // The Gemini SDK expects contents as an array of {text} or {role, parts}
    const historyText = history
      .map((msg) => `${msg.role === 'user' ? 'User' : 'Assistant'}: ${msg.content}`)
      .join('\n\n');

    const fullPrompt = historyText
      ? `${systemPrompt}\n\nConversation so far:\n${historyText}\n\nUser: ${message}`
      : `${systemPrompt}\n\nUser: ${message}`;

    const response = await this.client.models.generateContent({
      model: MODEL_NAME,
      contents: [{ text: fullPrompt }],
      config: {
        responseMimeType: 'application/json',
      },
    });

    const responseText = response.text;
    if (!responseText) {
      throw new Error('Empty response from Gemini');
    }

    let parsed: RecommendationResult;
    try {
      parsed = JSON.parse(responseText);
    } catch {
      // If JSON parsing fails, wrap the raw text as the response
      parsed = { response: responseText, recommended_product_ids: [] };
    }

    // Validate product IDs exist in catalog
    const validIds = new Set(
      products.filter((p) => 'product_id' in p).map((p: any) => p.product_id)
    );
    parsed.recommended_product_ids = (parsed.recommended_product_ids || []).filter((id) =>
      validIds.has(id),
    );

    return parsed;
  }
}
