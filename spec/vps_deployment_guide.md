# Інструкція з розгортання GraphRAG на Hostinger VPS

Цей документ містить покрокові вказівки щодо запуску системи GraphRAG (Neo4j + Streamlit UI) у Docker-контейнерах на віртуальному сервері (VPS) від Hostinger.

Завдяки міграції на OpenRouter API для обчислення векторів та генерації відповідей, вимоги до апаратного забезпечення VPS є мінімальними (стабільно працює на тарифах з 2 ГБ RAM і більше).

---

## 📋 Попередня підготовка на VPS

Переконайтеся, що на вашому Hostinger VPS встановлено:
1. **Git**
2. **Docker** та **Docker Compose**

Якщо Docker не встановлено, ви можете встановити його за допомогою команд:
```bash
sudo apt update
sudo apt install docker.io docker-compose -y
sudo systemctl enable --now docker
```

---

## 🚀 Покроковий запуск системи

### 1. Клонування репозиторію
Підключіться до VPS по SSH та клонуйте проект:
```bash
git clone https://github.com/YAROVISION/logicpython.git
cd logicpython
```

### 2. Створення файлу оточення `.env`
Створіть файл `.env` у кореневій папці проекту для збереження ключа API OpenRouter:
```bash
nano .env
```
Додайте наступний рядок (замініть на свій реальний ключ):
```env
OPENROUTER_API_KEY=ваш_ключ_від_openrouter_тут
```
Збережіть файл (`Ctrl + O`, `Enter`, `Ctrl + X`).

### 3. Запуск Docker-контейнерів
Запустіть Neo4j та Streamlit у фоновому режимі:
```bash
docker compose up -d --build
```
* Docker завантажить необхідні образи, змонтує сховища для зберігання даних Neo4j та підніме веб-сервер Streamlit на порту `8501`.
* Перевірити статус запущених контейнерів можна командою: `docker compose ps`

### 4. Заповнення бази знань логіки (Neo4j)
Оскільки база даних у контейнері запуститься порожньою, виконайте імпорт та побудову векторів безпосередньо у контейнері Streamlit:

```bash
# Крок А: Імпорт сутностей та зв'язків з JSON-файлів у Neo4j
docker compose exec streamlit-app python3 extract_to_graph.py

# Крок Б: Створення 2048-вимірних індексів та розрахунок векторів через OpenRouter
docker compose exec streamlit-app python3 populate_embeddings.py
```
*Цей процес займе близько 2-3 хвилин. Після завершення ваша графова база буде повністю наповнена та готова до пошуку.*

---

## 🌐 Доступ до сервісів

Після запуску ви зможете отримати доступ до інтерфейсів з будь-якого пристрою:
* **Streamlit Веб-інтерфейс (чат-асистент)**: `http://IP_вашого_VPS:8501`
* **Neo4j Browser (адміністрування графу)**: `http://IP_вашого_VPS:7474` (логін: `neo4j`, пароль: `password`)

---

## 🛠️ Корисні команди для керування

* **Перегляд логів Streamlit**:
  ```bash
  docker compose logs -f streamlit-app
  ```
* **Перевірка стану графу та статистики бази**:
  ```bash
  docker compose exec streamlit-app python3 validate_graph.py
  ```
* **Зупинка сервісів**:
  ```bash
  docker compose down
  ```
