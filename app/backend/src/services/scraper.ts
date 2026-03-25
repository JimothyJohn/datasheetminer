
import axios from 'axios';
import { v5 as uuidv5 } from 'uuid';
import { DynamoDBService } from '../db/dynamodb';
import { ProductType } from '../types/models';
import config from '../config';
import { geminiService } from './gemini';

const db = new DynamoDBService({ tableName: config.dynamodb.tableName });

// UUID v5 Namespace (DNS)
const PRODUCT_NAMESPACE = '6ba7b810-9dad-11d1-80b4-00c04fd430c8';

function normalizeString(s: string | undefined | null): string {
  if (!s) return '';
  return s.toLowerCase().replace(/[^a-z0-9]/g, '');
}

/**
 * Detect if a URL points to a PDF (by extension or content-type header).
 */
function isPdfUrl(url: string): boolean {
  const lowerUrl = url.toLowerCase();
  if (lowerUrl.endsWith('.pdf')) return true;
  if (lowerUrl.includes('getdocument')) return true;
  // URLs with pdf in query params
  if (lowerUrl.includes('.pdf?')) return true;
  return false;
}

// Helper to extract text from PDF buffer using pdfjs-dist
async function extractTextFromPdf(buffer: Buffer, pages?: number[]): Promise<string> {
    try {
        const pdfjsLib = await import('pdfjs-dist/legacy/build/pdf.mjs');
        const uint8Array = new Uint8Array(buffer);
        const loadingTask = pdfjsLib.getDocument({data: uint8Array});
        const pdf = await loadingTask.promise;

        console.log(`[Text Extraction] PDF loaded. Pages: ${pdf.numPages}`);

        let fullText = "";
        const targetPages = (pages && pages.length > 0)
            ? pages.map(p => p + 1)
            : Array.from({length: Math.min(pdf.numPages, 30)}, (_, i) => i + 1);

        for (const pageNum of targetPages) {
             if (pageNum > pdf.numPages || pageNum < 1) continue;
             try {
                 const page = await pdf.getPage(pageNum);
                 const textContent = await page.getTextContent();
                 const pageText = textContent.items.map((item: any) => item.str).join(' ');
                 fullText += `--- Page ${pageNum} ---\n${pageText}\n\n`;
             } catch (pageError) {
                 console.warn(`Failed to extract text from page ${pageNum}`, pageError);
             }
        }
        return fullText;
    } catch (e) {
        console.error("Failed to extract text from PDF:", e);
        return "";
    }
}

/**
 * Fetch HTML content from a URL with browser-like headers.
 */
async function fetchHtmlContent(url: string): Promise<string> {
    const response = await axios.get(url, {
        timeout: 30000,
        headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        },
        // Accept both text and binary responses
        responseType: 'text',
        // Don't throw on non-2xx for redirect handling
        maxRedirects: 5,
    });

    return response.data;
}

export class ScraperService {

  async scrapeDatasheet(id: string, type?: string): Promise<{ success: boolean; count: number; error?: string }> {
    console.log(`Scraping datasheet ${id} (type hint: ${type || 'none'})`);

    // 1. Get Datasheet - try direct read first, then scan if type not provided
    let datasheet: any;

    if (type) {
      try {
        // Direct read with known type
        const result = await db.read(id, type as ProductType);
        if (result) datasheet = result;
      } catch (e) {
        console.warn(`Direct read failed for ${id} with type ${type}`);
      }
    }

    if (!datasheet) {
      // Scan all datasheets to find by ID
      try {
        const allDatasheets = await db.listDatasheets();
        datasheet = allDatasheets.find((ds: any) =>
          ds.datasheet_id === id || ds.SK === `DATASHEET#${id}`
        );
      } catch (e) {
        console.error(`Failed to find datasheet ${id} by scanning`, e);
      }
    }

    if (!datasheet || !datasheet.url) {
        return { success: false, count: 0, error: 'Datasheet not found or has no URL' };
    }

    // Resolve the actual product type from the datasheet
    // The datasheet's product_type indicates what kind of products to extract
    const productType = datasheet.product_type || type || 'motor';
    // For datasheets, the component_type or product_type field tells us what to extract
    const extractionType = datasheet.component_type || productType;

    console.log(`Datasheet found: ${datasheet.product_name}, type: ${extractionType}, URL: ${datasheet.url}`);

    const context = {
        product_name: datasheet.product_name,
        manufacturer: datasheet.manufacturer || "",
        product_family: datasheet.product_family || "",
        url: datasheet.url
    };

    let extractedProducts: any[] | null = null;

    // Determine if URL is a PDF or HTML page
    const urlIsPdf = isPdfUrl(datasheet.url);

    if (urlIsPdf) {
        // === PDF FLOW ===
        extractedProducts = await this.scrapePdf(datasheet, extractionType, context);
    } else {
        // === HTML FLOW ===
        extractedProducts = await this.scrapeHtml(datasheet.url, extractionType, context);
    }

    const products = extractedProducts || [];

    if (products.length === 0) {
        return { success: false, count: 0, error: 'No products extracted' };
    }

    // 4. Generate IDs and Save
    const productsToSave: any[] = [];

    for (const product of products) {
        const normManufacturer = normalizeString(product.manufacturer) || normalizeString(datasheet.manufacturer);
        const normPartNumber = normalizeString(product.part_number);
        const normName = normalizeString(product.product_name);

        let idString = "";
        if (normManufacturer && normPartNumber) {
          idString = `${normManufacturer}:${normPartNumber}`;
        } else if (normManufacturer && normName) {
          idString = `${normManufacturer}:${normName}`;
        } else {
          console.warn("Skipping product due to insufficient ID data", product);
          continue;
        }

        const productId = uuidv5(idString, PRODUCT_NAMESPACE);

        product.product_id = productId;
        product.datasheet_url = datasheet.url;
        product.PK = `PRODUCT#${extractionType.toUpperCase()}`;
        product.SK = `PRODUCT#${productId}`;

        productsToSave.push(product);
    }

    let savedCount = 0;
    for (const p of productsToSave) {
        const success = await db.create(p);
        if (success) savedCount++;
    }

    // Update Datasheet last_scraped status
    try {
        const dsType = datasheet.product_type || extractionType;
        const dsId = datasheet.datasheet_id || id;
        await db.updateDatasheet(dsId, dsType, {
            last_scraped: new Date().toISOString()
        });
        console.log(`Updated datasheet ${dsId} last_scraped timestamp`);
    } catch (updateError) {
        console.warn("Failed to update datasheet last_scraped:", updateError);
    }

    return { success: true, count: savedCount };
  }

  /**
   * Scrape a PDF document - download, optionally slice pages, send to Gemini.
   */
  private async scrapePdf(
    datasheet: any,
    productType: string,
    context: any
  ): Promise<any[] | null> {
    let fileBuffer: Buffer;
    let mimeType: string;
    let originalBuffer: Buffer;

    try {
        console.log(`Downloading PDF from ${datasheet.url}...`);
        const response = await axios.get(datasheet.url, {
            responseType: 'arraybuffer',
            timeout: 30000,
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            }
        });

        fileBuffer = Buffer.from(response.data);
        originalBuffer = Buffer.from(response.data);
        mimeType = response.headers['content-type'] || 'application/pdf';

        if (fileBuffer.slice(0, 4).toString() === '%PDF') {
            mimeType = 'application/pdf';
        }

        console.log(`Downloaded ${fileBuffer.length} bytes, type: ${mimeType}`);

        // If downloaded content is not actually a PDF, try HTML flow instead
        if (mimeType.includes('text/html') || fileBuffer.slice(0, 5).toString() === '<html' || fileBuffer.slice(0, 5).toString() === '<!DOC') {
            console.log("Downloaded content is HTML, not PDF. Switching to HTML flow.");
            return this.scrapeHtml(datasheet.url, productType, context);
        }

    } catch (e) {
        console.error("Download failed", e);
        return null;
    }

    let extractedProducts: any[] | null = null;

    // Only slice if pages are specified AND they're not just [0,1] (cover pages)
    const pages = datasheet.pages;
    const hasUsefulPages = pages && pages.length > 0 && !(pages.length <= 2 && pages.every((p: number) => p <= 1));

    if (mimeType === 'application/pdf' && hasUsefulPages) {
        try {
            const { PDFDocument } = await import('pdf-lib');
            const pdfDoc = await PDFDocument.load(fileBuffer, { ignoreEncryption: true });
            const pageCount = pdfDoc.getPageCount();
            const pagesToKeep = pages.filter((p: number) => p >= 0 && p < pageCount);

            if (pagesToKeep.length > 0) {
                const newPdf = await PDFDocument.create();
                const copiedPages = await newPdf.copyPages(pdfDoc, pagesToKeep);
                copiedPages.forEach((p: any) => newPdf.addPage(p));

                const newPdfBytes = await newPdf.save();
                fileBuffer = Buffer.from(newPdfBytes);
                console.log(`Sliced PDF to ${pagesToKeep.length} pages (from ${pageCount}). New size: ${fileBuffer.length}`);
            }
        } catch (sliceError: any) {
            console.error("PDF Slicing/Loading failed.", sliceError.message);
            console.log("Switching to Text Extraction Fallback...");

            const text = await extractTextFromPdf(originalBuffer, hasUsefulPages ? pages : undefined);
            if (text.length > 100) {
                 console.log(`Extracted ${text.length} chars. Sending text to Gemini.`);
                 try {
                     extractedProducts = await geminiService.analyzeText(text, productType, context);
                 } catch (geminiTextError) {
                     console.error("Gemini text analysis also failed.", geminiTextError);
                 }
            }
        }
    } else if (pages && pages.length <= 2 && pages.every((p: number) => p <= 1)) {
        console.log(`Ignoring pages=[${pages}] (cover pages only). Sending full PDF to Gemini.`);
    }

    // Main flow - send (possibly sliced) PDF to Gemini
    if (!extractedProducts) {
         try {
            extractedProducts = await geminiService.analyzeDocument(
                fileBuffer,
                mimeType,
                productType,
                context
            );
         } catch (geminiError: any) {
             if (geminiError.message && geminiError.message.includes('400 Invalid Argument')) {
                  console.log("Gemini rejected file (400). Attempting Text Fallback...");
                  const text = await extractTextFromPdf(originalBuffer, hasUsefulPages ? pages : undefined);

                  if (text.length > 100) {
                      extractedProducts = await geminiService.analyzeText(text, productType, context);
                  } else {
                      throw geminiError;
                  }
             } else {
                 throw geminiError;
             }
         }
    }

    return extractedProducts;
  }

  /**
   * Scrape an HTML page - fetch content, send to Gemini for extraction.
   */
  private async scrapeHtml(
    url: string,
    productType: string,
    context: any
  ): Promise<any[] | null> {
    try {
        console.log(`Fetching HTML from ${url}...`);
        const htmlContent = await fetchHtmlContent(url);

        if (!htmlContent || htmlContent.length < 100) {
            console.error("HTML content too short or empty");
            return null;
        }

        console.log(`Fetched ${htmlContent.length} chars of HTML. Sending to Gemini...`);

        // Trim HTML if extremely large (Gemini has input limits)
        const maxHtmlLength = 500000; // ~500KB
        const trimmedHtml = htmlContent.length > maxHtmlLength
            ? htmlContent.substring(0, maxHtmlLength)
            : htmlContent;

        return await geminiService.analyzeHtml(trimmedHtml, productType, context);

    } catch (e) {
        console.error("HTML scraping failed:", e);
        return null;
    }
  }
}

export const scraperService = new ScraperService();
