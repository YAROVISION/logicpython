import os
import re
import json

def normalize_text(text):
    # Переводимо в нижній регістр
    text = text.lower()
    # Нормалізуємо пробіли
    text = re.sub(r'\s+', ' ', text)
    # Замінюємо сполучники та/і/й на пробіли, щоб зробити їх еквівалентними
    text = re.sub(r'\b(та|і|й)\b', ' ', text)
    # Видаляємо всі не-буквено-цифрові символи
    return re.sub(r'[^\w]', '', text)

def strip_numbering(text):
    text = text.strip()
    # Видаляємо "Розділ X."
    text = re.sub(r'^(Розділ\s+\d+[\.:]?|Розділ\s+[IVXLCDM]+[\.:]?)\s*', '', text, flags=re.IGNORECASE)
    # Видаляємо нумерацію підрозділів типу "1.1.", "6.3." тощо
    text = re.sub(r'^(\d+\.)+\s*', '', text)
    return text.strip()

def build_known_headers(segments):
    headers = set()
    # Стандартні службові заголовки
    standard = [
        "передмова",
        "контрольні питання",
        "список рекомендованих джерел",
        "для нотаток",
        "навчальне видання",
        "підручник",
        "зміст"
    ]
    for s in standard:
        headers.add(normalize_text(s))
        headers.add(normalize_text(strip_numbering(s)))
        
    for seg in segments:
        sec = seg["section"]
        sub = seg["segment"]
        
        # Додаємо повні заголовки
        headers.add(normalize_text(sec))
        headers.add(normalize_text(strip_numbering(sec)))
        headers.add(normalize_text(sub))
        headers.add(normalize_text(strip_numbering(sub)))
        
        # Додаємо частини розділів/сегментів після розділення розділовими знаками
        for part in re.split(r'[\.:,—-]', sec):
            part_clean = strip_numbering(part)
            part_norm = normalize_text(part_clean)
            if len(part_norm) > 3:
                headers.add(part_norm)
                
        for part in re.split(r'[\.:,—-]', sub):
            part_clean = strip_numbering(part)
            part_norm = normalize_text(part_clean)
            if len(part_norm) > 3:
                headers.add(part_norm)
                
    return headers

def clean_page(page_num, text, known_headers_norm):
    lines = text.split('\n')
    cleaned_lines = []
    checking_header = True
    
    for line in lines:
        if checking_header:
            line_strip = line.strip()
            # Пропускаємо порожні рядки на початку сторінки
            if not line_strip:
                continue
                
            # Перевірка на номер сторінки (одне або декілька чисел з можливими крапками/дефісами)
            if re.match(r'^[-–—\s\.]*\d+(\s+\d+)?[-–—\s\.]*$', line_strip):
                continue
                
            # Очищуємо нумерацію з початку рядка та нормалізуємо його
            line_clean = strip_numbering(line_strip)
            line_norm = normalize_text(line_clean)
            
            # Якщо рядок порожній після видалення нумерації (наприклад, "1.1." або "Розділ 1.")
            if not line_norm:
                continue
                
            # Перевірка на відповідність відомим заголовкам
            if line_norm in known_headers_norm:
                continue
                
            # Якщо ми зустріли перший рядок, який не є заголовком чи номером сторінки,
            # припиняємо перевірку і додаємо всі наступні рядки
            checking_header = False
            
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines).strip()

def segment_book(md_path, output_dir):
    if not os.path.exists(md_path):
        print(f"Помилка: Файл {md_path} не знайдено.")
        return

    os.makedirs(output_dir, exist_ok=True)
    print(f"Зчитуємо {md_path}...")
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Розділяємо файл за шаблоном "## Сторінка X", враховуючи як \n, так і \r\n
    parts = re.split(r'## Сторінка (\d+)\s*\n', content)
    
    pages = {}
    
    for i in range(1, len(parts), 2):
        page_num = int(parts[i])
        page_text = parts[i+1]
        
        # Очищуємо текст від кінцевих розділювачів сторінок "---"
        page_text = page_text.strip()
        if page_text.endswith("---"):
            page_text = page_text[:-3].strip()
            
        pages[page_num] = page_text

    print(f"Успішно зчитано {len(pages)} сторінок.")

    # Визначаємо карту сегментів відповідно до скіла
    segments = [
        {"id": 1, "section": "Титульні сторінки та Зміст", "segment": "Титул, зміст", "start": 1, "end": 4},
        {"id": 2, "section": "Передмова", "segment": "Передмова", "start": 5, "end": 6},
        
        # Розділ 1
        {"id": 3, "section": "Розділ 1. Предмет і значення логіки. Мислення і мова", "segment": "1.1. Поняття про мислення", "start": 7, "end": 13},
        {"id": 4, "section": "Розділ 1. Предмет і значення логіки. Мислення і мова", "segment": "1.2. Предмет науки логіки", "start": 14, "end": 17},
        {"id": 5, "section": "Розділ 1. Предмет і значення логіки. Мислення і мова", "segment": "1.3. Історичні етапи розвитку науки логіки", "start": 18, "end": 23},
        {"id": 6, "section": "Розділ 1. Предмет і значення логіки. Мислення і мова", "segment": "1.4. Мислення і мова. Семіотика", "start": 24, "end": 28},
        {"id": 7, "section": "Розділ 1. Предмет і значення логіки. Мислення і мова", "segment": "1.5. Значення логіки для правознавства та юридичної практики", "start": 29, "end": 30},
        {"id": 8, "section": "Розділ 1. Предмет і значення логіки. Мислення і мова", "segment": "Контрольні питання до Розділу 1", "start": 31, "end": 31},
        
        # Розділ 2
        {"id": 9, "section": "Розділ 2. Поняття", "segment": "2.1. Поняття як форма думки. Поняття і слово", "start": 32, "end": 35},
        {"id": 10, "section": "Розділ 2. Поняття", "segment": "2.2. Логічна структура поняття. Закон зворотного відношення між змістом і обсягом поняття", "start": 36, "end": 36},
        {"id": 11, "section": "Розділ 2. Поняття", "segment": "2.3. Види понять", "start": 37, "end": 40},
        {"id": 12, "section": "Розділ 2. Поняття", "segment": "2.4. Відношення між поняттями. Діаграми Ейлера – Венна", "start": 41, "end": 43},
        {"id": 13, "section": "Розділ 2. Поняття", "segment": "2.5. Логічні операції з поняттями", "start": 44, "end": 65},
        {"id": 14, "section": "Розділ 2. Поняття", "segment": "Контрольні питання до Розділу 2", "start": 66, "end": 67},
        
        # Розділ 3
        {"id": 15, "section": "Розділ 3. Судження", "segment": "3.1. Загальна характеристика судження", "start": 68, "end": 71},
        {"id": 16, "section": "Розділ 3. Судження", "segment": "3.2. Прості судження", "start": 72, "end": 87},
        {"id": 17, "section": "Розділ 3. Судження", "segment": "3.3. Складні судження", "start": 88, "end": 95},
        {"id": 18, "section": "Розділ 3. Судження", "segment": "3.4. Модальні судження", "start": 96, "end": 100},
        {"id": 19, "section": "Розділ 3. Судження", "segment": "3.5. Логіка запитань і відповідей (інтерогативна логіка)", "start": 101, "end": 106},
        {"id": 20, "section": "Розділ 3. Судження", "segment": "Контрольні питання до Розділу 3", "start": 107, "end": 107},
        
        # Розділ 4
        {"id": 21, "section": "Розділ 4. Основні закони логіки", "segment": "4.1. Загальна характеристика основних законів логіки", "start": 108, "end": 108},
        {"id": 22, "section": "Розділ 4. Основні закони логіки", "segment": "4.2. Закон тотожності", "start": 109, "end": 109},
        {"id": 23, "section": "Розділ 4. Основні закони логіки", "segment": "4.3. Закон непротиріччя", "start": 110, "end": 110},
        {"id": 24, "section": "Розділ 4. Основні закони логіки", "segment": "4.4. Закон виключеного третього", "start": 111, "end": 112},
        {"id": 25, "section": "Розділ 4. Основні закони логіки", "segment": "4.5. Закон достатньої підстави", "start": 113, "end": 113},
        {"id": 26, "section": "Розділ 4. Основні закони логіки", "segment": "Контрольні питання до Розділу 4", "start": 114, "end": 114},
        
        # Розділ 5
        {"id": 27, "section": "Розділ 5. Умовивід", "segment": "5.1. Загальна характеристика умовиводів. Види умовиводів", "start": 115, "end": 116},
        {"id": 28, "section": "Розділ 5. Умовивід", "segment": "5.2. Безпосередні умовиводи", "start": 117, "end": 127},
        {"id": 29, "section": "Розділ 5. Умовивід", "segment": "5.3. Дедуктивні умовиводи", "start": 128, "end": 166},
        {"id": 30, "section": "Розділ 5. Умовивід", "segment": "5.4. Недедуктивні умовиводи", "start": 167, "end": 193},
        {"id": 31, "section": "Розділ 5. Умовивід", "segment": "Контрольні питання до Розділу 5", "start": 194, "end": 194},
        
        # Розділ 6
        {"id": 32, "section": "Розділ 6. Доведення і спростування. Гіпотеза", "segment": "6.1. Загальна характеристика доведення", "start": 195, "end": 196},
        {"id": 33, "section": "Розділ 6. Доведення і спростування. Гіпотеза", "segment": "6.2. Види доведення", "start": 197, "end": 201},
        {"id": 34, "section": "Розділ 6. Доведення і спростування. Гіпотеза", "segment": "6.3. Правила доведення та можливі логічні помилки в доведенні", "start": 202, "end": 208},
        {"id": 35, "section": "Розділ 6. Доведення і спростування. Гіпотеза", "segment": "6.4. Спростування. Методи спростування", "start": 209, "end": 210},
        {"id": 36, "section": "Розділ 6. Доведення і спростування. Гіпотеза", "segment": "6.5. Гіпотеза як форма пізнання", "start": 211, "end": 216},
        {"id": 37, "section": "Розділ 6. Доведення і спростування. Гіпотеза", "segment": "Контрольні питання до Розділу 6", "start": 217, "end": 217},
        
        # Список джерел та примітки
        {"id": 38, "section": "Список рекомендованих джерел", "segment": "Список рекомендованих джерел", "start": 218, "end": 220},
        {"id": 39, "section": "Додаткові матеріали", "segment": "Для нотаток", "start": 221, "end": 224}
    ]

    # Створюємо базу нормалізованих заголовків
    known_headers_norm = build_known_headers(segments)

    # Максимальний розмір шматка в сторінках для великих сегментів
    CHUNK_SIZE = 3

    for seg in segments:
        seg_id = seg["id"]
        section_name = seg["section"]
        segment_name = seg["segment"]
        start_page = seg["start"]
        end_page = seg["end"]

        total_pages = end_page - start_page + 1
        chunks_data = []

        # Визначаємо, чи потрібно розбивати сегмент на підсегменти
        if total_pages > 5:
            # Розбиваємо великий сегмент на шматки по CHUNK_SIZE сторінок
            for ch_start in range(start_page, end_page + 1, CHUNK_SIZE):
                ch_end = min(ch_start + CHUNK_SIZE - 1, end_page)
                
                chunk_text_parts = []
                for p in range(ch_start, ch_end + 1):
                    if p in pages:
                        cleaned_text = clean_page(p, pages[p], known_headers_norm)
                        if cleaned_text:
                            # 1. Видаляємо переноси слів на межі рядків
                            cleaned_text = re.sub(
                                r'([а-яА-ЯіІїЇєЄґҐa-zA-Z\u2019\x27]+)[-­\u2010\u2011]\s*\n\s*([а-яА-ЯіІїЇєЄґҐa-zA-Z\u2019\x27]+)',
                                r'\1\2',
                                cleaned_text
                            )
                            # 2. Замінюємо інші переноси рядків на пробіли
                            cleaned_text = re.sub(r'\s*\n\s*', ' ', cleaned_text)
                            # 3. Видаляємо переноси слів, які могли залишитися з пробілом
                            cleaned_text = re.sub(
                                r'([а-яА-ЯіІїЇєЄґҐa-zA-Z\u2019\x27]+)[-­\u2010\u2011]\s+([а-яА-ЯіІїЇєЄґҐa-zA-Z\u2019\x27]+)',
                                r'\1\2',
                                cleaned_text
                            )
                            chunk_text_parts.append(cleaned_text)
                
                if chunk_text_parts:
                    chunk_text = " ".join(chunk_text_parts)
                    # Видаляємо всі переноси слів, які залишилися з пробілом (зокрема крос-сторінкові)
                    chunk_text = re.sub(
                        r'([а-яА-ЯіІїЇєЄґҐa-zA-Z\u2019\x27]+)[-­\u2010\u2011]\s+([а-яА-ЯіІїЇєЄґҐa-zA-Z\u2019\x27]+)',
                        r'\1\2',
                        chunk_text
                    )
                    chunks_data.append({
                        "підсегмент_id": len(chunks_data) + 1,
                        "сторінки": f"{ch_start}-{ch_end}",
                        "текст": chunk_text
                    })
        else:
            # Для малих сегментів залишаємо один загальний шматок
            segment_text_parts = []
            for p in range(start_page, end_page + 1):
                if p in pages:
                    cleaned_text = clean_page(p, pages[p], known_headers_norm)
                    if cleaned_text:
                        # 1. Видаляємо переноси слів на межі рядків
                        cleaned_text = re.sub(
                            r'([а-яА-ЯіІїЇєЄґҐa-zA-Z\u2019\x27]+)[-­\u2010\u2011]\s*\n\s*([а-яА-ЯіІїЇєЄґҐa-zA-Z\u2019\x27]+)',
                            r'\1\2',
                            cleaned_text
                        )
                        # 2. Замінюємо інші переноси рядків на пробіли
                        cleaned_text = re.sub(r'\s*\n\s*', ' ', cleaned_text)
                        # 3. Видаляємо переноси слів, які могли залишитися з пробілом
                        cleaned_text = re.sub(
                            r'([а-яА-ЯіІїЇєЄґҐa-zA-Z\u2019\x27]+)[-­\u2010\u2011]\s+([а-яА-ЯіІїЇєЄґҐa-zA-Z\u2019\x27]+)',
                            r'\1\2',
                            cleaned_text
                        )
                        segment_text_parts.append(cleaned_text)
            
            if segment_text_parts:
                segment_text = " ".join(segment_text_parts)
                # Видаляємо всі переноси слів, які залишилися з пробілом (зокрема крос-сторінкові)
                segment_text = re.sub(
                    r'([а-яА-ЯіІїЇєЄґҐa-zA-Z\u2019\x27]+)[-­\u2010\u2011]\s+([а-яА-ЯіІїЇєЄґҐa-zA-Z\u2019\x27]+)',
                    r'\1\2',
                    segment_text
                )
                chunks_data.append({
                    "підсегмент_id": 1,
                    "сторінки": f"{start_page}-{end_page}",
                    "текст": segment_text
                })

        # Формуємо оновлений JSON-об'єкт
        json_data = {
            "назва розділу": section_name,
            "назва сегменту": segment_name,
            "загальна кількість сторінок": total_pages,
            "підсегменти": chunks_data
        }

        # Очищуємо ім'я файлу від заборонених символів
        clean_segment_name = "".join([c if c.isalnum() or c in '.-' else '_' for c in segment_name])
        clean_segment_name = re.sub(r'_+', '_', clean_segment_name).strip('_')
        
        if len(clean_segment_name) > 50:
            clean_segment_name = clean_segment_name[:50]
            
        filename = f"segment_{seg_id:02d}_{clean_segment_name}.json"
        file_path = os.path.join(output_dir, filename)

        with open(file_path, 'w', encoding='utf-8') as jf:
            json.dump(json_data, jf, ensure_ascii=False, indent=2)

        print(f"Збережено: {filename} (Шматків: {len(chunks_data)})")

    print(f"\nУспішно оновлено та експортовано {len(segments)} сегментів в папку '{output_dir}'.")

if __name__ == "__main__":
    segment_book("logica.md", "logica_json_segments")
