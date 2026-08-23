import os
import sys
import json
import base64
import requests
from bs4 import BeautifulSoup
from ebooklib import epub
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import gdrive_helper
import telegram_helper

LANG_CODE = "FR"
LANG_NAME = "French"
TASK_ID = os.environ.get("TASK_ID", f"novel_{LANG_CODE.lower()}_001")
TASK_PAYLOAD = os.environ.get("TASK_PAYLOAD", "")
DRIVE_ROOT = os.environ.get("GDRIVE_FOLDER_ID", "")

def parse_payload():
    if not TASK_PAYLOAD:
        return {"novel_id": TASK_ID, "title": "Sample Novel", "author": "Author", "chapters": [], "chat_id": "", "post_id": ""}
    try:
        decoded = base64.b64decode(TASK_PAYLOAD).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        return {"novel_id": TASK_ID, "title": "Sample Novel", "author": "Author", "chapters": [], "chat_id": "", "post_id": ""}

def build_txt_file(chapters, output_txt, title, author):
    with open(output_txt, "w", encoding="utf-8") as f:
        f.write(f"{title}\nAuthor: {author}\nLanguage: {LANG_NAME}\n\n" + "="*50 + "\n\n")
        for chap in chapters:
            f.write(f"\n\n### {chap.get('title', 'Chapter')}\n\n")
            f.write(chap.get("content", ""))
    return os.path.exists(output_txt)

def build_epub_file(chapters, output_epub, title, author):
    book = epub.EpubBook()
    book.set_identifier(f"novel-{LANG_CODE.lower()}-{title}")
    book.set_title(title)
    book.set_language(LANG_CODE.lower())
    book.add_author(author)

    epub_chapters = []
    for idx, chap in enumerate(chapters):
        c_title = chap.get("title", f"Chapter {idx+1}")
        c_item = epub.EpubHtml(title=c_title, file_name=f"chap_{idx+1:04d}.xhtml", lang=LANG_CODE.lower())
        body = f"<h2>{c_title}</h2>" + "".join(f"<p>{p}</p>" for p in chap.get("content", "").split("\n") if p.strip())
        c_item.content = body
        book.add_item(c_item)
        epub_chapters.append(c_item)

    book.toc = tuple(epub_chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + epub_chapters
    epub.write_epub(output_epub, book, {})
    return os.path.exists(output_epub)

def build_pdf_file(chapters, output_pdf, title, author):
    doc = SimpleDocTemplate(output_pdf, pagesize=letter)
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    h2_style = styles["Heading2"]
    normal_style = styles["Normal"]

    story = [
        Paragraph(title, title_style),
        Paragraph(f"<b>Author:</b> {author} | <b>Language:</b> {LANG_NAME}", normal_style),
        Spacer(1, 20),
        PageBreak()
    ]

    for chap in chapters:
        c_title = chap.get("title", "Chapter")
        story.append(Paragraph(c_title, h2_style))
        story.append(Spacer(1, 10))
        for p in chap.get("content", "").split("\n"):
            if p.strip():
                story.append(Paragraph(p.strip(), normal_style))
                story.append(Spacer(1, 6))
        story.append(PageBreak())

    doc.build(story)
    return os.path.exists(output_pdf)

def main():
    print(f"📖 Starting {LANG_NAME} Novel Engine for: {TASK_ID}")
    data = parse_payload()
    title = data.get("title", "Novel")
    author = data.get("author", "Author")
    chapters = data.get("chapters", [])
    chat_id = data.get("chat_id", "")
    post_id = data.get("post_id", "")

    work_dir = "./temp_downloads"
    os.makedirs(work_dir, exist_ok=True)

    safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
    txt_path = os.path.join(work_dir, f"{safe_title}.txt")
    pdf_path = os.path.join(work_dir, f"{safe_title}.pdf")
    epub_path = os.path.join(work_dir, f"{safe_title}.epub")

    # Build 3 formats
    print("🔨 Building TXT, PDF, and EPUB formats...")
    build_txt_file(chapters, txt_path, title, author)
    build_pdf_file(chapters, pdf_path, title, author)
    build_epub_file(chapters, epub_path, title, author)

    # Upload to GDrive
    try:
        lang_folder = gdrive_helper.get_or_create_folder(f"Novels_{LANG_CODE}", DRIVE_ROOT)
        novel_folder = gdrive_helper.get_or_create_folder(safe_title, lang_folder)
        gdrive_helper.upload_file_to_drive(txt_path, os.path.basename(txt_path), novel_folder)
        gdrive_helper.upload_file_to_drive(pdf_path, os.path.basename(pdf_path), novel_folder)
        gdrive_helper.upload_file_to_drive(epub_path, os.path.basename(epub_path), novel_folder)
        print(f"☁️ Uploaded all 3 formats to Google Drive.")
    except Exception as e:
        print(f"⚠️ GDrive upload warning: {e}")

    # Publish to TG comments
    if chat_id and post_id:
        caption = f"📚 <b>{title}</b>\n✍️ Tác giả: {author}\n🌐 Ngôn ngữ: {LANG_NAME}"
        telegram_helper.send_document(chat_id, epub_path, caption=f"{caption}\n📱 <b>Bản EPUB (Đọc trên điện thoại/Kindle)</b>", reply_to_message_id=int(post_id))
        telegram_helper.send_document(chat_id, pdf_path, caption=f"{caption}\n📕 <b>Bản PDF (In ấn & Mục lục)</b>", reply_to_message_id=int(post_id))
        telegram_helper.send_document(chat_id, txt_path, caption=f"{caption}\n📄 <b>Bản TXT (Văn bản thuần UTF-8)</b>", reply_to_message_id=int(post_id))
        print("📤 Published all formats to Telegram comments.")

    print(f"🎉 {LANG_NAME} novel processing finished successfully.")

if __name__ == "__main__":
    main()
