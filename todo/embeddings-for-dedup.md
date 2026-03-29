# Should Datasheetminer Use Embeddings for Deduplication?

## Current Dedup Approach

The pipeline uses three dedup mechanisms:
1. **SHA-256 content hash** — exact byte-level match (intake pipeline only)
2. **URL match** — same URL can't be re-submitted
3. **Deterministic product ID** — UUID5 from normalized `manufacturer:part_number`

These catch exact duplicates but miss **semantic duplicates**: the same datasheet from a different CDN, a slightly re-formatted version, or the same product specs published in a different catalog.

## The Case FOR Embeddings

**Problem embeddings would solve:**
- Same PDF hosted at two different URLs (e.g. manufacturer site vs. distributor mirror)
- Updated revision of a datasheet with minor formatting changes but same specs
- Same product appearing in a family catalog AND a standalone datasheet
- Near-duplicate product variants that should be merged (e.g. same motor with different shaft options published as separate PDFs)

**Approach:**
1. Generate embeddings from the first N pages of each PDF using a multimodal model (Gemini, or a dedicated embedding model like `text-embedding-3-large`)
2. Store embeddings in a vector index (Pinecone, pgvector, or even a local FAISS index)
3. Before promoting a PDF from triage/, query the vector index for nearest neighbors above a similarity threshold (e.g. cosine > 0.95)
4. If a near-match exists, flag it as a potential duplicate for review instead of auto-promoting

**Benefits:**
- Catches semantic duplicates that hash/URL checks miss
- Could also power a "similar products" search feature on the frontend
- Enables fuzzy matching of product specs across manufacturers

## The Case AGAINST Embeddings

**Complexity cost:**
- Adds a vector database dependency (infra, cost, maintenance)
- Embedding generation adds latency to the intake pipeline (1-3s per PDF)
- Threshold tuning is empirical — too aggressive and you reject legitimate similar products, too lax and duplicates slip through
- The current dataset is ~500 products and ~50 datasheets. At this scale, exact dedup handles 99% of cases

**False positive risk:**
- Motor datasheets from the same manufacturer often look very similar (same template, same table layout, different specs). Embedding similarity would flag these as duplicates when they're actually different products
- A "Kollmorgen AKM" catalog and a "Kollmorgen AKM" single-model datasheet would embed similarly but should both be kept

**What the current approach already covers:**
- Content hash catches exact re-uploads (the most common duplicate scenario)
- URL dedup catches re-submissions of known URLs
- Deterministic product IDs prevent the same manufacturer+part_number from being stored twice
- The blacklist prevents known-bad PDFs from being re-processed

## Recommendation

**Not now. Revisit at ~5,000 datasheets.**

The current hash + URL + product ID dedup is sufficient for the current scale. The marginal duplicates that embeddings would catch (CDN mirrors, reformatted PDFs) are rare enough to handle manually. The false positive problem with embeddings (similar-looking but different products) is harder to solve than the duplication problem itself.

**When to reconsider:**
- Dataset grows past 5,000 datasheets and manual dedup becomes impractical
- Users start uploading PDFs from multiple sources for the same product (distributor mirrors)
- A "similar products" search feature is needed on the frontend
- The pipeline starts ingesting PDFs from automated crawlers (where duplicate URLs are common)

**If/when implementing, start small:**
- Use Gemini's built-in embedding API (no new infra)
- Store embeddings as a field on the Datasheet DynamoDB record (no vector DB yet)
- Do brute-force cosine similarity against all existing embeddings (fast enough at <10k items)
- Only flag potential duplicates for human review — don't auto-reject based on similarity alone
