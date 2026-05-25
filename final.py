import json
import re
from pathlib import Path
from pypdf import PdfReader
import fitz
from PIL import Image
import io
from pix2text import Pix2Text
from natasha import Segmenter, NewsEmbedding, NewsNERTagger, Doc


PDF_FOLDER = "./pdfs"
OUTPUT_JSON = "result.json"

MARKERS = [
    r'тогда\s+и\s+только\s+тогда',
    r'критери[яйюеи]?[м]?\b'
]

BREAK_WORDS = ['доказательство', 'таким образом', 'следовательно', 'отсюда', 'заметим', 'лемма', 'теорема']

STOP_SECTIONS = [
    "аннотация", "abstract", "ключевые слова", "keywords",
    "список литературы", "references", "благодарности",
    "для цитирования", "for citation"
]

JUNK_STARTS = [
    "аннотация", "abstract", "ключевые слова", "keywords",
    "список литературы", "references", "благодарности",
    "для цитирования", "for citation", "©", "doi", "удк",
    "поступила", "received", "accepted", "issn"
]

segmenter = Segmenter()
emb = NewsEmbedding()
ner_tagger = NewsNERTagger(emb)


print("Загрузка Pix2Text...")
total_config = {
    'text_formula': {'languages': ('ru', 'en')}
}
p2t = Pix2Text.from_config(total_configs=total_config)
print("Готово.")

def find_annotation_position(text):
    patterns = [
        r'Аннотация', r'Abstract', r'Ключевые слова', r'Keywords',
        r'Введение', r'Introduction', r'Поступила', r'Received'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.start()
    return 2000

def is_likely_author(name):
    return bool(re.search(r'[А-Я]\.\s*[А-Я]\.\s*[А-Я][а-я]+', name))

def extract_authors_from_first_page(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = doc[0].get_text()
        doc.close()
        if not text:
            return ""
        
        lines = text.split('\n')[:15]
        first_lines = '\n'.join(lines)
        
        annotation_pos = find_annotation_position(first_lines)
        before_annotation = first_lines[:annotation_pos] if annotation_pos < len(first_lines) else first_lines
        
        doc_natasha = Doc(before_annotation)
        doc_natasha.segment(segmenter)
        doc_natasha.tag_ner(ner_tagger)
        
        authors = []
        for span in doc_natasha.spans:
            if span.type == 'PER' and is_likely_author(span.text):
                if '-' in span.text or span.text.endswith('-'):
                    continue
                authors.append(span.text)
        
        seen = set()
        unique_authors = []
        for a in authors:
            if a not in seen:
                seen.add(a)
                unique_authors.append(a)
        
        return '; '.join(unique_authors)
    except Exception as e:
        print(f"Ошибка при извлечении авторов из {pdf_path}: {e}")
        return ""

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

def extract_context(sentences, marker_idx,marker_type):
    marker_sent = sentences[marker_idx].strip()
    if marker_type == "тогда и только тогда":
        if count_words(marker_sent) >= 15:
            return marker_sent
    else:
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

def find_markers_in_text(sentences):
    results = []
    for idx, sent in enumerate(sentences):
        sent_lower = sent.lower()
        for pattern in MARKERS:
            if re.search(pattern, sent_lower):
                marker_type = "тогда и только тогда" if "тогда и только тогда" in sent_lower else "критерий"
                results.append((idx, marker_type))
                break
    return results

def split_sentences_safe(text):
    text = re.sub(r'(\d+)\.(\d+)', r'\1<DOT>\2', text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.replace('<DOT>', '.') for s in sentences if s.strip()]
    return sentences


def extract_formula_around_marker(pdf_path, page_num, marker_pos_in_text):
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_num - 1]
        
        words = page.get_text("words")
        marker_rect = None
        for w in words:
            if re.search(r'тогда\s+и\s+только\s+тогда|критери[яйюеи]?[м]?\b', w[4].lower()):
                marker_rect = fitz.Rect(w[0], w[1], w[2], w[3])
                break
        
        if marker_rect is None:
            return ""
        
        expanded_rect = marker_rect + (-150, -300, 150, 300)
        zoom = 300 / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, clip=expanded_rect)
        img_data = pix.tobytes("png")
        doc.close()
        
        img = Image.open(io.BytesIO(img_data))
        img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
        
        result = p2t.recognize(img, return_text=True)
        result = re.sub(r'\n+', '\n', result).strip()
        return result if result else ""
    except Exception as e:
        print(f"Ошибка распознавания формулы: {e}")
        return ""

def process_pdf(pdf_path):
    pdf_name = pdf_path.name.replace(".pdf", "")
    print(f"Обрабатываю: {pdf_name}")
    
    author = extract_authors_from_first_page(str(pdf_path))
    reader = PdfReader(str(pdf_path))
    results = []
    
    for page_num, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text()
        if not raw_text:
            continue
        
        text = clean_text(raw_text)
        text = remove_unwanted_sections(text)
        if not text:
            continue
        
        text_fixed = fix_hyphen_breaks(text)
        sentences = split_sentences_safe(text_fixed)
        markers = find_markers_in_text(sentences)
        
        if not markers:
            continue
        
        seen_on_page = set()
        
        for marker_idx, marker_type in markers:
            context = extract_context(sentences, marker_idx, marker_type)
            if is_junk_sentence(context):
                continue
            
            key = (page_num, context)
            if key in seen_on_page:
                continue
            seen_on_page.add(key)
            
            formula_latex = extract_formula_around_marker(str(pdf_path), page_num, 0)
            
            results.append({
                "article_title": pdf_name,
                "author": author,
                "page": page_num,
                "context": context,
                "formula_latex": formula_latex,
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
