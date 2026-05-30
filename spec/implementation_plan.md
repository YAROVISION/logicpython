# Migration to OpenRouter 2048-Dimension Embedding Model

This plan details the steps to migrate the GraphRAG embedding model from Ollama's local `nomic-embed-text` (768 dimensions) to OpenRouter's `nvidia/llama-nemotron-embed-vl-1b-v2:free` (2048 dimensions). 

Since Neo4j vector indexes require the query vector dimension to match the index dimension exactly, we will drop the old 768-dimensional indexes, recreate them as 2048-dimensional indexes, and re-populate embeddings for all 852 nodes with descriptions using OpenRouter.

## User Review Required

> [!WARNING]
> We will recreate the vector indexes. This requires dropping the existing `concept_embeddings_idx`, `rule_embeddings_idx`, `fallacy_embeddings_idx`, and `example_embeddings_idx` and recreating them with 2048 dimensions.
> Generating 852 embeddings via OpenRouter's free API might be subject to rate limiting. We will include a delay and retry mechanism to process this transition smoothly.

## Proposed Changes

### 1. Vector Indexes & Embedding Migration Script
We will update the embedding script to drop the old indexes, create the new 2048-dimensional indexes, and update all nodes with OpenRouter embeddings.

#### [MODIFY] [populate_embeddings.py](file:///Users/kostantinkrivula/Desktop/sqlbase/logica/populate_embeddings.py)
* Read `OPENROUTER_API_KEY` from `.env`.
* Implement a helper function `get_openrouter_embedding(text)` using the OpenRouter API with retry logic and error handling.
* Add index recreation:
  * Drop old indexes: `DROP INDEX <index_name> IF EXISTS`.
  * Create new indexes with `vector.dimensions: 2048`.
* Query all nodes with a non-empty `description`, generate 2048-dimensional embeddings, and save them.

---

### 2. Query Orchestrator Migration
We will update the query engine to use the OpenRouter embedding model.

#### [MODIFY] [query_graphrag.py](file:///Users/kostantinkrivula/Desktop/sqlbase/logica/query_graphrag.py)
* Read `OPENROUTER_API_KEY` from `.env`.
* Replace `get_ollama_query_embedding` with `get_openrouter_query_embedding`.
* Ensure that user queries generate 2048-dimensional vectors for Neo4j lookup.

---

### 3. Streamlit UI Updates
We will modify the Streamlit app to run queries using the new OpenRouter embeddings.

#### [MODIFY] [app.py](file:///Users/kostantinkrivula/Desktop/sqlbase/logica/app.py)
* Update references to use the OpenRouter embedding generator.
* Verify connectivity to OpenRouter before launching.

## Verification Plan

### Automated Tests
1. Run the migration script:
   ```bash
   python3 populate_embeddings.py
   ```
2. Verify in the Neo4j console or via python that indexes are `ONLINE` and have `2048` dimensions.
3. Run the query engine with the test query:
   ```bash
   python3 query_graphrag.py --query "Суддя заявив, що оскільки підсудний запізнився, він точно винен. Яка тут помилка?"
   ```

### Manual Verification
1. Open the Streamlit web interface and submit questions to verify that semantic search functions correctly with the new 2048-dimensional embeddings.
