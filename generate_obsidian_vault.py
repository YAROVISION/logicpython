import os
import json
import re

def sanitize_name(name):
    """Sanitizes names to be safe for folders and filenames on Windows and Obsidian."""
    # Characters not allowed in Windows filenames: \ / : * ? " < > |
    # Replace colon with space-dash-space
    name = name.replace(":", " -")
    # Replace slash/backslash with dash
    name = name.replace("/", "-").replace("\\", "-")
    # Remove other forbidden characters
    name = re.sub(r'[*?"<>|]', '', name)
    # Strip whitespace
    return name.strip()

def main():
    json_dir = "logica_json_segments"
    vault_dir = "Логіка_Obsidian"
    
    if not os.path.exists(vault_dir):
        os.makedirs(vault_dir)
        print(f"Created vault directory: {vault_dir}")
        
    # Get all JSON segment files and sort them chronologically
    if not os.path.exists(json_dir):
        print(f"Error: directory '{json_dir}' does not exist.")
        return
        
    files = [f for f in os.listdir(json_dir) if f.endswith(".json")]
    files.sort() # segment_01_..., segment_02_...
    
    segments_data = []
    unique_sections = []
    section_folders = {}
    
    # First pass: read all data to build section-to-folder mapping and know next/prev relationships
    for filename in files:
        filepath = os.path.join(json_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        section = data.get("назва розділу", "").strip()
        segment = data.get("назва сегменту", "").strip()
        text = data.get("повний текст сегменту", "")
        
        # Track unique sections in order
        if section not in unique_sections:
            unique_sections.append(section)
            folder_idx = len(unique_sections)
            folder_name = f"{folder_idx:02d}_{sanitize_name(section)}"
            section_folders[section] = folder_name
            
        segments_data.append({
            "original_filename": filename,
            "section": section,
            "segment": segment,
            "text": text,
            "sanitized_segment": sanitize_name(segment)
        })
        
    # Create section directories
    for folder in section_folders.values():
        dir_path = os.path.join(vault_dir, folder)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"Created section folder: {dir_path}")
            
    # Second pass: write the markdown files
    for idx, seg in enumerate(segments_data):
        section = seg["section"]
        segment = seg["segment"]
        text = seg["text"]
        sanitized_segment = seg["sanitized_segment"]
        folder_name = section_folders[section]
        
        # Determine previous and next links
        prev_link = ""
        if idx > 0:
            prev_link = f"[[{segments_data[idx-1]['sanitized_segment']}]]"
            
        next_link = ""
        if idx < len(segments_data) - 1:
            next_link = f"[[{segments_data[idx+1]['sanitized_segment']}]]"
            
        # Format markdown content
        md_content = []
        md_content.append("---")
        md_content.append(f'розділ: "{section}"')
        md_content.append(f'сегмент: "{segment}"')
        md_content.append(f'номер: {idx + 1}')
        if prev_link:
            md_content.append(f'попередня: "{prev_link}"')
        if next_link:
            md_content.append(f'наступна: "{next_link}"')
        md_content.append("тип: конспект")
        md_content.append("---")
        md_content.append("")
        
        # Breadcrumbs
        md_content.append(f"[[Зміст|← Зміст]] | Розділ: **{section}**")
        md_content.append("")
        md_content.append(f"# {segment}")
        md_content.append("")
        md_content.append(text)
        md_content.append("")
        
        # Footer navigation
        footer = []
        if prev_link:
            prev_seg_name = segments_data[idx-1]['segment']
            footer.append(f"← [[{segments_data[idx-1]['sanitized_segment']}|Попередня: {prev_seg_name}]]")
        footer.append("[[Зміст|Зміст]]")
        if next_link:
            next_seg_name = segments_data[idx+1]['segment']
            footer.append(f"[[{segments_data[idx+1]['sanitized_segment']}|Наступна: {next_seg_name}]] →")
            
        md_content.append(" | ".join(footer))
        
        # Write to file
        md_filename = f"{sanitized_segment}.md"
        md_filepath = os.path.join(vault_dir, folder_name, md_filename)
        with open(md_filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(md_content))
            
    # Generate main index Zміст.md
    zmist_content = []
    zmist_content.append("# Зміст підручника \"Логіка\" (2021)")
    zmist_content.append("")
    
    current_section = None
    for seg in segments_data:
        section = seg["section"]
        segment = seg["segment"]
        sanitized_segment = seg["sanitized_segment"]
        
        if section != current_section:
            current_section = section
            zmist_content.append("")
            zmist_content.append(f"## {current_section}")
            zmist_content.append("")
            
        zmist_content.append(f"- [[{sanitized_segment}|{segment}]]")
        
    zmist_filepath = os.path.join(vault_dir, "Зміст.md")
    with open(zmist_filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(zmist_content))
        
    print(f"\nSuccess! Generated {len(segments_data)} markdown files and Зміст.md in '{vault_dir}'.")

if __name__ == "__main__":
    main()
