import streamlit as st
import requests
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from query_graphrag import (
    get_openrouter_query_embedding,
    query_llm,
    search_subgraph,
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
    NEO4J_DATABASE,
    OLLAMA_BASE_URL,
    PROMPT_TEMPLATE
)

# Set page config for a premium wide layout
st.set_page_config(
    page_title="Logic GraphRAG Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling
st.markdown("""
<style>
    /* Sleek gradient background and modern styling */
    .main {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    .title-container {
        padding: 1.5rem;
        background: linear-gradient(135deg, #1e3a8a 0%, #0d9488 100%);
        border-radius: 12px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .title-container h1 {
        margin: 0;
        font-family: 'Outfit', 'Inter', sans-serif;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    .title-container p {
        margin: 5px 0 0 0;
        opacity: 0.9;
        font-size: 1.1rem;
    }
    .card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 12px;
    }
    .entity-tag {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: bold;
        margin-right: 8px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .tag-concept { background-color: #1f6feb; color: #ffffff; }
    .tag-rule { background-color: #238636; color: #ffffff; }
    .tag-fallacy { background-color: #da3633; color: #ffffff; }
    .tag-example { background-color: #d29922; color: #0d1117; }
    .tag-segment { background-color: #8b5cf6; color: #ffffff; }
    
    .relation-badge {
        font-family: monospace;
        background-color: #21262d;
        color: #8b949e;
        padding: 2px 6px;
        border-radius: 4px;
        border: 1px solid #30363d;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to get available models (OpenRouter + Ollama)
def get_available_models():
    models = []
    
    # 1. Add OpenRouter free models
    models.extend([
        "nvidia/llama-3.1-nemotron-70b-instruct:free",
        "google/gemma-2-9b-it:free",
        "meta-llama/llama-3-8b-instruct:free",
        "qwen/qwen-2.5-72b-instruct:free",
        "deepseek/deepseek-chat"
    ])
    
    # 2. Add local Ollama models
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        if r.status_code == 200:
            local_models = [m["name"] for m in r.json().get("models", [])]
            # Exclude embedding models from generation dropdown to avoid confusion
            local_models = [m for m in local_models if "embed" not in m]
            models.extend(local_models)
    except Exception:
        # Fallback local models if Ollama is down
        models.extend(["gemma4:e4b", "qwen2.5-coder:14b"])
        
    return models


# Check services connectivity
def check_connections():
    services = {"neo4j": False, "ollama": False}
    # Neo4j check
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        driver.close()
        services["neo4j"] = True
    except Exception:
        pass
    # Ollama check
    try:
        r = requests.get(OLLAMA_BASE_URL, timeout=2)
        if r.status_code == 200 or "Ollama is running" in r.text:
            services["ollama"] = True
    except Exception:
        pass
    return services

# Get database statistics
def get_db_stats():
    stats = {"nodes": {}, "relationships": {}, "embeddings": {}}
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session(database=NEO4J_DATABASE) as session:
            # Nodes
            nodes = session.run("MATCH (n) RETURN labels(n)[0] as label, count(n) as count")
            for r in nodes:
                lbl = r["label"] or "Unknown"
                stats["nodes"][lbl] = r["count"]
            # Relationships
            rels = session.run("MATCH ()-[r]->() RETURN type(r) as type, count(r) as count")
            for r in rels:
                stats["relationships"][r["type"]] = r["count"]
            # Embeddings status
            emb = session.run("""
            MATCH (n) 
            WHERE labels(n)[0] IN ['Concept', 'Rule', 'Fallacy', 'Example']
            RETURN labels(n)[0] as label, count(n.embedding) as with_emb
            """)
            for r in emb:
                stats["embeddings"][r["label"]] = r["with_emb"]
        driver.close()
    except Exception as e:
        st.sidebar.error(f"Помилка отримання статистики: {e}")
    return stats

# Initialize states
if "messages" not in st.session_state:
    st.session_state.messages = []

# Connections Check
conn = check_connections()

# Sidebar Setup
st.sidebar.title("⚙️ Налаштування системи")

st.sidebar.subheader("Статус з'єднання")
col1, col2 = st.sidebar.columns(2)
with col1:
    if conn["neo4j"]:
        st.success("Neo4j: Online")
    else:
        st.error("Neo4j: Offline")
with col2:
    if conn["ollama"]:
        st.success("Ollama: Online")
    else:
        st.error("Ollama: Offline")

st.sidebar.markdown("---")

# Model configuration
available_models = get_available_models()
selected_model = st.sidebar.selectbox(
    "Оберіть модель LLM:",
    options=available_models,
    index=0
)

limit_nodes = st.sidebar.slider(
    "Кількість джерел з графу (Limit):",
    min_value=1,
    max_value=10,
    value=3
)

st.sidebar.markdown("---")

# Database Stats Section
if st.sidebar.button("📊 Показати статистику бази даних"):
    with st.sidebar.expander("Статистика Neo4j", expanded=True):
        stats = get_db_stats()
        if stats["nodes"]:
            st.markdown("**Вузли:**")
            for lbl, count in stats["nodes"].items():
                st.write(f"- `{lbl}`: {count}")
            st.markdown("**Зв'язки:**")
            for r_type, count in stats["relationships"].items():
                st.write(f"- `{r_type}`: {count}")
            st.markdown("**Ембедінги:**")
            for lbl, count in stats["embeddings"].items():
                st.write(f"- `{lbl}`: {count} векторів")
        else:
            st.warning("Не вдалося отримати статистику. Перевірте з'єднання з Neo4j.")

# Title Banner
st.markdown("""
<div class="title-container">
    <h1>🧠 Логічний GraphRAG Асистент</h1>
    <p>Аналіз логічних помилок, правил та концептів на основі бази знань підручника з логіки</p>
</div>
""", unsafe_allow_html=True)

# Query logic function
def process_user_query(query_text):
    if not conn["neo4j"]:
        st.error("Будь ласка, переконайтеся, що Neo4j запущено.")
        return None

    is_openrouter_model = "/" in selected_model or selected_model.endswith(":free")
    if not is_openrouter_model and not conn["ollama"]:
        st.error("З'єднання з Ollama відсутнє, а ви обрали локальну модель. Запустіть Ollama або оберіть модель OpenRouter.")
        return None

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        # 1. Get embedding
        query_emb = get_openrouter_query_embedding(query_text)
        if not query_emb:
            st.error("Помилка генерації ембедінгу через OpenRouter.")
            driver.close()
            return None

        # 2. Retrieve Graph Context
        graph_result = search_subgraph(driver, query_emb, limit=limit_nodes)
        driver.close()
        return graph_result
    except Exception as e:
        st.error(f"Помилка під час пошуку в БД: {e}")
        return None

# User interface input
user_query = st.chat_input("Задайте питання (наприклад: яка помилка в твердженні 'після цього, отже, через це'?)")

if user_query:
    # Append user message
    st.session_state.messages.append({"role": "user", "content": user_query})

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "graph_data" in message:
            # We can show the source tabs inside the history
            g_data = message["graph_data"]
            t1, t2 = st.tabs(["Джерела з Графу (Сутності)", "Зв'язки (Графовий Шлях)"])
            with t1:
                for node in g_data["nodes"]:
                    lbl = node["label"]
                    score = node["score"]
                    name = node["name"]
                    desc = node["description"]
                    lbl_class = f"tag-{lbl.lower()}"
                    st.markdown(f"""
                    <div class="card">
                        <span class="entity-tag {lbl_class}">{lbl}</span>
                        <strong>{name}</strong> <span style='color: #8b949e; font-size: 0.85rem;'>(Подібність: {score:.4f})</span>
                        <div style='margin-top: 8px; font-size: 0.95rem; color: #c9d1d9;'>{desc}</div>
                    </div>
                    """, unsafe_allow_html=True)
            with t2:
                if g_data["relationships"]:
                    for rel in g_data["relationships"]:
                        s_lbl = f"tag-{rel['source_label'].lower()}"
                        t_lbl = f"tag-{rel['target_label'].lower()}"
                        st.markdown(f"""
                        <div style='padding: 6px 0;'>
                            <span class="entity-tag {s_lbl}">{rel['source_label']}</span> <strong>{rel['source_name']}</strong>
                            <span class="relation-badge">-{rel['type']}-></span>
                            <span class="entity-tag {t_lbl}">{rel['target_label']}</span> <strong>{rel['target_name']}</strong>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("Для знайдених сутностей немає безпосередніх зв'язків у базі знань.")

# Handle new query
if user_query:
    with st.chat_message("assistant"):
        with st.spinner("Отримання контексту з графової бази Neo4j..."):
            graph_data = process_user_query(user_query)

        if graph_data:
            # Show retrieved data status
            st.success(f"Знайдено релевантних сутностей: {len(graph_data['nodes'])}")
            
            with st.spinner(f"Генерація відповіді за допомогою моделі {selected_model}..."):
                final_prompt = PROMPT_TEMPLATE.format(query=user_query, context=graph_data["context_text"])
                answer = query_llm(selected_model, final_prompt)
                
            # Render answer
            st.markdown(answer)
            
            # Save assistant message
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "graph_data": graph_data
            })
            
            # Display source tabs for the newly generated answer
            t1, t2 = st.tabs(["Джерела з Графу (Сутності)", "Зв'язки (Графовий Шлях)"])
            with t1:
                for node in graph_data["nodes"]:
                    lbl = node["label"]
                    score = node["score"]
                    name = node["name"]
                    desc = node["description"]
                    lbl_class = f"tag-{lbl.lower()}"
                    st.markdown(f"""
                    <div class="card">
                        <span class="entity-tag {lbl_class}">{lbl}</span>
                        <strong>{name}</strong> <span style='color: #8b949e; font-size: 0.85rem;'>(Подібність: {score:.4f})</span>
                        <div style='margin-top: 8px; font-size: 0.95rem; color: #c9d1d9;'>{desc}</div>
                    </div>
                    """, unsafe_allow_html=True)
            with t2:
                if graph_data["relationships"]:
                    for rel in graph_data["relationships"]:
                        s_lbl = f"tag-{rel['source_label'].lower()}"
                        t_lbl = f"tag-{rel['target_label'].lower()}"
                        st.markdown(f"""
                        <div style='padding: 6px 0;'>
                            <span class="entity-tag {s_lbl}">{rel['source_label']}</span> <strong>{rel['source_name']}</strong>
                            <span class="relation-badge">-{rel['type']}-></span>
                            <span class="entity-tag {t_lbl}">{rel['target_label']}</span> <strong>{rel['target_name']}</strong>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("Для знайдених сутностей немає безпосередніх зв'язків у базі знань.")
        else:
            st.warning("Не вдалося знайти контекст або підключитися до бази знань.")
