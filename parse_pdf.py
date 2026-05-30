import os
import sys

def parse_pdf_to_md(pdf_path, md_path):
    print(f"Починаємо парсинг файлу: {pdf_path}")
    if not os.path.exists(pdf_path):
        print(f"Помилка: Файл {pdf_path} не знайдено!")
        sys.exit(1)
        
    # Спробуємо використати PyMuPDF (fitz) як пріоритетний варіант
    try:
        import fitz  # PyMuPDF
        print("Використовуємо бібліотеку PyMuPDF (fitz) для парсингу...")
        
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        print(f"Знайдено сторінок: {total_pages}")
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f"# Логіка - Парсинг книги\n\n")
            f.write(f"Джерело: `{os.path.basename(pdf_path)}`\n\n")
            f.write("---\n\n")
            
            for i, page in enumerate(doc):
                page_num = i + 1
                print(f"Опрацювання сторінки {page_num}/{total_pages}...", end='\r')
                
                # Отримуємо текст
                text = page.get_text("text")
                
                # Додаємо сторінку у розмітці markdown
                f.write(f"## Сторінка {page_num}\n\n")
                if text.strip():
                    f.write(text)
                else:
                    f.write("*[Порожня сторінка або зображення]*")
                f.write("\n\n---\n\n")
                
        print(f"\nУспішно збережено у {md_path}")
        return
        
    except ImportError:
        print("PyMuPDF не встановлено. Спробуємо використати pypdf...")
        
    # Спробуємо використати pypdf
    try:
        import pypdf
        print("Використовуємо бібліотеку pypdf для парсингу...")
        
        reader = pypdf.PdfReader(pdf_path)
        total_pages = len(reader.pages)
        print(f"Знайдено сторінок: {total_pages}")
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f"# Логіка - Парсинг книги\n\n")
            f.write(f"Джерело: `{os.path.basename(pdf_path)}`\n\n")
            f.write("---\n\n")
            
            for i, page in enumerate(reader.pages):
                page_num = i + 1
                print(f"Опрацювання сторінки {page_num}/{total_pages}...", end='\r')
                
                text = page.extract_text()
                
                f.write(f"## Сторінка {page_num}\n\n")
                if text.strip():
                    f.write(text)
                else:
                    f.write("*[Порожня сторінка або зображення]*")
                f.write("\n\n---\n\n")
                
        print(f"\nУспішно збережено у {md_path}")
        return
        
    except ImportError:
        print("Помилка: Не знайдено жодної бібліотеки для роботи з PDF (ні PyMuPDF, ні pypdf).")
        print("Будь ласка, встановіть одну з них: pip install pymupdf або pip install pypdf")
        sys.exit(1)

if __name__ == "__main__":
    pdf_file = "pidr_logika_2021.pdf"
    md_file = "logica.md"
    
    # Можна також передавати параметри через командний рядок
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
    if len(sys.argv) > 2:
        md_file = sys.argv[2]
        
    parse_pdf_to_md(pdf_file, md_file)
