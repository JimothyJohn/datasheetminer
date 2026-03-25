
import { GoogleGenAI } from '@google/genai';
import config from '../config';
import { SCHEMAS } from './gemini_schemas';
import {
  parseValueUnit,
  parseMinMaxUnit,
} from '../types/schemas';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

const MODEL_NAME = "gemini-2.0-flash-exp";

// Known bad manufacturer values that indicate extraction failure
const BAD_MANUFACTURERS = new Set(['ur', 'unknown', 'n/a', 'na', 'none', '']);

export class GeminiService {
  private client: GoogleGenAI;

  constructor() {
    if (!config.gemini.apiKey) {
      console.warn("GEMINI_API_KEY is not set. Scraper will fail.");
    }
    this.client = new GoogleGenAI({ apiKey: config.gemini.apiKey || '' });
  }

  /**
   * Generates content from a document buffer using Gemini.
   */
  async analyzeDocument(
    fileBuffer: Buffer,
    mimeType: string,
    productType: string,
    context: any
  ): Promise<any[]> {

    const prompt = this.buildPrompt(productType, context);

    const tempFilePath = path.join(os.tmpdir(), `gemini_upload_${Date.now()}_${Math.random().toString(36).substring(7)}.pdf`);
    fs.writeFileSync(tempFilePath, fileBuffer);

    let uploadResult: any;

    try {
      // @ts-ignore
      uploadResult = await this.client.files.upload({
        file: tempFilePath,
        config: {
            mimeType: mimeType,
            displayName: context.product_name || 'Datasheet'
        },
      });

      console.log(`Uploaded file to Gemini: ${uploadResult.name}`);

      try {
        const response = await this.client.models.generateContent({
          model: MODEL_NAME,
          contents: [
            { text: prompt },
            {
              fileData: {
                mimeType: uploadResult.mimeType,
                fileUri: uploadResult.uri
              }
            }
          ],
          config: {
            responseMimeType: 'application/json',
            responseSchema: SCHEMAS[productType],
          },
        });

        const responseText = response.text;
        if (!responseText) {
            throw new Error("Empty response from Gemini");
        }

        let rawData: any[] = [];
        try {
          rawData = JSON.parse(responseText);
          if (!Array.isArray(rawData)) rawData = [rawData];
        } catch (e) {
          console.error("Failed to parse Gemini JSON response", e);
          throw new Error("Invalid JSON response from Gemini");
        }

        return this.processAndValidate(rawData, productType, context);

      } catch (genError: any) {
         if (genError.status === 400 || (genError.response && genError.response.status === 400)) {
             throw new Error("Gemini API rejected the file request (400 Invalid Argument).");
         }
         throw genError;
      }

    } finally {
        if (fs.existsSync(tempFilePath)) {
            fs.unlinkSync(tempFilePath);
        }
    }
  }

  /**
   * Generates content from raw text (fallback for corrupt PDFs).
   */
  async analyzeText(
    text: string,
    productType: string,
    context: any
  ): Promise<any[]> {
    const prompt = this.buildPrompt(productType, context, true);

    console.log(`Analyzing text content (${text.length} chars) with Gemini...`);

    try {
        const response = await this.client.models.generateContent({
          model: MODEL_NAME,
          contents: [
            { text: prompt },
            { text: text }
          ],
          config: {
            responseMimeType: 'application/json',
            responseSchema: SCHEMAS[productType],
          },
        });

        const responseText = response.text;
        if (!responseText) {
            throw new Error("Empty response from Gemini");
        }

        let rawData: any[] = [];
        try {
          rawData = JSON.parse(responseText);
          if (!Array.isArray(rawData)) rawData = [rawData];
        } catch (e) {
          console.error("Failed to parse Gemini JSON response", e);
          throw new Error("Invalid JSON response from Gemini");
        }

        return this.processAndValidate(rawData, productType, context);

    } catch (genError: any) {
         console.error("Gemini text analysis failed:", genError);
         throw genError;
    }
  }

  /**
   * Generates content from an HTML page.
   * Fetches the page and sends the HTML content to Gemini for extraction.
   */
  async analyzeHtml(
    htmlContent: string,
    productType: string,
    context: any
  ): Promise<any[]> {
    const prompt = this.buildPrompt(productType, context, false, true);

    console.log(`Analyzing HTML content (${htmlContent.length} chars) with Gemini...`);

    try {
        const response = await this.client.models.generateContent({
          model: MODEL_NAME,
          contents: [
            { text: prompt },
            { text: htmlContent }
          ],
          config: {
            responseMimeType: 'application/json',
            responseSchema: SCHEMAS[productType],
          },
        });

        const responseText = response.text;
        if (!responseText) {
            throw new Error("Empty response from Gemini");
        }

        let rawData: any[] = [];
        try {
          rawData = JSON.parse(responseText);
          if (!Array.isArray(rawData)) rawData = [rawData];
        } catch (e) {
          console.error("Failed to parse Gemini JSON response", e);
          throw new Error("Invalid JSON response from Gemini");
        }

        return this.processAndValidate(rawData, productType, context);

    } catch (genError: any) {
         console.error("Gemini HTML analysis failed:", genError);
         throw genError;
    }
  }

  private buildPrompt(_productType: string, context: any, isText: boolean = false, isHtml: boolean = false): string {
    const sourceDesc = isHtml
      ? "HTML content from a product webpage"
      : isText
        ? "extracted text from a catalog for an industrial product"
        : "a catalog for an industrial product";

    return `You are being presented with ${sourceDesc}.
The following information is already known:
- Product Name: ${context.product_name}
- Manufacturer: ${context.manufacturer}
- Product Family: ${context.product_family}
- Datasheet URL: ${context.url}

Your task is to identify the individual product versions from the document and extract their key technical specifications.

IMPORTANT RULES:
1. For the 'manufacturer' field: extract the REAL manufacturer company name from the document (e.g., "Mitsubishi Electric", "FANUC", "Harmonic Drive", "Parker"). Do NOT use generic values like "UR", "Unknown", or "N/A". If you cannot determine the manufacturer, omit the field entirely.
2. Each product MUST have a unique 'part_number'. This is the specific model number or part designation.
3. Do NOT include the product_name, product_family, or datasheet_url in the output objects unless they differ per item.
4. For 'value;unit' fields (e.g. weight, torque), return a string "value;unit". Example: "5.0;A"
5. For 'min-max;unit' fields, return "min-max;unit". Example: "10-20;V"
6. Extract as many specification fields as possible from the document. Be thorough.
${isText ? '\nThe text may be messy or unstructured (tables flattened). Infer structure where possible.' : ''}
${isHtml ? '\nThe HTML may contain navigation, ads, and other non-product content. Focus only on the technical product specifications.' : ''}

Focus only on the fields defined in the schema.`;
  }

  private processAndValidate(items: any[], productType: string, context: any): any[] {
    const validItems: any[] = [];

    for (const item of items) {
      try {
        const fullItem = {
          ...context,
          ...item,
          product_type: productType,
        };

        // Fix bad manufacturer values - prefer the one from context if LLM returned garbage
        if (fullItem.manufacturer) {
          const normMfg = fullItem.manufacturer.toLowerCase().trim();
          if (BAD_MANUFACTURERS.has(normMfg)) {
            if (context.manufacturer && !BAD_MANUFACTURERS.has(context.manufacturer.toLowerCase().trim())) {
              fullItem.manufacturer = context.manufacturer;
            } else {
              delete fullItem.manufacturer;
            }
          }
        }

        // Transform fields
        const transformed = this.transformFields(fullItem, productType);

        // For types with Zod schemas, validate. For others, pass through.
        // All types go through field transformation which handles ValueUnit/MinMaxUnit parsing.
        validItems.push(transformed);

      } catch (e) {
        console.error(`Validation failed for item: ${(item as any).part_number}`, e);
      }
    }

    return validItems;
  }

  private transformFields(item: any, _type: string): any {
    const newItem: any = { ...item };

    // ValueUnit fields (across all product types)
    const valueUnitFields = [
      // Motor
      'rated_speed', 'max_speed', 'rated_torque', 'peak_torque', 'rated_power',
      'rated_current', 'peak_current', 'voltage_constant', 'torque_constant',
      'resistance', 'inductance', 'rotor_inertia', 'output_power',
      // Gearhead
      'nominal_input_speed', 'max_input_speed', 'max_continuous_torque', 'max_peak_torque',
      'backlash', 'torsional_rigidity', 'noise_level', 'input_shaft_diameter',
      'output_shaft_diameter', 'max_radial_load', 'max_axial_load', 'service_life',
      'weight',
      // Robot arm
      'payload', 'reach', 'pose_repeatability', 'max_tcp_speed',
    ];

    const minMaxUnitFields = [
      'rated_voltage', 'input_voltage', 'ambient_temp', 'operating_temp',
    ];

    const arrayValueUnitFields = [
      'input_voltage_frequency', 'switching_frequency',
    ];

    for (const key of Object.keys(newItem)) {
      const val = newItem[key];

      if (valueUnitFields.includes(key)) {
        if (typeof val === 'string') {
          newItem[key] = parseValueUnit(val) || undefined;
        }
      } else if (minMaxUnitFields.includes(key)) {
        if (typeof val === 'string') {
          newItem[key] = parseMinMaxUnit(val) || undefined;
        }
      } else if (arrayValueUnitFields.includes(key)) {
        if (Array.isArray(val)) {
          newItem[key] = val.map((v: any) => typeof v === 'string' ? parseValueUnit(v) : v).filter((v: any) => v);
        }
      }
    }

    return newItem;
  }
}

export const geminiService = new GeminiService();
