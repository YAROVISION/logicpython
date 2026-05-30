import os
import argparse
import requests
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Завантажуємо конфігурацію з .env
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "logica")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Промпт для генерації відповіді
PROMPT_TEMPLATE = """Ти — аналітична модель штучного інтелекту, що спеціалізується на логіці.
Перед тобою поставлено завдання відповісти на запит користувача, спираючись на наданий контекст, який було витягнуто з графової бази знань підручника з логіки.

Запит користувача:
{query}

Наданий графовий контекст (знання з підручника):
{context}

Інструкція:
1. Проаналізуй запит користувача, використовуючи лише факти, правила, поняття та приклади з наданого контексту.
2. Не вигадуй інформацію, якої немає в контексті. Якщо інформації недостатньо, вкажи про це.
3. Твоя відповідь має бути структурованою, логічною та спиратися на термінологію підручника.
"""

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
EMBEDDING_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"

def get_openrouter_query_embedding(query_text):
    """Отримання векторного ембедінгу для запиту з OpenRouter"""
    if not OPENROUTER_API_KEY:
        print("Помилка: OPENROUTER_API_KEY не знайдено в .env")
        return None
    url = "https://openrouter.ai/api/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": EMBEDDING_MODEL,
        "input": query_text
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return data.get("data", [{}])[0].get("embedding")
        else:
            print(f"Помилка OpenRouter (embedding): {response.text}")
    except Exception as e:
        print(f"Помилка підключення до OpenRouter для ембедінгу: {e}")
    return None

def query_llm(model_name, prompt):
    """Універсальний виклик LLM (Ollama або OpenRouter)"""
    if "/" in model_name or model_name.endswith(":free"):
        if not OPENROUTER_API_KEY:
            return "Помилка: OPENROUTER_API_KEY не знайдено в .env"
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=90)
            if response.status_code == 200:
                return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                return f"Помилка OpenRouter: {response.text}"
        except Exception as e:
            return f"Помилка підключення до OpenRouter: {e}"
    else:
        # Виклик локальної LLM через Ollama
        url = f"{OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False
        }
        try:
            response = requests.post(url, json=payload, timeout=90)
            if response.status_code == 200:
                return response.json().get("response")
            else:
                return f"Помилка генерації Ollama: {response.text}"
        except Exception as e:
            return f"Помилка підключення до Ollama для генерації: {e}"

def search_subgraph(driver, query_embedding, limit=3):
    """Пошук суміжних вузлів та зв'язків (subgraph) у Neo4j"""
    context_parts = []
    found_nodes = []
    all_relationships = []

    with driver.session(database=NEO4J_DATABASE) as session:
        # Шукаємо найближчі концепти
        try:
            concept_res = session.run("""
            CALL db.index.vector.queryNodes('concept_embeddings_idx', $limit, $embedding)
            YIELD node, score
            RETURN node.id as id, node.name as name, node.description as description, 'Concept' as label, score
            """, {"embedding": query_embedding, "limit": limit})
            found_nodes.extend(list(concept_res))
        except Exception as e:
            pass

        # Шукаємо найближчі правила
        try:
            rule_res = session.run("""
            CALL db.index.vector.queryNodes('rule_embeddings_idx', $limit, $embedding)
            YIELD node, score
            RETURN node.id as id, node.name as name, node.description as description, 'Rule' as label, score
            """, {"embedding": query_embedding, "limit": limit})
            found_nodes.extend(list(rule_res))
        except Exception as e:
            pass

        # Шукаємо найближчі помилки
        try:
            fallacy_res = session.run("""
            CALL db.index.vector.queryNodes('fallacy_embeddings_idx', $limit, $embedding)
            YIELD node, score
            RETURN node.id as id, node.name as name, node.description as description, 'Fallacy' as label, score
            """, {"embedding": query_embedding, "limit": limit})
            found_nodes.extend(list(fallacy_res))
        except Exception as e:
            pass

        # Шукаємо найближчі приклади
        try:
            example_res = session.run("""
            CALL db.index.vector.queryNodes('example_embeddings_idx', $limit, $embedding)
            YIELD node, score
            RETURN node.id as id, node.name as name, node.description as description, 'Example' as label, score
            """, {"embedding": query_embedding, "limit": limit})
            found_nodes.extend(list(example_res))
        except Exception as e:
            pass

        if not found_nodes:
            return {
                "context_text": "Не знайдено релевантних знань у графовій базі даних.",
                "nodes": [],
                "relationships": []
            }

        # Сортуємо результати за скором подібності
        found_nodes = sorted(found_nodes, key=lambda x: x["score"], reverse=True)[:limit]

        context_parts.append("=== Знайдені ключові сутності ===")
        for node in found_nodes:
            n_id = node["id"]
            n_name = node["name"]
            n_desc = node["description"]
            n_label = node["label"]
            score = node["score"]
            
            context_parts.append(f"- [{n_label}] \"{n_name}\" (Подібність: {score:.4f}):")
            context_parts.append(f"  Опис: {n_desc}")

            # Знаходимо зв'язки першого рівня для цього вузла
            relations = session.run("""
            MATCH (n {id: $id})-[r]-(m)
            RETURN type(r) as rel_type, labels(m)[0] as m_label, m.name as m_name, m.id as m_id, m.description as m_desc
            LIMIT 10
            """, {"id": n_id})

            rel_list = list(relations)
            if rel_list:
                context_parts.append("  Зв'язки в базі знань:")
                for rel in rel_list:
                    m_name = rel["m_name"]
                    m_label = rel["m_label"]
                    rel_type = rel["rel_type"]
                    m_id = rel["m_id"]
                    
                    context_parts.append(f"    * -[{rel_type}]-> [{m_label}] \"{m_name}\"")
                    all_relationships.append({
                        "source_id": n_id,
                        "source_name": n_name,
                        "source_label": n_label,
                        "target_id": m_id,
                        "target_name": m_name,
                        "target_label": m_label,
                        "type": rel_type
                    })
            context_parts.append("")

    return {
        "context_text": "\n".join(context_parts),
        "nodes": found_nodes,
        "relationships": all_relationships
    }

def run_query_cycle(driver, query_text, model_name, limit):
    print("Генерація векторного ембедінгу для запиту...")
    query_embedding = get_openrouter_query_embedding(query_text)
    
    if not query_embedding:
        print("Помилка: не вдалося згенерувати ембедінг. Переконайтеся, що налаштовано OPENROUTER_API_KEY у .env.")
        return

    print("Пошук релевантного контексту у графовій базі даних...")
    result = search_subgraph(driver, query_embedding, limit=limit)
    graph_context = result["context_text"]

    print("\n--- Знайдений графовий контекст ---")
    print(graph_context)
    print("-----------------------------------\n")

    # Формуємо фінальний промпт для LLM
    final_prompt = PROMPT_TEMPLATE.format(query=query_text, context=graph_context)

    print(f"Надсилання контексту до моделі {model_name}...")
    response = query_llm(model_name, final_prompt)

    print("\n=== ВІДПОВІДЬ ГРАФОВОГО АСИСТЕНТА (GraphRAG) ===")
    print(response)
    print("================================================\n")

def main():
    parser = argparse.ArgumentParser(description="GraphRAG інтерфейс для підручника з логіки")
    parser.add_argument("--query", type=str, help="Запит користувача або текст для аналізу")
    parser.add_argument("--model", type=str, default="nvidia/llama-3.1-nemotron-70b-instruct:free", help="Назва моделі для генерації відповіді (за замовчуванням: nvidia/llama-3.1-nemotron-70b-instruct:free)")
    parser.add_argument("--limit", type=int, default=3, help="Кількість найближчих вузлів для пошуку контексту")
    parser.add_argument("--interactive", "-i", action="store_true", help="Запустити інтерактивний режим")
    args = parser.parse_args()

    if not args.query and not args.interactive:
        parser.print_help()
        return

    print(f"Підключення до Neo4j ({NEO4J_URI}, БД: {NEO4J_DATABASE})...")
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
    except Exception as e:
        print(f"Помилка підключення до Neo4j: {e}")
        return

    if args.interactive:
        print("\n=== Інтерактивний режим GraphRAG ===")
        print("Введіть ваше питання про логіку або вкажіть приклад тексту для аналізу.")
        print("Введіть 'exit' або 'quit' для виходу.")
        while True:
            try:
                query_text = input("\nЗапит > ").strip()
                if not query_text:
                    continue
                if query_text.lower() in ["exit", "quit", "вихід", "вийти"]:
                    break
                run_query_cycle(driver, query_text, args.model, args.limit)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Помилка під час обробки: {e}")
    else:
        run_query_cycle(driver, args.query, args.model, args.limit)

    driver.close()

if __name__ == "__main__":
    main()
