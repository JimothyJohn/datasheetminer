/**
 * Recommendation chat — AI-powered product recommendation via conversational interface.
 * Users describe requirements and receive matching product suggestions from the database.
 */

import { useState, useRef, useEffect } from 'react';
import { Product } from '../types/models';
import { formatValue } from '../utils/formatting';
import { sanitizeUrl } from '../utils/sanitize';
import { apiClient } from '../api/client';
import ProductDetailModal from './ProductDetailModal';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  products?: Product[];
}

export default function RecommendationChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [clickPosition, setClickPosition] = useState<{ x: number; y: number } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSend = async () => {
    const text = inputText.trim();
    if (!text || isLoading) return;

    setInputText('');
    setError(null);

    // Add user message
    const userMessage: ChatMessage = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMessage]);

    // Build history for API (convert to role format Gemini expects)
    const history = messages.map((m) => ({
      role: m.role === 'user' ? 'user' : 'model',
      content: m.content,
    }));

    setIsLoading(true);
    try {
      const result = await apiClient.recommend(text, history);
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: result.response,
        products: result.products,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      setError(err.message || 'Failed to get recommendation');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleProductClick = (product: Product, e: React.MouseEvent) => {
    setSelectedProduct(product);
    setClickPosition({ x: e.clientX, y: e.clientY });
  };

  const formatSpec = (product: Product): string => {
    const specs: string[] = [];
    const p = product as any;
    if (p.rated_torque) specs.push(formatValue(p.rated_torque));
    if (p.rated_speed) specs.push(formatValue(p.rated_speed));
    if (p.rated_voltage) specs.push(formatValue(p.rated_voltage));
    if (p.rated_power) specs.push(formatValue(p.rated_power));
    if (p.payload) specs.push(formatValue(p.payload));
    if (p.reach) specs.push(formatValue(p.reach));
    if (p.gear_ratio) specs.push(`Ratio: ${p.gear_ratio}:1`);
    return specs.slice(0, 3).join(' | ');
  };

  const datasheetUrl = (product: Product): string | null => {
    const url = typeof product.datasheet_url === 'string'
      ? product.datasheet_url
      : (product.datasheet_url as any)?.url ?? null;
    return url?.startsWith('http') ? url : null;
  };

  return (
    <div className="recommendation-chat">
      <div className="chat-messages">
        {messages.length === 0 && !isLoading && (
          <div className="chat-welcome">
            <h2>Product Recommendation</h2>
            <p>Describe your requirements and I'll recommend matching products from the database.</p>
            <div className="chat-suggestions">
              {[
                'I need a servo motor with at least 5 Nm torque at 3000 rpm',
                'What drives support EtherCAT fieldbus?',
                'Find me a compact gearhead with a 10:1 ratio',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  className="chat-suggestion-btn"
                  onClick={() => {
                    setInputText(suggestion);
                    inputRef.current?.focus();
                  }}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`chat-bubble chat-bubble-${msg.role}`}>
            <div className="chat-bubble-content">{msg.content}</div>
            {msg.products && msg.products.length > 0 && (
              <div className="chat-products">
                {msg.products.map((product) => (
                  <button
                    key={product.product_id}
                    className="chat-product-card"
                    onClick={(e) => handleProductClick(product, e)}
                  >
                    <div className="chat-product-header">
                      <span className="chat-product-manufacturer">{product.manufacturer}</span>
                      <span className="chat-product-type">{product.product_type}</span>
                    </div>
                    {datasheetUrl(product) ? (
                      <a
                        href={sanitizeUrl(datasheetUrl(product)!)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="chat-product-part-link"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {product.part_number || 'N/A'}
                      </a>
                    ) : (
                      <span className="chat-product-part">{product.part_number || 'N/A'}</span>
                    )}
                    <span className="chat-product-specs">{formatSpec(product)}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="chat-bubble chat-bubble-assistant">
            <div className="chat-bubble-content chat-loading">Thinking...</div>
          </div>
        )}

        {error && (
          <div className="chat-error">
            {error}
            <button onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <input
          ref={inputRef}
          type="text"
          className="chat-input"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe your requirements..."
          disabled={isLoading}
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={isLoading || !inputText.trim()}
        >
          Send
        </button>
      </div>

      <ProductDetailModal
        product={selectedProduct}
        onClose={() => setSelectedProduct(null)}
        clickPosition={clickPosition}
      />
    </div>
  );
}
