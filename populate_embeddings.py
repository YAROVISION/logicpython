import os
import time
import requests
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load configuration from .env
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "logica")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
EMBEDDING_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"

if not OPENROUTER_API_KEY:
    raise ValueError("Error: OPENROUTER_API_KEY not found in .env file.")

def get_openrouter_embeddings_batch(texts, retries=3, delay=3):
    """Obtain multiple vector embeddings from OpenRouter in a single batched call"""
    url = "https://openrouter.ai/api/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": EMBEDDING_MODEL,
        "input": texts
    }
    
    for attempt in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                items = data.get("data", [])
                # Sort items by index to ensure alignment
                items_sorted = sorted(items, key=lambda x: x.get("index", 0))
                embeddings = [item.get("embedding") for item in items_sorted]
                if len(embeddings) == len(texts) and all(e is not None for e in embeddings):
                    return embeddings
                else:
                    print(f"\n[!] Warning: Received {len(embeddings)} embeddings for {len(texts)} inputs. Retrying...", end="")
            elif response.status_code == 429:
                print(f"\n[!] Rate limited. Waiting {delay * 2}s...", end="")
                time.sleep(delay * 2)
            else:
                print(f"\n[-] OpenRouter returned status {response.status_code}: {response.text}", end="")
        except Exception as e:
            print(f"\n[-] Connection to OpenRouter failed (Attempt {attempt+1}): {e}", end="")
        
        if attempt < retries - 1:
            time.sleep(delay)
            
    return None

def recreate_vector_indexes(driver):
    """Drop 768-dimensional indexes and create 2048-dimensional indexes"""
    labels = ["Concept", "Rule", "Fallacy", "Example"]
    with driver.session(database=NEO4J_DATABASE) as session:
        for label in labels:
            idx_name = f"{label.lower()}_embeddings_idx"
            
            # Drop index
            print(f"Dropping index '{idx_name}' if exists...")
            session.run(f"DROP INDEX {idx_name} IF EXISTS")
            
            # Create index with 2048 dimensions
            print(f"Creating vector index '{idx_name}' (2048 dim) for label '{label}'...")
            query = f"""
            CREATE VECTOR INDEX {idx_name} IF NOT EXISTS
            FOR (n:{label}) ON (n.embedding)
            OPTIONS {{indexConfig: {{
              `vector.dimensions`: 2048,
              `vector.similarity_function`: 'cosine'
            }}}}
            """
            session.run(query)
    print("[+] Vector indexes recreated with 2048 dimensions successfully.")

def populate_openrouter_embeddings(batch_size=16):
    print(f"Connecting to Neo4j database '{NEO4J_DATABASE}' at {NEO4J_URI}...")
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
    except Exception as e:
        print(f"[-] Connection to Neo4j failed: {e}")
        return

    # 1. Recreate indexes to support 2048 dimensions
    recreate_vector_indexes(driver)

    # 2. Find all nodes requiring embeddings
    print("\nScanning database for nodes to re-embed...")
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run("""
        MATCH (n)
        WHERE labels(n)[0] IN ['Concept', 'Rule', 'Fallacy', 'Example']
          AND n.description IS NOT NULL AND n.description <> ''
        RETURN labels(n)[0] as label, n.id as id, n.description as description
        """)
        nodes_to_update = list(result)
        
    total_nodes = len(nodes_to_update)
    print(f"[+] Found {total_nodes} nodes to embed using OpenRouter.")

    if total_nodes == 0:
        print("[+] No nodes found with descriptions. Exiting.")
        driver.close()
        return

    success_count = 0
    start_time = time.time()

    # 3. Generate embeddings and save in batches
    with driver.session(database=NEO4J_DATABASE) as session:
        for i in range(0, total_nodes, batch_size):
            batch = nodes_to_update[i:i+batch_size]
            batch_texts = [node["description"] for node in batch]
            
            print(f"Processing nodes [{i+1}-{min(i+batch_size, total_nodes)}/{total_nodes}]...", end="", flush=True)
            
            embeddings = get_openrouter_embeddings_batch(batch_texts)
            if embeddings:
                # Write batch embeddings to Neo4j
                for node, embedding in zip(batch, embeddings):
                    label = node["label"]
                    node_id = node["id"]
                    session.run(f"""
                    MATCH (n:{label} {{id: $id}})
                    SET n.embedding = $embedding
                    """, {"id": node_id, "embedding": embedding})
                print(" Success.")
                success_count += len(batch)
            else:
                print(" Failed (Batch failed).")
            
            # Rate limiting mitigation between batches
            time.sleep(2.0)

    elapsed_time = time.time() - start_time
    print(f"\n[+] Re-embedding complete. Successfully populated {success_count}/{total_nodes} nodes in {elapsed_time:.1f}s.")
    driver.close()

if __name__ == "__main__":
    populate_openrouter_embeddings()
