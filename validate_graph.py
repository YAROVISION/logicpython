import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load configuration from .env
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "logica")

def validate_graph():
    print(f"Connecting to Neo4j database '{NEO4J_DATABASE}' at {NEO4J_URI}...")
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
    except Exception as e:
        print(f"[-] Connection failed: {e}")
        return

    with driver.session(database=NEO4J_DATABASE) as session:
        print("\n=== Graph Validation Report ===\n")

        # 1. Count nodes per label
        print("--- Node Counts ---")
        node_counts = session.run("""
        MATCH (n)
        RETURN labels(n)[0] as label, count(n) as count
        ORDER BY count DESC
        """)
        total_nodes = 0
        for record in node_counts:
            label = record["label"] or "No Label"
            count = record["count"]
            total_nodes += count
            print(f"  * {label}: {count}")
        print(f"  Total Nodes: {total_nodes}\n")

        # 2. Count relationships per type
        print("--- Relationship Counts ---")
        rel_counts = session.run("""
        MATCH ()-[r]->()
        RETURN type(r) as rel_type, count(r) as count
        ORDER BY count DESC
        """)
        total_rels = 0
        for record in rel_counts:
            rel_type = record["rel_type"]
            count = record["count"]
            total_rels += count
            print(f"  * {rel_type}: {count}")
        print(f"  Total Relationships: {total_rels}\n")

        # 3. Check subclass relations depth
        print("--- Subclass Hierarchy Check ---")
        path_res = session.run("""
        MATCH path = (c:Concept)-[:SUBCLASS_OF*]->(parent:Concept)
        RETURN length(path) as len, [node in nodes(path) | node.name] as path_names
        ORDER BY len DESC
        LIMIT 5
        """)
        paths = list(path_res)
        if paths:
            print("  Top 5 longest subclass paths:")
            for p in paths:
                print(f"    - Depth {p['len']}: {' -> '.join(p['path_names'])}")
        else:
            print("  No SUBCLASS_OF hierarchy paths found.")
        print()

        # 4. Find isolated/orphan nodes
        print("--- Isolated Nodes Check ---")
        isolated_res = session.run("""
        MATCH (n)
        WHERE count{(n)--()} = 0
        RETURN labels(n)[0] as label, n.id as id, n.name as name
        LIMIT 20
        """)
        isolated_nodes = list(isolated_res)
        if isolated_nodes:
            print(f"  [!] Found {len(isolated_nodes)} (limited to 20) isolated nodes:")
            for node in isolated_nodes:
                print(f"    - [{node['label']}] id: {node['id']}, name: {node['name']}")
        else:
            print("  [+] No isolated nodes found. Every node has at least one connection.")
        print()

        # 5. Missing Embeddings status
        print("--- Embedding Status ---")
        embedding_status = session.run("""
        MATCH (n)
        WHERE labels(n)[0] IN ['Concept', 'Rule', 'Fallacy', 'Example']
        RETURN labels(n)[0] as label, count(n) as total, count(n.embedding) as with_emb
        ORDER BY label
        """)
        for rec in embedding_status:
            label = rec["label"]
            total = rec["total"]
            with_emb = rec["with_emb"]
            missing = total - with_emb
            status_icon = "[+]" if missing == 0 else "[!]"
            print(f"  {status_icon} {label}: total={total}, with_embedding={with_emb}, missing={missing}")
        
    driver.close()

if __name__ == "__main__":
    validate_graph()
