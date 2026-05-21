import json
import re
from pathlib import Path
from pypdf import PdfReader

PDF_FOLDER = "."
OUTPUT_JSON = "result.json"

MARKERS = [
    r'тогда\s+и\s+только\s+тогда',
    r'критери[яйюеи]?[м]?\b'
]

BREAK_WORDS = ['доказательство', 'таким образом', 'следовательно', 'отсюда', 'заметим', 'лемма', 'теорема']


STOP_SECTIONS = [
    "аннотация",  "ключевые слова", 
    "список литературы", "благодарности",
    "для цитирования", 
]


JUNK_STARTS = [
    "аннотация",  "ключевые слова",
    "список литературы", "благодарности",
    "для цитирования", "©", "doi", "удк",
    "поступила", "issn"
]

def clean_text(text):
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def fix_hyphen_breaks(text):
    
    return re.sub(r'(\w+)-\s+(\w+)', r'\1\2', text)

def remove_unwanted_sections(text):
  
    text_lower = text.lower()
    earliest_pos = len(text)
    for stop in STOP_SECTIONS:
        pos = text_lower.find(stop)
        if pos != -1 and pos < earliest_pos:
            earliest_pos = pos
    if earliest_pos < len(text):
        return text[:earliest_pos]
    return text

def is_junk_sentence(sent):
 
    sent_lower = sent.lower().strip()
    for junk in JUNK_STARTS:
        if sent_lower.startswith(junk):
            return True
    
    if len(sent_lower) < 10 and any(c in sent_lower for c in ['©', 'doi', 'udk']):
        return True
    return False

def count_words(text):
    return len(text.split())

def get_prev_sentences(sentences, marker_idx, max_count=2):
    prev_list = []
    for i in range(marker_idx - 1, -1, -1):
        if len(prev_list) >= max_count:
            break
        sent = sentences[i].strip()
        if sent:
            prev_list.insert(0, sent)
    return prev_list

def get_next_sentence(sentences, idx):
    return sentences[idx + 1].strip() if idx < len(sentences) - 1 else None

def is_break_word(sentence):
    if not sentence:
        return True
    for bw in BREAK_WORDS:
        if sentence.lower().strip().startswith(bw):
            return True
    return False

def extract_context(sentences, marker_idx):
    marker_sent = sentences[marker_idx].strip()
    if count_words(marker_sent) >= 10:
        return marker_sent
    context_parts = []
    prev_sentences = get_prev_sentences(sentences, marker_idx, max_count=2)
    context_parts.extend(prev_sentences)
    context_parts.append(marker_sent)
    next_sent = get_next_sentence(sentences, marker_idx)
    if next_sent and not is_break_word(next_sent):
        context_parts.append(next_sent)
    return ' '.join(context_parts)

def find_markers_in_text(text):
    """Ищет маркеры в тексте, возвращает список (индекс_начала, тип)."""
    results = []
    for pattern in MARKERS:
        for match in re.finditer(pattern, text.lower()):
            marker_type = "тогда и только тогда" if "тогда и только тогда" in match.group() else "критерий"
            results.append((match.start(), marker_type))
    return results

def split_sentences_safe(text):
    
    text = re.sub(r'(\d+)\.(\d+)', r'\1<DOT>\2', text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.replace('<DOT>', '.') for s in sentences if s.strip()]
    return sentences

def process_pdf(pdf_path):
    pdf_name = pdf_path.name.replace(".pdf", "")
    print(f"Обрабатываю: {pdf_name}")
    reader = PdfReader(str(pdf_path))
    results = []
    
    for page_num, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text()
        if not raw_text:
            continue
        
        text = clean_text(raw_text)
        text = remove_unwanted_sections(text)  # Удаляем мусорные секции
        if not text:
            continue
        
       
        markers = find_markers_in_text(text)
        if not markers:
            continue
        
        
        text_fixed = fix_hyphen_breaks(text)
        sentences = split_sentences_safe(text_fixed)
        
       
        seen_on_page = set()
        
        for marker_start, marker_type in markers:
        
            marker_idx = -1
            for idx, sent in enumerate(sentences):
                if marker_type == "тогда и только тогда":
                    if "тогда и только тогда" in sent.lower():
                        marker_idx = idx
                        break
                else:  # критерий
                    if re.search(r'критери[яйюеи]?[м]?\b', sent.lower()):
                        marker_idx = idx
                        break
            
            if marker_idx == -1:
                continue
            
            context = extract_context(sentences, marker_idx)
            
       
            if is_junk_sentence(context):
                continue
            
         
            key = (page_num, context)
            if key in seen_on_page:
                continue
            seen_on_page.add(key)
            
            results.append({
                "article_title": pdf_name,
                "page": page_num,
                "context": context,
                "marker": marker_type
            })
    
    return results

if __name__ == "__main__":
    folder = Path(PDF_FOLDER)
    pdf_files = list(folder.glob("*.pdf"))
    print(f"Найдено PDF: {len(pdf_files)}")
    
    all_results = []
    for pdf_file in pdf_files:
        all_results.extend(process_pdf(pdf_file))
    
    total_stats = {"тогда и только тогда": 0, "критерий": 0}
    files_stats = {}
    
    for item in all_results:
        marker = item["marker"]
        total_stats[marker] = total_stats.get(marker, 0) + 1
        
        file_name = item["article_title"]
        if file_name not in files_stats:
            files_stats[file_name] = {"тогда и только тогда": 0, "критерий": 0}
        files_stats[file_name][marker] = files_stats[file_name].get(marker, 0) + 1
    
  
    output_data = {
        "total_statistics": total_stats,
        "files_statistics": files_stats,
        "results": all_results
    }
    
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    
    print(f"Готово. Записей: {len(all_results)}. Сохранено в {OUTPUT_JSON}")
    print(f"Общая статистика: {total_stats}")