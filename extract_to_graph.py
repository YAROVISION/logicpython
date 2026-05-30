import os
import re
import json
import glob
import time
import requests
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Завантажуємо налаштування з .env
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "logica")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

CHECKPOINT_FILE = "processed_segments.json"

# Перевірка наявності ключа API
if not OPENROUTER_API_KEY:
    raise ValueError("Помилка: OPENROUTER_API_KEY не знайдено в .env")

# Схема для Structured Output
SYSTEM_PROMPT = """Ти — лінгвістичний інженер та експерт з логіки.
Проаналізуй текст підсегменту підручника з логіки. Виділи ключові Концепти, Правила, Помилки та Приклади.
Поверни результат СТРОГО у форматі JSON зі списками nodes та edges відповідно до заданої онтології:

Вузли (nodes):
- id: унікальний ідентифікатор в нижньому регістрі (наприклад, "zakon_totozhnosti", "ponyattya")
- label: тип вузла, строго один з: "Concept" (для загальних понять), "Rule" (для законів/правил), "Fallacy" (для логічних помилок), "Example" (для текстових прикладів/ілюстрацій)
- name: назва українською мовою (наприклад, "Закон тотожності", "Поняття")
- description: коротке пояснення або визначення сутності українською мовою на основі наданого тексту.

Зв'язки (edges):
- source: id вихідного вузла
- target: id цільового вузла
- type: тип зв'язку, строго один з:
  - "SUBCLASS_OF" (для зв'язку Concept -> Concept, де source є підвидом target, наприклад: "Дедуктивний умовивід" -> "Умовивід")
  - "REGULATES" (для зв'язку Rule -> Concept, де правило регулює використання концепту)
  - "VIOLATES" (для зв'язку Fallacy -> Rule або Fallacy -> Concept, де помилка порушує правило чи концепт)
  - "ILLUSTRATES" (для зв'язку Example -> Concept або Example -> Rule, де приклад ілюструє концепт/правило)

Формат відповіді має бути СТРОГО валідним JSON-об'єктом наступного вигляду:
{
  "nodes": [
    {"id": "...", "label": "...", "name": "...", "description": "..."},
    ...
  ],
  "edges": [
    {"source": "...", "target": "...", "type": "..."},
    ...
  ]
}
Ніяких передмов, післямов, пояснень чи Markdown розмітки окрім самого JSON.
"""

def get_ollama_embedding(text):
    """Отримання векторного ембедінгу з Ollama (nomic-embed-text)"""
    url = f"{OLLAMA_BASE_URL}/api/embeddings"
    payload = {
        "model": "nomic-embed-text",
        # search_document: префікс рекомендований для nomic-embed-text при індексуванні
        "prompt": f"search_document: {text}"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json().get("embedding")
        else:
            print(f"Помилка Ollama: {response.text}")
    except Exception as e:
        print(f"Не вдалося згенерувати ембедінг: {e}")
    return None

from llm_rotator import LLMRotator

# Ініціалізація LLMRotator
llm_rotator = LLMRotator()

def extract_entities_with_llm(text):
    """Виклик ротатора LLM для екстракції графу"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Текст підсегменту для аналізу:\n\n{text}"}
    ]
    
    # Спроби ретраю у разі збоїв ротатора
    for attempt in range(3):
        try:
            result_text = llm_rotator.chat_completion(
                messages=messages,
                response_format={"type": "json_object"}
            )
            if result_text:
                # Очищаємо можливі markdown-блоки
                result_text = re.sub(r"^```json\s*", "", result_text, flags=re.IGNORECASE)
                result_text = re.sub(r"\s*```$", "", result_text, flags=re.IGNORECASE)
                return json.loads(result_text)
        except Exception as e:
            print(f"Помилка при запиті до LLM ротатора (Спроба {attempt+1}): {e}")
        time.sleep(2)
    return None

def create_db_and_constraints(driver):
    """Створення бази даних та констрейнтів у Neo4j"""
    # Створюємо базу даних logica, якщо її ще немає (через системну сесію)
    print("Ініціалізація бази даних у Neo4j...")
    try:
        with driver.session(database="system") as session:
            session.run(f"CREATE DATABASE {NEO4J_DATABASE} IF NOT EXISTS")
    except Exception as e:
        print(f"Попередження при створенні БД (можливо, використовується Community Edition): {e}")

    # Створюємо констрейнти та індекси в нашій базі
    with driver.session(database=NEO4J_DATABASE) as session:
        # Унікальність назв вузлів
        session.run("CREATE CONSTRAINT unique_concept IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE")
        session.run("CREATE CONSTRAINT unique_rule IF NOT EXISTS FOR (r:Rule) REQUIRE r.id IS UNIQUE")
        session.run("CREATE CONSTRAINT unique_fallacy IF NOT EXISTS FOR (f:Fallacy) REQUIRE f.id IS UNIQUE")
        session.run("CREATE CONSTRAINT unique_example IF NOT EXISTS FOR (e:Example) REQUIRE e.id IS UNIQUE")
        session.run("CREATE CONSTRAINT unique_segment IF NOT EXISTS FOR (s:Segment) REQUIRE s.name IS UNIQUE")
        
        # Створення векторного індексу для Concept
        session.run("""
        CREATE VECTOR INDEX concept_embeddings_idx IF NOT EXISTS
        FOR (c:Concept) ON (c.embedding)
        OPTIONS {indexConfig: {
          `vector.dimensions`: 768,
          `vector.similarity_function`: 'cosine'
        }}
        """)
        # Створення векторного індексу для Rule
        session.run("""
        CREATE VECTOR INDEX rule_embeddings_idx IF NOT EXISTS
        FOR (r:Rule) ON (r.embedding)
        OPTIONS {indexConfig: {
          `vector.dimensions`: 768,
          `vector.similarity_function`: 'cosine'
        }}
        """)
        print("Констрейнти та векторні індекси успішно налаштовані.")

def write_to_neo4j(driver, segment_info, graph_data):
    """Запис видобутих даних та зв'язків у Neo4j"""
    with driver.session(database=NEO4J_DATABASE) as session:
        # 1. Створюємо/оновлюємо вузол Segment
        session.run("""
        MERGE (s:Segment {name: $name})
        ON CREATE SET s.section = $section, s.pages = $pages, s.total_pages = $total_pages
        ON MATCH SET s.section = $section, s.pages = $pages, s.total_pages = $total_pages
        """, {
            "name": segment_info["segment_name"],
            "section": segment_info["section_name"],
            "pages": segment_info["pages"],
            "total_pages": segment_info["total_pages"]
        })

        # 2. Створюємо вузли
        for node in graph_data.get("nodes", []):
            node_id = node.get("id")
            label = node.get("label", "Concept")
            name = node.get("name")
            description = node.get("description", "")
            
            if not node_id or not name:
                continue

            # Валідація лейблу
            if label not in ["Concept", "Rule", "Fallacy", "Example"]:
                label = "Concept"

            # Отримуємо векторний ембедінг для опису
            embedding = None
            if description:
                embedding = get_ollama_embedding(description)

            # Записуємо вузол
            query = f"""
            MERGE (n:{label} {{id: $id}})
            ON CREATE SET n.name = $name, n.description = $description, n.embedding = $embedding
            ON MATCH SET n.name = $name, n.description = $description, n.embedding = $embedding
            """
            session.run(query, {
                "id": node_id,
                "name": name,
                "description": description,
                "embedding": embedding
            })

            # Зв'язуємо Segment з Концептами або Правилами, які в ньому визначені
            if label in ["Concept", "Rule"]:
                session.run("""
                MATCH (s:Segment {name: $seg_name})
                MATCH (target {id: $target_id})
                MERGE (s)-[:DEFINES]->(target)
                """, {
                    "seg_name": segment_info["segment_name"],
                    "target_id": node_id
                })

        # 3. Створюємо зв'язки (edges)
        for edge in graph_data.get("edges", []):
            source = edge.get("source")
            target = edge.get("target")
            rel_type = edge.get("type")
            
            if not source or not target or not rel_type:
                continue

            # Валідація типу зв'язку
            if rel_type not in ["SUBCLASS_OF", "REGULATES", "VIOLATES", "ILLUSTRATES"]:
                continue

            # Створюємо зв'язок між будь-якими двома сутностями за їх унікальними id
            query = f"""
            MATCH (a {{id: $source}})
            MATCH (b {{id: $target}})
            MERGE (a)-[r:{rel_type}]->(b)
            """
            session.run(query, {"source": source, "target": target})

def main():
    print(f"Підключення до Neo4j на {NEO4J_URI}...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        create_db_and_constraints(driver)
    except Exception as e:
        print(f"Помилка ініціалізації БД: {e}")
        driver.close()
        return

    # Завантажуємо чекпоінт
    processed = []
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            processed = json.load(f)

    json_files = sorted(glob.glob("logica_json_segments/*.json"))
    
    print(f"Знайдено {len(json_files)} файлів сегментів для обробки.")

    for index, file_path in enumerate(json_files):
        filename = os.path.basename(file_path)
        if filename in processed:
            print(f"[{index+1}/{len(json_files)}] Пропущено (вже оброблено): {filename}")
            continue

        print(f"\n[{index+1}/{len(json_files)}] Обробка файлу: {filename}...")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        segment_info = {
            "section_name": data["назва розділу"],
            "segment_name": data["назва сегменту"],
            "total_pages": data["загальна кількість сторінок"],
            "pages": ""
        }

        subsegments = data.get("підсегменти", [])
        if not subsegments:
            print(f"У файлі {filename} немає підсегментів для екстракції.")
            processed.append(filename)
            with open(CHECKPOINT_FILE, "w") as cf:
                json.dump(processed, cf)
            continue

        for sub in subsegments:
            sub_id = sub["підсегмент_id"]
            pages_range = sub["сторінки"]
            text = sub["текст"]

            segment_info["pages"] = pages_range
            print(f"  -> Екстракція підсегменту {sub_id} (сторінки {pages_range})...")

            graph_data = extract_entities_with_llm(text)
            if graph_data:
                nodes_count = len(graph_data.get("nodes", []))
                edges_count = len(graph_data.get("edges", []))
                print(f"     Знайдено сутностей: {nodes_count}, зв'язків: {edges_count}")
                
                # Запис у Neo4j
                write_to_neo4j(driver, segment_info, graph_data)
            else:
                print(f"     [!] Не вдалося розпізнати граф для підсегменту {sub_id}")

        # Зберігаємо прогрес у чекпоінт
        processed.append(filename)
        with open(CHECKPOINT_FILE, "w") as cf:
            json.dump(processed, cf)
        print(f"Успішно імпортовано та зафіксовано: {filename}")

    print("\nЕкстракцію та імпорт графу знань успішно завершено!")
    driver.close()

if __name__ == "__main__":
    main()
